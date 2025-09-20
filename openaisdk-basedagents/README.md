# Multi-Agent Daily Planner with OpenAI Agents SDK

A sophisticated multi-agent system that creates personalized daily plans by orchestrating multiple specialized AI agents using the OpenAI Agents SDK and Azure OpenAI.

## 🚀 Features

- **Multi-Agent Architecture**: 4 specialized agents working together
- **Azure OpenAI Integration**: Enterprise-grade AI capabilities
- **Function Tools**: Structured agent capabilities with `@function_tool` decorators
- **Sequential Orchestration**: Coordinated execution with data flow between agents
- **Modular Design**: Easy to extend with additional agents and capabilities

## 🏗️ Architecture

The application follows a multi-agent orchestration pattern:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Schedule Agent │    │   Meal Agent    │    │  Health Agent   │
│                 │    │                 │    │                 │
│ Calendar Tool   │    │ Meal Suggest    │    │ Health Check    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────┐
                    │ Planner Agent   │
                    │                 │
                    │ Synthesize Tool │
                    └─────────────────┘
                                 │
                                 ▼
                        📋 Final Daily Plan
```

## 🛠️ Agent Responsibilities

| Agent | Purpose | Tool Function |
|-------|---------|---------------|
| **ScheduleAgent** | Calendar management | `get_calendar_summary()` |
| **MealAgent** | Nutrition planning | `suggest_meal(fridge_items)` |
| **HealthAgent** | Wellness recommendations | `health_check(sleep_hours)` |
| **PlannerAgent** | Plan orchestration | `synthesize_plan(calendar, meal, health)` |

## 📋 Prerequisites

- Python 3.11+ 
- Azure OpenAI account and deployment
- OpenAI Agents SDK

## 🔧 Setup

### 1. Clone and Navigate
```bash
cd openaisdk-basedagents
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:

```env
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_KEY="your-api-key-here"
AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini"
AZURE_OPENAI_API_VERSION="2023-05-15"
```

## 🚀 Usage

### Run the Application
```bash
python main.py
```

### Expected Output
```
🧠 Final Daily Plan:
Here's your plan:
- Calendar: You have 2 meetings today: 10 AM sync and 2 PM design review.
- Meal: Based on your fridge items (eggs, spinach, oats), I suggest a spinach omelette and oats.
- Health: You slept 6.5 hours. Drink water and stretch for 5 minutes.
```

## 📁 Project Structure

```
openaisdk-basedagents/
├── .env                 # Environment variables (create this)
├── .venv/              # Virtual environment
├── main.py             # Main application
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── BLOG.md            # Detailed technical blog post
```

## 🧩 Key Code Components

### Environment Setup
```python
# Load environment variables and disable tracing
load_dotenv()
set_tracing_disabled(True)

# Configure Azure OpenAI client
openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT")
)
```

### Function Tools
```python
@function_tool
def get_calendar_summary() -> str:
    return "You have 2 meetings today: 10 AM sync and 2 PM design review."

@function_tool
def suggest_meal(fridge_items: str) -> str:
    return f"Based on your fridge items ({fridge_items}), I suggest a spinach omelette and oats."
```

### Agent Creation
```python
schedule_agent = Agent(
    name="ScheduleAgent",
    instructions="Summarize today's calendar events.",
    tools=[get_calendar_summary],
    model=model
)
```

## 🔄 Execution Flow

1. **Environment Setup**: Load Azure OpenAI configuration
2. **Agent Creation**: Initialize 4 specialized agents with tools
3. **Sequential Execution**: Run agents in order collecting outputs
4. **Plan Synthesis**: Combine all outputs into final plan
5. **Output Display**: Present unified daily plan to user

## Security Features

- **Environment Variables**: Sensitive credentials stored in `.env` file

## 🔧 Customization

### Adding New Agents
1. Create a new function tool:
```python
@function_tool
def your_new_tool(param: str) -> str:
    return f"Your logic here: {param}"
```

2. Create the agent:
```python
your_agent = Agent(
    name="YourAgent",
    instructions="Your agent instructions",
    tools=[your_new_tool],
    model=model
)
```

3. Add to execution flow and planner synthesis

### Modifying Existing Tools
Edit the function tool implementations in `main.py` to change agent behaviors.

## 📚 Dependencies

- `openai-agents`: OpenAI Agents SDK
- `openai`: OpenAI Python library with Azure support
- `python-dotenv`: Environment variable management

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **API Key Errors**: Verify `.env` file configuration
3. **Model Not Found**: Check Azure OpenAI deployment name
4. **Tracing Errors**: Ensure `set_tracing_disabled(True)` is called

### Debug Mode
Add debug prints to see configuration:
```python
print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
print(f"Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT')}")
```

## 📖 Learn More

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Azure OpenAI Service Documentation](https://docs.microsoft.com/azure/cognitive-services/openai/)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request


---

*Built with ❤️ using OpenAI Agents SDK and Azure OpenAI*
