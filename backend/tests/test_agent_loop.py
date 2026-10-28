import asyncio
import json
import types

from app.agents import base_agent_loop as loop


def tool_spec(name):
    return {"type": "function", "function": {
        "name": name, "description": "d",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }}


LOOKUP = tool_spec("lookup")
SUBMIT = tool_spec("submit")


def tool_response(name, args=None):
    fn = types.SimpleNamespace(name=name, arguments=json.dumps(args or {}))
    call = types.SimpleNamespace(id="c1", function=fn)
    message = types.SimpleNamespace(content=None, tool_calls=[call])
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class ScriptedClient:
    """Replays a fixed list of responses and records which tools were offered."""

    def __init__(self, script):
        self.script = list(script)
        self.tool_sets = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.tool_sets.append([t["function"]["name"] for t in kwargs["tools"]])
        return self.script.pop(0)


def run(client, monkeypatch, tool_functions, **kwargs):
    monkeypatch.setattr(loop, "get_client", lambda: client)
    monkeypatch.setattr(loop, "model_chain", lambda: ["m"])
    return asyncio.run(loop.run_agent(
        "system", "user", [LOOKUP, SUBMIT], tool_functions,
        final_tool="submit", final_validator=lambda args: "done", **kwargs,
    ))


def test_repeated_duplicates_restrict_tools_to_final_tool(monkeypatch):
    client = ScriptedClient([tool_response("lookup")] * 3 + [tool_response("submit")])

    async def lookup():
        return "result"

    assert run(client, monkeypatch, {"lookup": lookup}) == "done"
    assert client.tool_sets[0] == ["lookup", "submit"]
    assert client.tool_sets[-1] == ["submit"]


def test_last_steps_only_allow_the_final_tool(monkeypatch):
    client = ScriptedClient([
        tool_response("lookup", {"n": 1}),
        tool_response("lookup", {"n": 2}),
        tool_response("submit"),
    ])

    async def lookup(n):
        return "result"

    assert run(client, monkeypatch, {"lookup": lookup}, max_steps=4) == "done"
    assert client.tool_sets == [["lookup", "submit"], ["lookup", "submit"], ["submit"]]