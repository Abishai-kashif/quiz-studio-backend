# import asyncio
# from typing import Optional, Any
# from contextlib import AsyncExitStack
# from mcp import ClientSession, types
# from mcp.client.streamable_http import streamablehttp_client
# from dataclasses import dataclass
# from pprint import pprint

# class MCPClient:
#     def __init__(
#         self,
#         server_url: str,
#     ):
#         self._server_url = server_url
#         self._session: Optional[ClientSession] = None
#         self._exit_stack: AsyncExitStack = AsyncExitStack()

#     async def connect(self):
#         streamable_transport = await self._exit_stack.enter_async_context(
#             streamablehttp_client(self._server_url)
#         )
#         _read, _write, _ = streamable_transport

#         self._session = await self._exit_stack.enter_async_context(
#             ClientSession(_read, _write)
#         )
#         await self._session.initialize()

#     def session(self) -> ClientSession:
#         if self._session is None:
#             raise ConnectionError(
#                 "Client session not initialized or cache not populated. Call connect_to_server first."
#             )
#         return self._session
    
#     async def list_tools(self) -> types.ListToolsResult | list[None]:
#         result = await self.session().list_tools()
#         return result.tools
    
#     async def call_tool(
#         self, tool_name: str, tool_input: dict
#     ) -> types.CallToolResult | None:
#         result = await  self.session().call_tool(tool_name, tool_input)
#         pprint(result)

#         content = result.content[0]
#         if (type(content) == types.TextContent):
#             return content.text

#     async def cleanup(self):
#         await self._exit_stack.aclose()
#         self._session = None


#     async def __aenter__(self):
#         await self.connect()
#         return self
    
#     async def __aexit__(self, *args: Any):
#         await self.cleanup()



# async def main():
#     async with MCPClient("http://localhost:8000/mcp") as client:
#         tools = await client.list_tools()
#         print("Available tools:")
#         pprint(tools)

#         print("*" * 20)

#         print("Calling get_docs tool...")
#         result = await client.call_tool("get_doc", ["deposition.md"])
#         print(">>>>>>>>>>>>>> ", result)


# if __name__ == "__main__":
#     asyncio.run(main())