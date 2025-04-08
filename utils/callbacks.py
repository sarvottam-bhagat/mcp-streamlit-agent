from typing import Any, Dict, List
import json
import streamlit as st
from langchain_core.callbacks import AsyncCallbackHandler


class StreamlitCallbackHandler(AsyncCallbackHandler):
    """
    Base Streamlit callback handler
    """
    def __init__(self, text_placeholder, tool_placeholder):
        self.text_placeholder = text_placeholder
        self.tool_placeholder = tool_placeholder
        self.accumulated_text = []
        self.accumulated_tool = []

    async def streamlit_log_tokens(self, text: str):
        self.text_placeholder.markdown("".join(self.accumulated_text))

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        print(f"on_tool_start serialized: {serialized}, input_str: {input_str}, kwargs: {kwargs}")
        self.accumulated_tool.append("\n```json\n" + json.dumps(serialized, indent=2, ensure_ascii=False) + "\n```\n")
        self.accumulated_tool.append("\n```json\n" + input_str + "\n```\n")
        print(f"on_tool_start accumulated_tool: {self.accumulated_tool}")
        with self.tool_placeholder.expander("🔧 Tool Call Information", expanded=True):
            st.markdown("".join(self.accumulated_tool))

    async def on_tool_end(self, output: str, **kwargs) -> None:
        print(f"on_tool_end output: {output}, kwargs: {kwargs}")

        # Extract content area from output and add to accumulated_tool
        if hasattr(output, 'content'): # claude
            # Handle cases where Korean characters are displayed as Unicode escape sequences
            try:
                # Check if the string is in JSON format and parse it
                json_obj = json.loads(output.content)
                # Convert back to JSON so that characters are displayed properly
                formatted_content = json.dumps(json_obj, indent=2, ensure_ascii=False)
                self.accumulated_tool.append("\n```json\n" + formatted_content + "\n```\n")
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, use the original content as is
                self.accumulated_tool.append("\n```json\n" + output.content + "\n```\n")
        else:
            self.accumulated_tool.append("\n```json\n" + output + "\n```\n")
        with self.tool_placeholder.expander("🔧 Tool Call Information", expanded=True):
            st.markdown("".join(self.accumulated_tool))

    async def on_tool_error(self, error: Exception, **kwargs) -> None:
        with self.tool_placeholder.expander("🔧 Tool Call Information", expanded=True):
            st.markdown("".join(self.accumulated_tool))


class ClaudeCallbackHandler(StreamlitCallbackHandler):
    """
    Callback handler for Claude/Anthropic models
    """
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        print(f"[ClaudeCallbackHandler] token: {token} , kwargs : {kwargs}")
        if isinstance(token, list):
            content = token[0]
            if isinstance(content, dict) and "text" in content:
                self.accumulated_text.append(content["text"])
                await self.streamlit_log_tokens(token)


class GPTCallbackHandler(StreamlitCallbackHandler):
    """
    Callback handler for GPT/OpenAI models
    """
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        print(f"[GPTCallbackHandler] token: {token} , kwargs : {kwargs}")
        self.accumulated_text.append(token)
        await self.streamlit_log_tokens(token)


class GeminiCallbackHandler(StreamlitCallbackHandler):
    """
    Callback handler for Gemini/Google models
    """
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        print(f"[GeminiCallbackHandler] token: {token} , kwargs : {kwargs}")
        self.accumulated_text.append(token)
        await self.streamlit_log_tokens(token)


def get_model_callback_handler(model_type: str, text_placeholder, tool_placeholder) -> AsyncCallbackHandler:
    """
    Returns the appropriate callback handler based on the model type.
    """
    handlers = {
        "claude": ClaudeCallbackHandler,
        "openai": GPTCallbackHandler,
        "gemini": GeminiCallbackHandler
    }
    handler_class = handlers.get(model_type, StreamlitCallbackHandler)
    return handler_class(text_placeholder, tool_placeholder)
