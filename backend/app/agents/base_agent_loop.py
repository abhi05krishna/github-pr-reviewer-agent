import json
import logging
import os
from groq import AsyncGroq

logger = logging.getLogger("agent")
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))


async def run_agent(system_prompt: str, user_message: str, tools: list, tool_functions: dict, max_steps: int = 5):
    """ReAct-style loop: the model reasons, optionally requests a tool, we
    execute it for real, feed the result back, and repeat until the model
    gives a final answer or we hit max_steps (a hard guardrail against
    runaway loops and cost)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Guardrail: remembers every (tool, arguments) pair already executed in
    # this run, so the model can't burn steps and API quota repeating itself.
    seen_calls = set()

    for step in range(max_steps):
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=tools,
            max_tokens=4000,  # reasoning models spend part of this on hidden reasoning
        )
        choice = response.choices[0].message

        if choice.tool_calls:
            # Store the model's tool request as plain dicts
            messages.append({
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
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

                logger.info(f"Agent step {step}: calling {fn_name}({fn_args})")

                call_key = (fn_name, json.dumps(fn_args, sort_keys=True))

                if call_key in seen_calls:
                    logger.warning(f"Duplicate call blocked: {fn_name}({fn_args})")
                    result = "You already made this exact call. Use the earlier result instead of repeating it."
                elif fn_name not in tool_functions:
                    result = f"Error: unknown tool {fn_name}"
                else:
                    seen_calls.add(call_key)
                    try:
                        result = await tool_functions[fn_name](**fn_args)
                    except Exception as e:
                        # A failing tool must never crash the agent; the
                        # model sees the error and decides what to do next.
                        logger.error(f"Tool {fn_name} failed: {e}")
                        result = f"Error running {fn_name}: {e}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                })
            continue  # next step of the loop

        return choice.content or ""

    logger.warning(f"Agent reached max steps ({max_steps}) without a final answer")
    return None