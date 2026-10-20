import re

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def walk_diff(diff: str):
    """Yield (file, new_line, marker, text) for every line inside a hunk.
    marker is '+', '-' or ' '. new_line is None for removed lines."""
    current_file = None
    in_hunk = False
    new_line = 0

    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            in_hunk = False
            current_file = None
            continue

        if not in_hunk:
            # Still in the file header: look for the new path, then the first hunk
            if raw.startswith("+++ "):
                path = raw[4:].strip()
                current_file = path[2:] if path.startswith("b/") else None
                continue
            m = HUNK_RE.match(raw)
            if m and current_file:
                in_hunk = True
                new_line = int(m.group(1))
            continue

        m = HUNK_RE.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if raw.startswith("\\"):  # "\ No newline at end of file"
            continue

        marker = raw[:1] if raw[:1] in ("+", "-") else " "
        text = raw[1:]
        if marker == "-":
            yield current_file, None, "-", text
        else:
            yield current_file, new_line, marker, text
            new_line += 1


def changed_lines(diff: str) -> dict[str, set[int]]:
    """File -> set of new-file line numbers that appear in the diff."""
    result: dict[str, set[int]] = {}
    for file, line, _marker, _text in walk_diff(diff):
        result.setdefault(file, set())
        if line is not None:
            result[file].add(line)
    return result


def annotate_diff(diff: str) -> str:
    """Prefix each line with its new-file line number so the model doesn't
    have to count lines from hunk headers."""
    out = []
    last_file = None
    for file, line, marker, text in walk_diff(diff):
        if file != last_file:
            out.append(f"=== {file} ===")
            last_file = file
        if line is None:
            out.append(f"      - {text}")
        else:
            out.append(f"{line:>5} {marker} {text}")
    return "\n".join(out)