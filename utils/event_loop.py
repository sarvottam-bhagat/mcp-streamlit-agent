import asyncio
import nest_asyncio
import streamlit as st

# Apply nest_asyncio: Allow nested calls within an already running event loop
nest_asyncio.apply()

def initialize_event_loop():
    """
    Initialize the event loop and save it to the session state.
    If already initialized, return the existing loop.
    """
    if "event_loop" not in st.session_state:
        loop = asyncio.new_event_loop()
        st.session_state.event_loop = loop
        asyncio.set_event_loop(loop)
        return loop
    return st.session_state.event_loop

def ensure_event_loop():
    """
    Check if the current event loop is set, and if not,
    create a new one or get it from the session state.

    Returns:
        asyncio.AbstractEventLoop: The currently active event loop
    """
    try:
        loop = asyncio.get_event_loop()

        # If the event loop is closed, create a new one
        if loop.is_closed():
            return initialize_event_loop()

        return loop
    except RuntimeError:
        # If there is no event loop or it cannot be accessed, create a new one
        return initialize_event_loop()