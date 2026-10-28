from app.models.review import Review, ReviewComment
from app.tools.review_poster import build_review_payload


def make_review():
    return Review(
        summary="Breaking change.",
        verdict="request_changes",
        comments=[
            ReviewComment(file="sample_app/auth.py", line=1, severity="blocking", message="Signature changed.", in_diff=True),
            ReviewComment(file="sample_app/api.py", line=4, severity="blocking", message="Caller breaks.", in_diff=False),
        ],
    )


def test_never_approves_or_requests_changes():
    assert build_review_payload(make_review(), "abc123")["event"] == "COMMENT"


def test_in_diff_comments_are_inline_and_others_go_in_body():
    p = build_review_payload(make_review(), "abc123")
    assert [c["path"] for c in p["comments"]] == ["sample_app/auth.py"]
    assert p["comments"][0]["side"] == "RIGHT" and p["comments"][0]["line"] == 1
    assert "sample_app/api.py:4" in p["body"]


def test_fallback_puts_everything_in_the_body():
    p = build_review_payload(make_review(), "abc123", inline=False)
    assert p["comments"] == []
    assert "sample_app/auth.py:1" in p["body"]


def test_body_has_verdict_and_disclaimer():
    body = build_review_payload(make_review(), "abc123")["body"]
    assert "request changes" in body and "never approves" in body


def test_unsafe_path_is_sanitized():
    r = Review(summary="s", verdict="comment", comments=[
        ReviewComment(file="x`\n@evil", line=None, severity="nit", message="m"),
    ])
    assert "`\n@evil" not in build_review_payload(r, "abc123")["body"]