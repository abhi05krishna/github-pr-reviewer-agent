import logging
import re
import httpx
from app.core.github_client import get_installation_token
from app.models.review import Review, ReviewComment

logger = logging.getLogger("review_poster")

MAX_BODY_CHARS = 20000
SAFE_PATH_RE = re.compile(r"[^\w./\-]")
FOOTER = (
    "\n\n---\n_Automated review by an AI agent. It can be wrong. "
    "It never approves or blocks a merge; a human decides._"
)


def _safe_path(path: str) -> str:
    """File paths come from the model, so keep only harmless characters
    before they go into markdown."""
    return SAFE_PATH_RE.sub("_", path)[:200]


def _outside_line(c: ReviewComment) -> str:
    location = _safe_path(c.file) + (f":{c.line}" if c.line else "")
    return f"- **{c.severity.upper()}** `{location}`: {c.message}"


def build_review_payload(review: Review, head_sha: str, inline: bool = True) -> dict:
    """Turn a validated Review into the body GitHub's review API expects.
    The event is always COMMENT: the bot never approves or requests changes."""
    inline_comments = []
    outside = []
    for c in review.comments:
        if inline and c.in_diff and c.line is not None:
            inline_comments.append({
                "path": c.file,
                "line": c.line,
                "side": "RIGHT",
                "body": f"**{c.severity.upper()}**: {c.message}",
            })
        else:
            outside.append(c)

    parts = [f"**Automated review: {review.verdict.replace('_', ' ')}**", "", review.summary]
    if outside:
        parts += ["", "**Findings outside the changed lines:**" if inline_comments else "**Findings:**"]
        parts += [_outside_line(c) for c in outside]
    if review.suspicious_content:
        parts += [
            "",
            "**Note:** text in this pull request tried to give instructions to the reviewer. "
            + (review.suspicious_note or ""),
        ]

    body = "\n".join(parts)[:MAX_BODY_CHARS] + FOOTER
    return {"commit_id": head_sha, "body": body, "event": "COMMENT", "comments": inline_comments}


async def post_review(installation_id: int, repo_full_name: str, pr_number: int, head_sha: str, review: Review) -> dict:
    token = await get_installation_token(installation_id)
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=build_review_payload(review, head_sha), headers=headers)

        if resp.status_code == 422:
            # Usually an inline comment GitHub won't accept. Keep the review by
            # moving every comment into the body.
            logger.warning("GitHub rejected inline comments (%s); retrying with everything in the body", resp.text[:300])
            resp = await client.post(url, json=build_review_payload(review, head_sha, inline=False), headers=headers)

        resp.raise_for_status()
        data = resp.json()

    logger.info(f"Posted review {data.get('id')} on {repo_full_name}#{pr_number}")
    return data