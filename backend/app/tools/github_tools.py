import httpx
from app.core.github_client import get_installation_token
from app.core.gaurdrails import sanitize_untrusted_text


CODE_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".c", ".cpp", ".h", ".rs")
MAX_FILES = 40
MAX_FILE_BYTES = 100_000
MAX_MATCHES = 40

# direct scan nto avoid slipping of new repos by the agent 

async def find_usages(installation_id: int, repo_full_name: str, symbol: str, ref: str) -> str:
    """Scan the repo's source files at the PR branch for lines that mention a
    symbol. Works immediately on any repo, because it doesn't depend on
    GitHub's search index."""
    symbol = symbol.strip().rstrip("(").strip()
    if not symbol:
        return sanitize_untrusted_text("Error: empty symbol.", label="usages")

    token = await get_installation_token(installation_id)
    base_headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=20) as client:
        tree_resp = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/git/trees/{ref}",
            params={"recursive": "1"},
            headers={**base_headers, "Accept": "application/vnd.github+json"},
        )
        tree_resp.raise_for_status()
        entries = [
            e for e in tree_resp.json().get("tree", [])
            if e["type"] == "blob"
            and e["path"].endswith(CODE_EXTENSIONS)
            and e.get("size", 0) <= MAX_FILE_BYTES
        ][:MAX_FILES]

        matches = []
        for entry in entries:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/contents/{entry['path']}",
                params={"ref": ref},
                headers={**base_headers, "Accept": "application/vnd.github.raw+json"},
            )
            if resp.status_code != 200:
                continue
            for lineno, line in enumerate(resp.text.splitlines(), 1):
                if symbol in line:
                    matches.append(f"{entry['path']}:{lineno}: {line.strip()[:160]}")
                    if len(matches) >= MAX_MATCHES:
                        break
            if len(matches) >= MAX_MATCHES:
                break

    if not matches:
        text = (f"Scanned {len(entries)} source files and found no lines mentioning "
                f"'{symbol}'. Note: only the first {MAX_FILES} source files are scanned.")
    else:
        text = "\n".join(matches)
    return sanitize_untrusted_text(text, label="usages")


async def get_file_content(installation_id:int , repo_full_name:str, path:str, ref: str) -> str:
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


async def search_code(installation_id: int, repo_full_name: str, query: str) -> str:
    """Searches code within this specific repo for a symbol or function name,
    so the agent can find other callers of something the PR changed."""
    query = query.strip().rstrip("(").strip()   # models sometimes add a trailing "("
    token = await get_installation_token(installation_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/search/code",
            params={"q": f"{query} repo:{repo_full_name}"},   # no spaces around the colon
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return sanitize_untrusted_text(
                f"No search results for '{query}'. This does NOT prove there are no "
                "usages: GitHub only indexes the default branch and can lag behind "
                "recent commits. Say that usages could not be verified.",
                label="search_results",
            )
        summary = "\n".join(f"- {item['path']}" for item in items[:10])
        return sanitize_untrusted_text(summary, label="search_results")
