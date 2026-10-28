from app.core.evidence import Evidence
from app.core.output_gaurdrails import verify_outside_lines
from app.models.review import Review, ReviewComment
from app.tools.github_tools import number_lines


def test_usage_lines_are_recorded_and_checked():
    e = Evidence()
    e.record_usages("<usages>\nbackend/sample_app/api.py:1: from x import verify_token\n"
                    "backend/sample_app/api.py:4: if verify_token(t):\n</usages>")
    assert e.shows("backend/sample_app/api.py", 4)
    assert not e.shows("backend/sample_app/api.py", 3)


def test_numbered_file_content_sets_bounds():
    e = Evidence()
    e.record_file("a.py", "<file_content>\n   1 | a\n   2 | b\n</file_content>")
    assert e.shows("a.py", 2)
    assert not e.shows("a.py", 3)


def make_review(line, in_diff):
    return Review(summary="s", verdict="comment", comments=[
        ReviewComment(file="x/api.py", line=line, severity="blocking", message="m", in_diff=in_diff),
    ])


def test_unverified_line_on_outside_comment_is_dropped():
    e = Evidence()
    e.record_usages("x/api.py:4: call")
    assert verify_outside_lines(make_review(3, False), e).comments[0].line is None


def test_verified_line_is_kept_and_in_diff_comments_are_untouched():
    e = Evidence()
    e.record_usages("x/api.py:4: call")
    assert verify_outside_lines(make_review(4, False), e).comments[0].line == 4
    assert verify_outside_lines(make_review(3, True), e).comments[0].line == 3


def test_number_lines():
    assert number_lines("a\nb") == "   1 | a\n   2 | b"