import asyncio
import json
import logging
import os
import random

from groq import (
    APIConnectionError,
    AsyncGroq,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger("agent")

MAX_MALFORMED_RETRIES = 2          # per model
MAX_SERVER_RETRIES = 2             # per model, for 5xx and network errors
MAX_DUPLICATES_BEFORE_FINISH = 2   # blocked repeats in a row before we force the final tool
FINISH_WINDOW = 2                  # in the last N steps only the final tool is offered
DEFAULT_MODELS = "openai/gpt-oss-120b,llama-3.3-70b-versatile"

_client = None


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def model_chain() -> list[str]:
    """Models to try in order. Override with LLM_MODELS in .env."""
    raw = os.environ.get("LLM_MODELS", DEFAULT_MODELS)
    return [m.strip() for m in raw.split(",") if m.strip()]


async def _sleep(seconds: float):
    await asyncio.sleep(seconds)


async def _call_with_backoff(model: str, messages: list, tools: list):
    """Retry transient server and network errors on ONE model."""
    for attempt in range(MAX_SERVER_RETRIES + 1):
        try:
            return await get_client().chat.completions.create(
                model=model, messages=messages, tools=tools, max_tokens=4000
            )
        except (InternalServerError, APIConnectionError) as e:
            if attempt == MAX_SERVER_RETRIES:
                raise
            delay = min(2 ** attempt, 8) + random.random()
            logger.warning(f"{model}: {type(e).__name__}; retry {attempt + 1} in {delay:.1f}s")
            await _sleep(delay)


class ModelSession:
    """Tracks which model we're on and decides when to retry or switch."""

    def __init__(self):
        self.models = model_chain()
        self.idx = 0
        self.malformed = 0

    def _switch(self):
        self.idx += 1
        self.malformed = 0

    async def complete(self, messages: list, tools: list):
        while True:
            if self.idx >= len(self.models):
                raise RuntimeError("All configured models failed")
            model = self.models[self.idx]
            try:
                return await _call_with_backoff(model, messages, tools)
            except (RateLimitError, NotFoundError) as e:
                logger.warning(f"{model}: unavailable ({type(e).__name__}); switching to next model")
                self._switch()
            except (InternalServerError, APIConnectionError) as e:
                logger.warning(f"{model}: still failing after retries ({type(e).__name__}); switching")
                self._switch()
            except BadRequestError as e:
                text = str(e)
                if "model_decommissioned" in text or "model_not_found" in text:
                    logger.warning(f"{model}: model unavailable; switching to next model")
                    self._switch()
                elif "tool_use_failed" not in text:
                    raise   # a real bug in our request; don't hide it
                else:
                    self.malformed += 1
                    if self.malformed <= MAX_MALFORMED_RETRIES:
                        valid = ", ".join(t["function"]["name"] for t in tools)
                        logger.warning(f"{model}: malformed tool call (retry {self.malformed})")
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your last tool call was malformed. Tool names must match exactly; "
                                f"the only valid tools are: {valid}. "
                                "Make your next call using one of those names."
                            ),
                        })
                    else:
                        logger.warning(f"{model}: too many malformed tool calls; switching model")
                        self._switch()


async def run_agent(
    system_prompt: str,
    user_message: str,
    tools: list,
    tool_functions: dict,
    final_tool: str | None = None,
    final_validator=None,
    max_steps: int = 8,
):
    """ReAct-style loop. If final_tool is set, the run ends when the model
    calls it with arguments that pass final_validator. After repeated
    duplicate calls, or near the step limit, only the final tool is offered,
    so the run always ends with an answer instead of running out of steps."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    seen_calls = set()
    duplicate_streak = 0
    restricted = False
    final_only = [t for t in tools if t["function"]["name"] == final_tool] if final_tool else []
    session = ModelSession()

    for step in range(max_steps):
        if final_tool and not restricted and (
            duplicate_streak >= MAX_DUPLICATES_BEFORE_FINISH or step >= max_steps - FINISH_WINDOW
        ):
            restricted = True
            logger.info(f"Step {step}: only {final_tool} is allowed from here")
            messages.append({
                "role": "user",
                "content": f"You have enough information. Call {final_tool} now with your review.",
            })

        active_tools = final_only if restricted else tools
        response = await session.complete(messages, active_tools)
        choice = response.choices[0].message

        if choice.tool_calls:
            messages.append({
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.tool_calls
                ],
            })

            for call in choice.tool_calls:
                fn_name = call.function.name
                try:
                    fn_args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                shown = "..." if fn_name == final_tool else fn_args
                logger.info(f"Agent step {step}: calling {fn_name}({shown})")

                call_key = (fn_name, json.dumps(fn_args, sort_keys=True))

                if final_tool and fn_name == final_tool:
                    try:
                        return final_validator(fn_args)
                    except Exception as e:
                        logger.warning(f"Final output rejected: {str(e)[:300]}")
                        result = f"Your submission was rejected: {str(e)[:600]}. Fix the problem and call {final_tool} again."
                elif call_key in seen_calls:
                    duplicate_streak += 1
                    logger.warning(f"Duplicate call blocked: {fn_name}({fn_args})")
                    result = "You already made this exact call. Use the earlier result instead of repeating it."
                elif fn_name not in tool_functions:
                    result = f"Error: unknown tool {fn_name}"
                else:
                    duplicate_streak = 0
                    seen_calls.add(call_key)
                    try:
                        result = await tool_functions[fn_name](**fn_args)
                    except Exception as e:
                        logger.error(f"Tool {fn_name} failed: {e}")
                        result = f"Error running {fn_name}: {e}"

                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
            continue

        if final_tool:
            messages.append({"role": "assistant", "content": choice.content or "(no content)"})
            messages.append({"role": "user", "content": f"Do not reply in plain text. Finish by calling {final_tool}."})
            continue

        return choice.content or ""

    logger.warning(f"Agent reached max steps ({max_steps}) without a final answer")
    return None