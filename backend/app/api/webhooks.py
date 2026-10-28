import json
import logging
import os
import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.core.github_auth import verify_webhook_signature
from app.core.github_client import get_installation_token
from app.agents.pr_review_agent import analyze_pr
from app.tools.review_poster import post_review

router = APIRouter()
logger = logging.getLogger("webhooks")


def posting_status(repo_full_name: str) -> tuple[bool, str]:
    """Fail closed: posting needs an explicit mode AND an allowlisted repo.
    Read at call time, not import time."""
    mode = os.environ.get("REVIEW_POST_MODE", "dry_run")
    allowed = {r.strip() for r in os.environ.get("REVIEW_ALLOWED_REPOS", "").split(",") if r.strip()}
    if mode != "comment":
        return False, f"mode is '{mode}', not 'comment'"
    if repo_full_name not in allowed:
        return False, f"{repo_full_name} is not in REVIEW_ALLOWED_REPOS"
    return True, "ok"


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


async def process_pr(installation_id: int, repo_full_name: str, pr_number: int, head_ref: str, head_sha: str):
    """Runs after the 200 response has already gone back to GitHub."""
    try:
        diff = await fetch_pr_diff(installation_id, repo_full_name, pr_number)
        logger.info(f"Fetched diff, {len(diff)} characters")
        review = await analyze_pr(installation_id, repo_full_name, pr_number, diff, head_ref)
        logger.info("Review:\n%s", review.model_dump_json(indent=2))

        ok, reason = posting_status(repo_full_name)
        if review.degraded:
            logger.warning("Review unavailable (agent failed); not posting to GitHub")
        elif ok:
            await post_review(installation_id, repo_full_name, pr_number, head_sha, review)
        else:
            logger.info(f"Posting disabled ({reason}): review was not sent to GitHub")
        
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

    if event_type == "pull_request" and payload.get("action") in ("opened", "synchronize", "reopened"):
        installation_id = payload["installation"]["id"]
        repo_full_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        head_ref = payload["pull_request"]["head"]["ref"]
        head_sha = payload["pull_request"]["head"]["sha"]
        logger.info(f"PR event: {repo_full_name}#{pr_number} ({payload['action']})")
        background_tasks.add_task(process_pr, installation_id, repo_full_name, pr_number, head_ref, head_sha)
    else:
        logger.info(f"Ignored event: {event_type} / {payload.get('action')}")

    return {"status": "received"}