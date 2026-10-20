from app.core.diff_utils import changed_lines, annotate_diff

SAMPLE_DIFF = "\n".join([
    "diff --git a/sample_app/auth.py b/sample_app/auth.py",
    "index 111..222 100644",
    "--- a/sample_app/auth.py",
    "+++ b/sample_app/auth.py",
    "@@ -1,2 +1,4 @@",
    "-def verify_token(token):",
    "+def verify_token(token, require_admin):",
    "+    if require_admin:",
    '+        return token == "admin-token"',
    '     return token == "secret-token"',
])


def test_changed_lines():
    assert changed_lines(SAMPLE_DIFF) == {"sample_app/auth.py": {1, 2, 3, 4}}


def test_annotate_numbers_new_lines_and_marks_removed():
    out = annotate_diff(SAMPLE_DIFF)
    assert "    1 + def verify_token(token, require_admin):" in out
    assert "- def verify_token(token):" in out


def test_removed_line_that_looks_like_a_header_is_not_misread():
    diff = "\n".join([
        "diff --git a/q.sql b/q.sql",
        "--- a/q.sql",
        "+++ b/q.sql",
        "@@ -1,2 +1,1 @@",
        "--- old comment",
        "+select 1;",
    ])
    assert changed_lines(diff) == {"q.sql": {1}}