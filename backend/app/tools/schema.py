GET_FILE_CONTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_file_content",
        "description": "Fetch the full content of a specific file in the repo at the PR's branch, to see context beyond the diff.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root, e.g. 'sample_app/auth.py'",
                },
            },
            "required": ["path"],
        },
    },
}

SEARCH_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_code",
        "description": "Search this repo's code for a function or symbol name to find other places it is used, before flagging a breaking change.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Function or symbol name to search for",
                },
            },
            "required": ["query"],
        },
    },
}
FIND_USAGES_TOOL = {
    "type": "function",
    "function": {
        "name": "find_usages",
        "description": "Scan the repo's source files at the PR branch for every line that mentions a function or symbol name. Use it to find callers of anything the PR changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Function, class or variable name, without parentheses",
                },
            },
            "required": ["symbol"],
        },
    },
}

ALL_PR_REVIEW_TOOLS = [GET_FILE_CONTENT_TOOL, FIND_USAGES_TOOL]
