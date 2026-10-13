import re

MAX_CONTENT_CHARS = 8000  # keeps prompts small and cheap, and bounds worst-case input size

INJECTION_PATTERNS = re.compile(
    r"(ignore (all|previous|the above) instructions|you are now|system:|assistant:)",
    re.IGNORECASE,
)

def sanitize_untrusted_text(text: str, label: str = "content") -> str:
    """Wrap any code/diff/file content pulled from GitHub before it enters
    a prompt. Truncates to a bounded size and neutralizes obvious
    prompt-injection phrasing. The LLM is told (in the system prompt)
    that anything inside these tags is data to analyze, never instructions
    to follow."""
    text = text[:MAX_CONTENT_CHARS]
    text = INJECTION_PATTERNS.sub("[filtered]", text)
    return f"<{label}>\n{text}\n</{label}>"