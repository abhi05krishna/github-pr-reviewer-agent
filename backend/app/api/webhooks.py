import json
import logging
from fastapi import APIRouter, Request, HTTPException
from app.core.github_auth import verify_webhook_signature
from app.core.github_client import get_installation_token
import httpx

router = APIRouter()
logger = logging.getLogger("webhooks")


@router.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_webhook_signature(body, signature):
        # Reject anything that isn't genuinely from GitHub — this is the
        # security boundary for the whole system's entry point.
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event")
    payload = json.loads(body)

    if event_type == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        installation_id = payload["installation"]["id"]
        repo_full_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        head_ref = payload["pull_request"]["head"]["ref"]

        
        logger.info(f"PR event: {repo_full_name}#{pr_number} ({payload['action']})")

        diff = await fetch_pr_diff(installation_id, repo_full_name, pr_number)
        # Stage 1 just proves we can fetch it -  the agent loop that reads
        # and acts on this diff comes in a later stage.
        logger.info(f"Fetched diff, {len(diff)} characters")

        analysis = await analyze_pr(installation_id, repo_full_name, pr_number, diff, head_ref)
        logger.info(f"Agent analysis : \n{analysis}")

    return {"status": "received"}


async def fetch_pr_diff(installation_id: int, repo_full_name: str, pr_number: int) -> str:
    """The first real tool: GitHub will return a PR's diff directly if we
    ask for it with the right Accept header - no manual diffing needed."""
    token = await get_installation_token(installation_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.diff",
            },
        )
        resp.raise_for_status()
        return resp.text