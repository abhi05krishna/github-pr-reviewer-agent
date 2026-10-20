import re
from app.models.review import Review

SEVERITY_ORDER = {"blocking": 0, "warning": 1, "suggestion": 2, "nit": 3}
MAX_COMMENTS = 15
MAX_MESSAGE_CHARS = 1200
MAX_SUMMARY_CHARS = 1500

LINK_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@(?=\w)")


def clean_text(text: str, limit: int) -> str:
    """Anything the model writes may have been influenced by attacker text,
    so strip links (phishing) and neutralize @mentions (notification spam)."""
    text = LINK_RE.sub("[link removed]", text)
    text = MENTION_RE.sub("@\u200b", text)
    return text[:limit]


def enforce_review_rules(review: Review, diff_lines: dict[str, set[int]]) -> Review:
    """Deterministic checks applied after the model. The model proposes,
    this code decides what is allowed to stand."""
    ordered = sorted(review.comments, key=lambda c: SEVERITY_ORDER[c.severity])[:MAX_COMMENTS]

    comments = []
    for c in ordered:
        in_diff = c.line is not None and c.line in diff_lines.get(c.file, set())
        comments.append(c.model_copy(update={
            "message": clean_text(c.message, MAX_MESSAGE_CHARS),
            "in_diff": in_diff,  # always recomputed, never trusted
        }))

    severities = {c.severity for c in comments}
    verdict = review.verdict
    if "blocking" in severities:
        verdict = "request_changes"
    elif "warning" in severities and verdict == "approve":
        verdict = "comment"
    if review.suspicious_content and verdict == "approve":
        verdict = "comment"  # a human must look at anything that tried to steer the bot

    note = clean_text(review.suspicious_note, 300) if review.suspicious_note else None

    return review.model_copy(update={
        "summary": clean_text(review.summary, MAX_SUMMARY_CHARS),
        "verdict": verdict,
        "comments": comments,
        "suspicious_note": note,
    })