import json
import logging
from groq import AsyncGroq
import os


logger = logging.getLogger("agent")
client =  AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

async def run_agent(system_prompt : str, user_message : str, tools : list, tool_function : dict, max_steps : int =5):
    """ReAct-style loop: the model reasons, optionally picks a tool, we
    execute it for real, feed the result back, and repeat until the model
    gives a final answer or we hit max_steps (a hard guardrail against
    runaway loops/cost)."""

    messages  = [
        {"role" : "system", "content" : system_prompt},
        {"role" : "user", "content" : user_message},
    ]

    for step in range(max_steps) : 
        response = await client.chat.completions.create(
            model = "openai/gpt-oss-120b",
            messages = messages,
            tools = tools,
            max_tokens = 2000,
        )

        choice = response.choices[0].message

        if choice.tool_calls:
            messages.append({"role" : "assistant", "tool_calls" : choice.tool_calls , "content" : choice.content or ""})
            for call in choice.tool_calls:
                fn_name = call.function_name
                try : 
                    fn_args = json.loads(call.function.arguments)
                except json.JSONDecodeError: 
                    fn_args = {}

                logger.info(f"Agent step {step} : {fn_name}({fn_args})")

                if fn_name not in tool_functions:
                    result = f"Error : unknown tool {fn_name}"
                else :
                    try :
                        result =  f"Error : unknown tool {fn_name}"
                    except Exception as e:
                        logger.error(f"Tool {fn_name} failed : {e}")
                        result = f"Error  running {fn_name} : {e}"


                messages.append({
                    "role" : "tool", 
                    "tool_call_id" : call.id,
                    "content" : str(result)
                })

            continue # next step of the loop

        return choice.content or ""

    logger.warning(f"Agent reached max steps ({max_steps}) without a final answer")
    return None


                    
                
                    


