import httpx
from app.core.github_client import get_installation_token
from app.core.gaurdrails import sanitize_untrusted_text


async def get_file_content(installation_id:int , repo_full_name:str, path:str) -> str:
    """Fetch a single file's full content at a specific commit ref.
    This is how the agent looks *beyond* the diff — e.g. seeing a whole
    function's context when the diff only shows a few changed lines."""

    token = await get_installation_token(installation_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/contents/{path}",
            params={"ref":ref},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },   #raw file content not json 
        )

        if resp.status_code == 404:
            raise sanitize_untrusted_text(f"File not found: {path}", label="tool_result")
        resp.raise_for_status()
        return sanitize_untrusted_text(resp.text, label="file_content")


async def search_code(installation_id : int , repo_full_name : str, query : str) -> str:
    """Searches code within this specific repo for a symbol/function name —
    this is how the agent finds other callers of something the PR changed,
    without needing to understand the whole codebase upfront."""


    token = await get_installation_token(installation_id)
    async with httpx.AsyncClient() as client:
        resp =  await client.get(
            "https://api.github.com/search/code",
            params  = {"q" : f"{query} repo : {repo_full_name}"},
            headers = {
                "Authorization" : f"Bearer {token}",
                "Accept" : "application/vnd.github+json",

            },
        )

        resp.raise_for_status()
        items = resp.json().get("items", [])

        print(items)
        if not items:
            return sanitize_untrusted_text(f"No code results for query: {query}", label="tool_result")
        summary = "\n".join(f"- {item['path']}" for item in items[:10])
        return sanitize_untrusted_text(summary, label="tool_result")

