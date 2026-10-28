import re

USAGE_RE = re.compile(r"^(\S+?):(\d+):", re.MULTILINE)      # find_usages lines: path:line: code
NUMBERED_RE = re.compile(r"^\s*(\d+) \| ", re.MULTILINE)    # get_file_content lines:   4 | code


class Evidence:
    """Remembers which (file, line) pairs the tools actually showed the model."""

    def __init__(self):
        self.usage_lines: dict[str, set[int]] = {}
        self.read_files: dict[str, int] = {}    # file -> highest line number shown

    def record_usages(self, text: str):
        for path, lineno in USAGE_RE.findall(text):
            self.usage_lines.setdefault(path, set()).add(int(lineno))

    def record_file(self, path: str, text: str):
        numbers = [int(n) for n in NUMBERED_RE.findall(text)]
        if numbers:
            self.read_files[path] = max(numbers)

    def shows(self, path: str, line: int) -> bool:
        if line in self.usage_lines.get(path, set()):
            return True
        return 1 <= line <= self.read_files.get(path, 0)