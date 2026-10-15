import json
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.core.github_auth import verify_webhook_signature
from app.core.github_client import get_installation_token
from app.agents.pr_review_agent import analyze_pr

router = APIRouter()
logger = logging.getLogger("webhooks")


async def fetch_pr_diff(installation_id: int, repo_full_name: str, pr_number: int) -> str:
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


async def process_pr(installation_id: int, repo_full_name: str, pr_number: int, head_ref: str):
    """Runs after the 200 response has already gone back to GitHub."""
    try:
        diff = await fetch_pr_diff(installation_id, repo_full_name, pr_number)
        logger.info(f"Fetched diff, {len(diff)} characters")
        analysis = await analyze_pr(installation_id, repo_full_name, pr_number, diff, head_ref)
        logger.info(f"Agent analysis:\n{analysis}")
    except Exception:
        logger.exception("PR processing failed")


@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event")
    payload = json.loads(body)

    if event_type == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        installation_id = payload["installation"]["id"]
        repo_full_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        head_ref = payload["pull_request"]["head"]["ref"]
        logger.info(f"PR event: {repo_full_name}#{pr_number} ({payload['action']})")
        background_tasks.add_task(process_pr, installation_id, repo_full_name, pr_number, head_ref)

    return {"status": "received"}