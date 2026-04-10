TOOL_NAME = "hello_World"
TOOL_DESCRIPTION = "Just says hello"

async def run(params: dict, agent: dict) -> str:
    query = params.get("query", "")
    return f"Hello!"