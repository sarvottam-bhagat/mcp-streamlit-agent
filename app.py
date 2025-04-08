import json
import uuid
import os
import streamlit as st
import asyncio
from typing import Any, Callable, Dict, List
from utils.event_loop import initialize_event_loop, ensure_event_loop
from utils.callbacks import get_model_callback_handler

initialize_event_loop()

from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig

# Load environment variables (get API keys and other settings from .env file)
load_dotenv(override=True)

# Print loaded environment variables for debugging (excluding sensitive values)
print("Loaded environment variables:")
print(f"OPENWEATHER_API_KEY: {'Set' if os.environ.get('OPENWEATHER_API_KEY') else 'Not set'}")


async def astream_graph(
    graph: CompiledStateGraph,
    inputs: Dict[str, Any],
    config: RunnableConfig,
    node_names: List[str] = [],
    callback: Callable[[Dict[str, str]], None] = None,
):
    """
    Asynchronously streams the execution results of a LangGraph.

    Parameters:
    - graph (CompiledStateGraph): The compiled LangGraph to be executed.
    - inputs (dict): The input data dictionary to be passed to the graph.
    - config (RunnableConfig): Execution configuration.
    - node_names (List[str], optional): List of node names to filter output (empty list means all nodes).
    - callback (Callable[[Dict[str, str]], None], optional): A callback function for processing each chunk.
      The callback receives a dictionary with keys "node" (str) and "content" (str).

    Returns:
    - None: This function prints the streaming output but does not return any value.
    """

    prev_node = ""

    async for chunk_msg, metadata in graph.astream(
        inputs, config, stream_mode="messages"
    ):
        curr_node = metadata["langgraph_node"]
        # Process only the specified nodes if node_names is not empty
        if not node_names or curr_node in node_names:
            if callback:
                callback({"node": curr_node, "content": chunk_msg})
            else:
                if curr_node != prev_node:
                    print("\n" + "=" * 50)
                    print(f"🔄 Node: \033[1;36m{curr_node}\033[0m 🔄")
                    print("- " * 25)

            prev_node = curr_node

# Page settings: title, icon, layout configuration
st.set_page_config(page_title="Agent with MCP Tools", page_icon="🧠", layout="wide")

# Add author information at the top of the sidebar (placed before other sidebar elements)
st.sidebar.markdown("### ✍️ Developed by Sarvottam")
st.sidebar.divider()  # Add divider

# Page title and description
st.title("🤖 Agent with MCP Tools")
st.markdown("✨ Ask questions to the ReAct agent using MCP tools.")

# Initialize session state
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = False  # Session initialization status flag
    st.session_state.agent = None  # Storage for ReAct agent object
    st.session_state.history = []  # List for storing conversation history
    st.session_state.mcp_client = None  # Storage for MCP client object
    st.session_state.selected_model = "claude"  # Set Claude as the default model

if "thread_id" not in st.session_state:
    st.session_state.thread_id = uuid.uuid4()


# --- Function Definitions ---
def print_message():
    """
    Display chat history on screen.
    """
    for message in st.session_state.history:
        if message["role"] == "user":
            st.chat_message("user").markdown(message["content"])
        elif message["role"] == "assistant":
            st.chat_message("assistant").write(message["content"], unsafe_allow_html=True)
        elif message["role"] == "assistant_tool":
            with st.expander("🔧 Tool Call Information", expanded=False):
                st.markdown(message["content"])


# 기존 process_query 함수를 주석 처리하고 새로운 버전 추가
async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=60):
    """
    Process user query and generate response.
    """
    try:
        ensure_event_loop()

        if st.session_state.agent:
            # Use new callback handler
            callback_handler = get_model_callback_handler(
                st.session_state.selected_model,
                text_placeholder,
                tool_placeholder
            )

            try:
                response = await asyncio.wait_for(
                    astream_graph(
                        st.session_state.agent,
                        {"messages": [HumanMessage(content=query)]},
                        config=RunnableConfig(
                            callbacks=[callback_handler],
                            recursion_limit=100,
                            thread_id=st.session_state.thread_id
                        ),
                    ),
                    timeout=timeout_seconds,
                )

            except asyncio.TimeoutError:
                error_msg = f"⏱️ Request exceeded {timeout_seconds} seconds. Please try again later."
                return {"error": error_msg}, error_msg, ""

            final_text = "".join(callback_handler.accumulated_text)
            final_tool = "".join(callback_handler.accumulated_tool)

            return response, final_text, final_tool

        else:
            return (
                {"error": "🚫 Agent is not initialized."},
                "🚫 Agent is not initialized.",
                "",
            )
    except Exception as e:
        import traceback
        error_msg = f"❌ Error during query processing: {str(e)}\n{traceback.format_exc()}"
        return {"error": error_msg}, error_msg, ""


def _create_agent_with_model(model_name: str, tools: List[Any]):
    """Creates the specific LLM and the ReAct agent."""
    prompt = "Use your tools to answer the question."  # Removed Korean instruction
    if model_name == "claude":
        model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0.1,
            max_tokens=8192
        )
    elif model_name == "openai":
        model = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,
            max_tokens=4096
        )
    elif model_name == "gemini":
        model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1,
            max_tokens=8192
        )
    else:
        # Default to Claude
        model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            temperature=0.1,
            max_tokens=8192
        )

    agent = create_react_agent(
        model,
        tools,
        checkpointer=MemorySaver(),
        prompt=prompt,
    )
    return agent


async def initialize_mcp_connection(mcp_config=None):
    """
    Initializes the MCP client connection and retrieves tools.
    Handles closing of the previous client.

    Returns:
        tuple(MultiServerMCPClient | None, List[Any] | None):
            A tuple containing the client and tools, or (None, None) on failure.
    """
    # Close previous client if exists
    if st.session_state.mcp_client:
        try:
            print(f"Closing existing MCP client")
            await st.session_state.mcp_client.__aexit__(None, None, None)
            st.session_state.mcp_client = None # Clear reference after closing
        except Exception as client_exit_e:
            print(f"Error closing previous MCP client: {client_exit_e}") # Log error but continue
            st.session_state.mcp_client = None # Attempt to clear reference even if close failed

    # Create and enter new client
    try:
        with st.spinner("🔄 Connecting to MCP server..."):
            print("inner Connecting to MCP server...")
            client = MultiServerMCPClient(mcp_config)
            await client.__aenter__()
            tools = client.get_tools()
            print(f"MCP Connection successful, {len(tools)} tools retrieved.")
            return client, tools # Return client and tools
    except Exception as e:
        st.error(f"❌ MCP client connection or tool loading failed: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None, None # Indicate failure


async def apply_and_reinitialize(config):
    """
    Applies the provided MCP configuration, re-initializes the MCP connection,
    and recreates the agent. Handles status updates and errors.
    """
    apply_status = st.empty()
    initialization_attempted = False # Flag to track if full init was attempted
    success = False
    try:
        with apply_status.container():
            st.warning("🔄 Applying MCP tool settings and reconfiguring agent...")
            progress_bar = st.progress(0)
            progress_bar.progress(10)

            # Clear old state
            st.session_state.session_initialized = False
            st.session_state.agent = None
            st.session_state.tools = None
            # st.session_state.mcp_client is handled within initialize_mcp_connection

            print(f"Applying new MCP config: {config}")
            initialization_attempted = True

            # Initialize MCP Connection
            progress_bar.progress(30)
            new_client, new_tools = await initialize_mcp_connection(config)
            progress_bar.progress(60)

            if new_client and new_tools:
                st.session_state.mcp_client = new_client
                st.session_state.tools = new_tools # Store tools
                st.session_state.tool_count = len(new_tools)

                try:
                    # Create Agent using the current model selection
                    selected_model_name = st.session_state.selected_model
                    st.session_state.agent = _create_agent_with_model(selected_model_name, new_tools)
                    st.session_state.session_initialized = True
                    success = True
                    progress_bar.progress(100)
                    st.success("✅ MCP tool settings applied and agent reconfigured successfully.")
                    await asyncio.sleep(2)
                    apply_status.empty()
                except Exception as agent_e:
                    progress_bar.progress(100)
                    st.error(f"❌ Error occurred while creating agent: {agent_e}")
                    # Keep error message visible
            else:
                # initialize_mcp_connection already showed an error
                progress_bar.progress(100)
                st.error("❌ Cannot create agent due to MCP connection or tool loading failure.")
                # Keep error message visible

    except Exception as outer_e:
        # Catch errors in the status display logic itself
        st.error(f"❌ Error occurred while updating reinitialization status: {str(outer_e)}")
        # Attempt to clear any lingering status message if possible
        try:
            apply_status.empty()
        except: pass # Ignore cleanup errors

    # Rerun only if initialization was actually attempted and successful
    if initialization_attempted and success:
        st.rerun()
    elif not success:
         # Clear spinner/warning if it failed but didn't rerun
         try: apply_status.empty()
         except: pass


async def recreate_agent_only():
    """
    Recreates the agent using the currently selected model and existing tools.
    Assumes the MCP client connection is already valid.
    """

    success = False
    try:
        st.session_state.session_initialized = False # Mark as uninitialized during agent creation
        st.session_state.agent = None # Clear old agent

        selected_model_name = st.session_state.selected_model
        tools = st.session_state.tools
        new_agent = _create_agent_with_model(selected_model_name, tools)

        st.session_state.agent = new_agent
        st.session_state.session_initialized = True
        success = True

    except Exception as e:
         st.error(f"❌ Error occurred while reconfiguring agent: {e}")
         import traceback
         st.error(traceback.format_exc())
         # Keep error message visible
         st.session_state.session_initialized = False # Ensure state reflects failure

    # Rerun only on success, show toast first
    if success:
        st.rerun()
    else:
        pass


# --- Sidebar UI: MCP Tool Addition Interface ---
with st.sidebar.expander("Add MCP Tools", expanded=False):
    default_config = """{
  "weather": {
    "command": "python",
    "args": ["./adapters/weather_server.py"],
    "transport": "stdio"
  }
}"""
    # If pending_config doesn't exist, create it based on existing mcp_config_text
    if "pending_mcp_config" not in st.session_state:
        # Load values from configs/default.json file
        with open("configs/default.json", "r") as f:
            default_json = json.load(f)

        # Assign mcpServers content from default.json to pending_mcp_config
        if "mcpServers" in default_json:
            st.session_state.pending_mcp_config = default_json["mcpServers"]
        else:
            st.session_state.pending_mcp_config = default_json


    # UI for adding individual tools
    st.subheader("Add Individual Tool")
    st.markdown(
        """
    Enter **one tool** in JSON format:

    ```json
    {
      "tool_name": {
        "command": "execution_command",
        "args": ["arg1", "arg2", ...],
        "transport": "stdio"
      }
    }
    ```
    ⚠️ **Important**: JSON must be wrapped in curly braces (`{}`).
    """
    )

    # Provide a clearer example
    example_json = {
        "github": {
            "command": "npx",
            "args": [
                "-y",
                "@smithery/cli@latest",
                "run",
                "@smithery-ai/github",
                "--config",
                '{"githubPersonalAccessToken":"your_token_here"}',
            ],
            "transport": "stdio",
        }
    }

    default_text = json.dumps(example_json, indent=2, ensure_ascii=False)

    new_tool_json = st.text_area(
        "Tool JSON",
        default_text,
        height=250,
    )

    # Add button
    if st.button(
        "Add Tool",
        type="primary",
        key="add_tool_button",
        use_container_width=True,
    ):
        try:
            # Validate input
            if not new_tool_json.strip().startswith(
                "{"
            ) or not new_tool_json.strip().endswith("}"):
                st.error("JSON must start and end with curly braces ({}).")
                st.markdown('Correct format: `{ "tool_name": { ... } }`')
            else:
                # Parse JSON
                parsed_tool = json.loads(new_tool_json)

                # Check if it's in mcpServers format and process accordingly
                if "mcpServers" in parsed_tool:
                    # Move contents inside mcpServers to the top level
                    parsed_tool = parsed_tool["mcpServers"]
                    st.info("'mcpServers' format detected. Converting automatically.")

                # Check the number of tools entered
                if len(parsed_tool) == 0:
                    st.error("Please enter at least one tool.")
                else:
                    # Process all tools
                    success_tools = []
                    for tool_name, tool_config in parsed_tool.items():
                        # Check URL field and set transport
                        if "url" in tool_config:
                            # If URL exists, set transport to "sse"
                            tool_config["transport"] = "sse"
                            st.info(
                                f"URL detected in '{tool_name}' tool. Transport set to 'sse'."
                            )
                        elif "transport" not in tool_config:
                            # If no URL and no transport, set default to "stdio"
                            tool_config["transport"] = "stdio"

                        # Check required fields
                        if "command" not in tool_config and "url" not in tool_config:
                            st.error(
                                f"'{tool_name}' tool configuration requires 'command' or 'url' field."
                            )
                        elif "command" in tool_config and "args" not in tool_config:
                            st.error(
                                f"'{tool_name}' tool configuration requires 'args' field."
                            )
                        elif "command" in tool_config and not isinstance(
                            tool_config["args"], list
                        ):
                            st.error(
                                f"'{tool_name}' tool's 'args' field must be an array ([]) format."
                            )
                        else:
                            # Add tool to pending_mcp_config
                            st.session_state.pending_mcp_config[tool_name] = tool_config
                            success_tools.append(tool_name)

                    # Apply immediately instead of success message
                    if success_tools:
                        st.info(f"Added tools: {', '.join(success_tools)}. Applying changes...")
                        # Apply changes immediately
                        st.session_state.event_loop.run_until_complete(
                            apply_and_reinitialize(st.session_state.pending_mcp_config)
                        )
                        # Rerun happens inside apply_and_reinitialize on success

        except json.JSONDecodeError as e:
            st.error(f"JSON parsing error: {e}")
            st.markdown(
                f"""
            **How to fix**:
            1. Check that the JSON format is correct.
            2. All keys must be wrapped in double quotes (").
            3. String values must also be wrapped in double quotes (").
            4. If using double quotes within a string, they must be escaped (\").
            """
            )
        except Exception as e:
            st.error(f"Error occurred: {e}")

    # Add divider
    st.divider()

    # Display current tool settings (read-only)
    st.subheader("Current Tool Settings (Read-only)")
    st.code(
        json.dumps(st.session_state.pending_mcp_config, indent=2, ensure_ascii=False)
    )

# --- Display registered tools list and add delete button ---
with st.sidebar.expander("Registered Tools List", expanded=True):
    try:
        pending_config = st.session_state.pending_mcp_config
    except Exception as e:
        st.error("Not a valid MCP tool configuration.")
    else:
        # Iterate through the keys (tool names) in pending config and display them
        for tool_name in list(pending_config.keys()):
            col1, col2 = st.columns([8, 2])
            col1.markdown(f"- **{tool_name}**")
            if col2.button("Delete", key=f"delete_{tool_name}"):
                # Delete the tool from pending config (not applied immediately)
                tool_name_deleted = tool_name # Store name for message
                del st.session_state.pending_mcp_config[tool_name]
                st.info(f"{tool_name_deleted} tool has been deleted. Applying changes...")
                # Apply changes immediately
                st.session_state.event_loop.run_until_complete(
                    apply_and_reinitialize(st.session_state.pending_mcp_config)
                )
                # Rerun happens inside apply_and_reinitialize on success


with st.sidebar:

    # 모델 선택 UI 추가
    st.subheader("🚀 Select LLM Model")
    model_options = {
        "claude": "Claude 3.5 Haiku (Anthropic)",
        "openai": "GPT-4o (OpenAI)",
        "gemini": "Gemini 2.0 Flash (Google)"
    }

    # Get index of currently selected model, default to 0 if not found
    current_model_key = st.session_state.selected_model
    default_index = 0
    model_keys = list(model_options.keys())
    if current_model_key in model_keys:
        default_index = model_keys.index(current_model_key)

    selected_model = st.selectbox(
        "Select LLM Model",
        model_keys,
        format_func=lambda x: model_options[x],
        index=default_index
    )

    # 선택된 모델이 변경되면 에이전트만 재구성
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model
        # Call the function to recreate only the agent
        st.session_state.event_loop.run_until_complete(
            recreate_agent_only()
        )
        # Rerun is handled within recreate_agent_only on success


# --- Initialize default session (if not initialized) ---
if not st.session_state.session_initialized:
    st.info("🔄 Connecting to MCP server and initializing agent...")
    # Use the full reinitialize function for the initial setup
    st.session_state.event_loop.run_until_complete(
        apply_and_reinitialize(st.session_state.pending_mcp_config)
    )
    # apply_and_reinitialize handles success/error messages and potential rerun


# --- Display conversation history ---
print_message()

# --- User input and processing ---
user_query = st.chat_input("💬 Enter your question")
if user_query:
    if st.session_state.session_initialized:
        st.chat_message("user").markdown(user_query)
        with st.chat_message("assistant"):
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            resp, final_text, final_tool = (
                st.session_state.event_loop.run_until_complete(
                    process_query(user_query, text_placeholder, tool_placeholder)
                )
            )

        if resp and "error" in resp:
            st.error(resp["error"])
        else:
            # Model tag styles
            model_tags = {
                "claude": {"name": "Claude", "color": "orange"},
                "openai": {"name": "GPT", "color": "black"},
                "gemini": {"name": "Gemini", "color": "blue"}
            }

            current_model = st.session_state.selected_model
            model_info = model_tags.get(current_model, {"name": "AI", "color": "gray"})

            model_tag = f'<span style="background-color: {model_info["color"]}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px;">{model_info["name"]}</span>'

            final_text_with_tag = f"{model_tag}{final_text}"

            st.session_state.history.append({"role": "user", "content": user_query})
            st.session_state.history.append(
                {"role": "assistant", "content": final_text_with_tag}
            )
            if final_tool.strip():
                st.session_state.history.append(
                    {"role": "assistant_tool", "content": final_tool}
                )
            st.rerun()
    else:
        st.warning("⏳ System is still initializing. Please try again in a moment.")

# --- Sidebar: Display system information ---
with st.sidebar:
    st.subheader("🔧 System Information")
    st.write(f"🛠️ MCP Tools Count: {st.session_state.get('tool_count', 'Initializing...')}")

    st.divider()

    # Reset conversation button
    if st.button("🔄 Reset Conversation", use_container_width=True, type="primary"):
        st.session_state.thread_id = uuid.uuid4()
        st.session_state.history = []
        st.success("✅ Conversation has been reset.")
        st.rerun()


