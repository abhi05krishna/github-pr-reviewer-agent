import json
import logging
import os
from groq import AsyncGroq
from groq import  BadRequestError

logger = logging.getLogger("agent")
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
MAX_MALFORMED_RETRIES = 2

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
    calls it with arguments that pass final_validator. Invalid submissions
    are sent back to the model as errors so it can fix them."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    seen_calls = set()

    malformed_retries = 0
    valid_tools = ", ".join(t["function"]["name"] for t in tools)

    for step in range(max_steps):
        try:
            response = await client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=tools,
                max_tokens=4000,
            )
        except BadRequestError as e:
            if "tool_use_failed" in str(e) and malformed_retries < MAX_MALFORMED_RETRIES:
                malformed_retries += 1
                logger.warning(f"Malformed tool call from model (retry {malformed_retries}): {str(e)[:200]}")
                messages.append({
                    "role": "user",
                    "content": (
                        "Your last tool call was malformed. Tool names must match exactly; "
                        f"the only valid tools are: {valid_tools}. "
                        "Make your next call using one of those names."
                    ),
                })
                continue
            raise
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
                    logger.warning(f"Duplicate call blocked: {fn_name}({fn_args})")
                    result = "You already made this exact call. Use the earlier result instead of repeating it."
                elif fn_name not in tool_functions:
                    result = f"Error: unknown tool {fn_name}"
                else:
                    seen_calls.add(call_key)
                    try:
                        result = await tool_functions[fn_name](**fn_args)
                    except Exception as e:
                        logger.error(f"Tool {fn_name} failed: {e}")
                        result = f"Error running {fn_name}: {e}"

                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
            continue

        if final_tool:
            # The model answered in plain text instead of submitting. Push it back.
            messages.append({"role": "assistant", "content": choice.content or "(no content)"})
            messages.append({"role": "user", "content": f"Do not reply in plain text. Finish by calling {final_tool}."})
            continue

        return choice.content or ""

    logger.warning(f"Agent reached max steps ({max_steps}) without a final answer")
    return None