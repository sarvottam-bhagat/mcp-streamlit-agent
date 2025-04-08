# MCP Streamlit Agent

A Streamlit interface for creating and interacting with LLM agents using MCP tools. Build intelligent assistants with Claude, GPT, or Gemini models and visualize their reasoning in real-time.

## Features

- 🤖 Create ReAct agents using Claude, GPT-4o, or Gemini models
- 🛠️ Easily configure MCP tools through a user-friendly interface
- 📊 Real-time visualization of agent thinking process and tool usage
- 🔄 Asynchronous processing for responsive performance
- 🧩 Modular code structure for easier maintenance and extensions

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/sarvottam-bhagat/mcp-streamlit-agent.git
   cd mcp-streamlit-agent
   ```

2. Set up the environment (using Make):
   ```bash
   make setup
   ```

   Or manually:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Edit the `.env` file to add your API keys:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   OPENWEATHER_API_KEY=your_openweather_api_key_here
   ```

   To get an OpenWeatherMap API key:
   - Sign up at [OpenWeatherMap](https://openweathermap.org/api)
   - Get your free API key
   - Add it to the `.env` file

## Usage

1. Start the Streamlit app (with Make):
   ```bash
   streamlit run app.py
   ```

   Or using the run script:
   ```bash
   ./run.sh
   ```

2. Access the web interface at `http://localhost:8501`

3. In the interface:
   - Configure MCP tools in the sidebar
   - Choose from Claude, GPT, or Gemini models
   - Send messages to your agent and see responses in real-time
   - View detailed tool usage information in expandable sections

## Using MCP Tools

The application supports adding various MCP tools through the UI:

1. Click "Add MCP Tools" in the sidebar
2. Add tool configurations in JSON format:
   ```json
   {
     "tool_name": {
       "command": "command_to_execute",
       "args": ["arg1", "arg2"],
       "transport": "stdio"
     }
   }
   ```
3. Click "Add Tool" button
4. Changes will be applied automatically

The application comes with default tools configured in `configs/default.json`.

## Project Structure

```
mcp-streamlit-agent/
├── app.py                 # Main Streamlit application
├── utils/                 # Utility modules
│   ├── callbacks.py       # Callback handlers for streaming responses
│   ├── event_loop.py      # Async event loop management
│   └── ui.py              # UI-related utility functions
├── configs/               # Configuration files
│   └── default.json       # Default MCP tool configurations
├── adapters/              # MCP tool adapters
│   └── weather_server.py  # Example weather tool adapter
└── README.md              # Project documentation
```

## How It Works

1. **MCP Tool Integration**: Machine Control Protocol (MCP) allows the agent to interact with various tools using a standardized interface.

2. **Streaming Responses**: Agent responses and tool usage are streamed in real-time to provide immediate feedback.

3. **Model Selection**: Choose from Claude, GPT, or Gemini models to power your agent.

## Dependencies

- Streamlit
- LangChain & LangGraph
- Google Generative AI (Gemini)
- OpenAI (GPT)
- Anthropic (Claude)
- Python dotenv
- MCP (Machine Control Protocol)
- Requests (for API calls)
- OpenWeatherMap API

## License

[MIT License](LICENSE)

---