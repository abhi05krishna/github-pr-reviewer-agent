from app.models.review import Review, ReviewComment
# from app.core.gaurdrails import enforce_review_rules
from app.core.output_gaurdrails import enforce_review_rules

DIFF_LINES = {"sample_app/auth.py": {1, 2, 3, 4}}


def make(verdict, comments, suspicious=False):
    return Review(summary="s", verdict=verdict, comments=comments, suspicious_content=suspicious)


def comment(severity, file="sample_app/auth.py", line=1, msg="m"):
    return ReviewComment(file=file, line=line, severity=severity, message=msg)


def test_blocking_forces_request_changes():
    assert enforce_review_rules(make("approve", [comment("blocking")]), DIFF_LINES).verdict == "request_changes"


def test_warning_downgrades_approve():
    assert enforce_review_rules(make("approve", [comment("warning")]), DIFF_LINES).verdict == "comment"


def test_suspicious_content_blocks_approve():
    assert enforce_review_rules(make("approve", [], suspicious=True), DIFF_LINES).verdict == "comment"


def test_in_diff_is_computed_not_trusted():
    c = ReviewComment(file="sample_app/api.py", line=3, severity="warning", message="m", in_diff=True)
    assert enforce_review_rules(make("comment", [c]), DIFF_LINES).comments[0].in_diff is False


def test_comments_sorted_by_severity():
    r = enforce_review_rules(make("comment", [comment("nit"), comment("blocking")]), DIFF_LINES)
    assert [c.severity for c in r.comments] == ["blocking", "nit"]


def test_links_and_mentions_are_neutralized():
    r = enforce_review_rules(make("comment", [comment("nit", msg="ping @admin see https://evil.example/x")]), DIFF_LINES)
    msg = r.comments[0].message
    assert "https://" not in msg and "@admin" not in msg