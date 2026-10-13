GET_FILE_CONTENT_TOOL = {
    "type" : "function",
    "function" : {
        "name" : "get_file_content",
        "description" : "Fetch the full content of a specific file in the repo at the PR's branch , to see content beyond the diff", 
        "parameters" : {
            "type" : "object", 
            "properties" : {
                "path" : {
                    "type" : "string",
                    "description" : "The path of the file to fetch"
                }, 
                "required" : ["path"],
            }
        }
    }

    
}

SEARCH_CODE_TOOL = {
    "type" : "function",
    "function" : {
        "name" : "search_code",
        "description" : "Searches code within this specific repo for a symbol/function name — this is how the agent finds other callers of something the PR changed, without needing to understand the whole codebase upfront.",
        "parameters" : {
            "type" : "object",
            "properties" : {
                "query" : {
                    "type" : "string",
                    "description" : "The symbol or function name to search for"
                }
            },
            "required" : ["query"]
        }
    }

    
        
}

ALL_PR_REVIEW_TOOLS = [GET_FILE_CONTENT_TOOL, SEARCH_CODE_TOOL]