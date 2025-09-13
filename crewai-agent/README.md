# CrewAI Daily Planner Agent

A personalized daily planning AI agent built with CrewAI and Azure OpenAI that creates customized 10-point daily schedules based on your tasks and priorities.

## 🎯 Features

- **Personalized Planning**: Creates daily schedules tailored to your specific tasks and preferences
- **Intelligent Scheduling**: Balances work, breaks, and meal times with realistic time allocation
- **Priority Management**: Automatically assigns priorities (High/Medium/Low) to your tasks
- **Productivity Tips**: Includes helpful productivity advice in each plan
- **Interactive Interface**: Simple command-line interface for easy daily planning

## 🛠️ Technology Stack

- **CrewAI**: Multi-agent framework for AI collaboration
- **Azure OpenAI**: GPT-4 for intelligent planning and scheduling
- **Python 3.11+**: Core programming language
- **python-dotenv**: Environment variable management

## 📋 Prerequisites

- Python 3.11 or higher
- Azure OpenAI account with GPT-4 deployment
- Basic command line familiarity

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root with your Azure OpenAI credentials:

```env
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

### 3. Run the Application

```bash
python main.py
```

## 📖 Usage

1. **Start the application**: Run `python main.py`
2. **Enter your name**: The agent will personalize your plan
3. **List your tasks**: Enter comma-separated tasks you need to complete
4. **Receive your plan**: Get a customized 10-point daily schedule

### Example Input/Output

**Input:**
```
Name: Alex
Tasks: Review project proposals, Team meeting, Write documentation, Exercise
```

**Output:**
```
📋 ALEX'S DAILY PLAN
================================================
1. 9:00 AM - Review project proposals (High Priority) - 90 minutes
2. 10:30 AM - Coffee break and quick email check - 15 minutes
3. 11:00 AM - Team meeting (High Priority) - 60 minutes
4. 12:00 PM - Lunch break - 45 minutes
5. 1:00 PM - Write documentation (Medium Priority) - 2 hours
6. 3:00 PM - Afternoon break and stretch - 15 minutes
7. 3:30 PM - Continue documentation work - 90 minutes
8. 5:00 PM - Exercise (Low Priority) - 45 minutes
9. 6:00 PM - Dinner and wind down - 60 minutes
10. 💡 Productivity Tip: Use the Pomodoro Technique (25min work + 5min break)
```

## 🏗️ Project Structure

```
crewai-agent/
├── .env                 # Environment variables (create this)
├── .venv/              # Virtual environment
├── main.py             # Main application entry point
├── requirements.txt    # Python dependencies
└── README.md          # Project documentation
```

## 🤖 Agent Details

### Daily Planner AI Agent
- **Role**: Daily Planner AI
- **Goal**: Create personalized daily schedules, set priorities, and provide helpful reminders
- **Expertise**: Time management, productivity optimization, work-life balance
- **Output**: Structured 10-point daily plans with time blocks and priorities

## 🔧 Configuration Options

The application uses the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI service endpoint | Yes |
| `AZURE_OPENAI_KEY` | Your Azure OpenAI API key | Yes |
| `AZURE_OPENAI_DEPLOYMENT` | Name of your GPT-4 deployment | Yes |

## 🚨 Troubleshooting

### Common Issues

1. **ImportError: No module named 'crewai'**
   - Ensure virtual environment is activated
   - Run `pip install -r requirements.txt`

2. **Authentication Error with Azure OpenAI**
   - Verify your `.env` file contains correct credentials
   - Check that your Azure OpenAI deployment is active

3. **Python Version Issues**
   - Ensure Python 3.11+ is installed
   - Use `python3.11 -m venv .venv` for environment creation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request



## References

- [CrewAI](https://github.com/joaomdmoura/crewAI) for the multi-agent framework
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) for AI capabilities
- The open-source community for inspiration and tools

---

**Made with ❤️ and AI**
