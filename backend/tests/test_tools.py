import asyncio

from agent.tools import tool, ToolManager


@tool
async def echo(text: str) -> str:
    """Echo the given text back to the caller."""
    return f"echo: {text}"


def test_tool_extract_and_schemas():
    assert echo.card.name == "echo"
    assert echo.card.description.startswith("Echo")
    assert echo.card.parameters["properties"]["text"]["type"] == "string"

    tm = ToolManager()
    tm.register(echo)
    schemas = tm.schemas()
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "echo"


def test_tool_execute_and_unknown():
    tm = ToolManager()
    tm.register(echo)
    out = asyncio.run(tm.execute("echo", {"text": "hi"}))
    assert out == "echo: hi"

    from agent.tools.errors import ToolError
    try:
        asyncio.run(tm.execute("nope", {}))
        assert False, "should raise"
    except ToolError:
        pass
