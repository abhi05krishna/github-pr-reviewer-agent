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

ALL_PR_REVIEW_TOOLS = [GET_FILE_CONTENT_TOOL, SEARCH_CODE_TOOL]