# Microsoft Agent Framework: Complete Demo Suite

This repository contains comprehensive examples demonstrating different aspects of the Microsoft Agent Framework with Azure OpenAI. It includes both basic agent usage patterns and advanced multi-agent workflows.

## Demo Examples

### 1. Chat History Management (`main.py`)
Explores two different approaches to managing conversation history:
- **Thread-Based Approach**: Automatic conversation management using `AgentThread`
- **Custom Manual Approach**: Complete control over conversation storage and retrieval
- **Storage Analysis**: Real-time inspection of where and how conversations are stored

### 2. AI Agents Workflow (`morning_routine_workflow.py`)
Demonstrates sophisticated multi-agent workflow orchestration:
- **Multi-Agent Orchestration**: Sequential workflow with 5 specialized AI agents
- **Real-World Application**: Personalized morning routine planning for daily life scenarios
- **Error Handling**: Graceful degradation and status tracking throughout the workflow
- **Event Monitoring**: Real-time workflow progress and completion tracking
- **Data Evolution**: How data structures evolve through multiple processing stages

## Workflow Overview

The morning routine workflow consists of 5 stages:

1. **Weather Analyst**: Analyzes weather conditions and provides clothing/activity recommendations
2. **Schedule Analyzer**: Optimizes timing based on work commitments and preferences
3. **Routine Planner**: Creates detailed step-by-step morning routine activities
4. **Timeline Optimizer**: Optimizes for efficiency and identifies parallel activities
5. **Routine Finalizer**: Packages and validates the complete morning routine

## Prerequisites

- Python 3.8 or higher
- Azure OpenAI resource with a deployed model
- Azure OpenAI API key
- Microsoft Agent Framework package

## Setup Instructions

### Step 1: Create Virtual Environment
```bash
python -m venv .venv
```

### Step 2: Activate Virtual Environment
**On Windows:**
```bash
.venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

**Option A: Using .env file (Recommended)**
Create a `.env` file in the project root:
```bash
AZURE_OPENAI_ENDPOINT=https://YOUR-ENDPOINT.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=YOUR-DEPLOYMENT-NAME
AZURE_OPENAI_API_VERSION=2024-10-01-preview
AZURE_OPENAI_API_KEY=your-api-key-here
```

**Option B: Export environment variables**
```bash
export AZURE_OPENAI_ENDPOINT="https://YOUR-ENDPOINT.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT="YOUR-DEPLOYMENT-NAME"
export AZURE_OPENAI_API_VERSION="2024-10-01-preview"
export AZURE_OPENAI_API_KEY="your-api-key-here"
```

### Step 5: Run the Demos

**Run Chat History Management Demo:**
```bash
python main.py
```

**Run AI Agents Workflow Demo:**
```bash
python morning_routine_workflow.py
```

## Expected Output

### Chat History Management Demo (`main.py`)
The demo will show:
1. **Thread-based conversation** with automatic context management
2. **Storage analysis** showing actual storage location (in-memory vs service)
3. **Custom history conversation** with manual context management
4. **Detailed comparison** of both approaches

### AI Agents Workflow Demo (`morning_routine_workflow.py`)
The workflow demo will show:
1. **Workflow architecture** visualization of the 5-stage pipeline
2. **Real-time agent execution** with progress monitoring
3. **Personalized morning routine** with weather, schedule, and activity recommendations
4. **Complete routine package** with 30+ detailed steps and optimized timeline

## Key Features Demonstrated

### Chat History Management
- The "service" approach actually uses **in-memory storage** with process-shared threads
- True Azure service storage requires additional configuration
- Custom approach gives complete control but requires manual history management

### AI Agents Workflow
- **Sequential Processing**: Each agent builds on the previous one's output
- **Specialized AI Agents**: Weather analysis, schedule optimization, routine planning, timeline optimization
- **Error Resilience**: Graceful handling of AI call failures with status tracking
- **Real-time Monitoring**: Streaming workflow events for observability
- **Data Transformation**: PersonProfile evolves into comprehensive MorningPlan through 5 stages

## Sample Output Examples

### Chat History Management Demo
```
SERVICE Chat History Storage
Thread initialized: True
Service thread ID: <thread_id>

User: Hi! I'm Alice and I work in marketing.
Agent: Hello Alice! Nice to meet you. I see you work in marketing...

User: What's my name and job?
Agent: Your name is Alice and you work in marketing...

ACTUAL STORAGE ANALYSIS:
   - Thread has local messages: True
   - Thread has service ID: True
   - Storage type: IN-MEMORY
```

### AI Agents Workflow Demo
```
AI AGENT WORKFLOW ARCHITECTURE
Morning Routine AI Agent Pipeline:
  Person Profile → [Weather Analyst] → [Schedule Analyzer] → [Routine Planner] → [Timeline Optimizer] → [Routine Finalizer] → Personalized Morning Routine

Starting AI agent morning routine workflow...
Analyzing weather for Sarah Chen in Seattle, WA...
Weather analysis completed
Analyzing schedule and commitments for Sarah Chen...
Schedule analysis completed
Creating detailed routine plan for Sarah Chen...
Routine planning completed
Optimizing timeline for Sarah Chen...
Timeline optimization completed
Finalizing morning routine for Sarah Chen...

AI MORNING ROUTINE COMPLETE
Personalized routine created for Sarah Chen
Location: Seattle, WA
Work starts: 8:30 AM

Weather Insights: Current conditions: Overcast with light rain expected...
Schedule Insights: Optimal wake-up time: 6:30 AM...
Morning Routine Steps:
   1. 6:30 AM - Wake up and hydrate
   2. 6:35 AM - Morning stretch/yoga (15 min)
   3. 6:50 AM - Shower and personal care (20 min)
   ... and 33 more steps
```

## Troubleshooting

**Import Error**: Make sure you're in the activated virtual environment
**API Key Error**: Verify your Azure OpenAI credentials are correct
**API Version Error**: Ensure you're using a supported API version (2024-10-01-preview or later)
**Workflow Execution Error**: Check that all required environment variables are set correctly

## Learning Outcomes

This demo suite is perfect for early career developers to learn:
- **Basic Agent Usage**: Simple conversation patterns and history management
- **Advanced Workflows**: Multi-agent orchestration and complex data processing
- **Error Handling**: Professional patterns for resilient AI applications
- **Real-time Monitoring**: Observability patterns for production systems
- **Resource Management**: Efficient use of Azure OpenAI resources across multiple agents
