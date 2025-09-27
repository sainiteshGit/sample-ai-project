# LangGraph Sample Memory Flow

This project demonstrates a multi-agent workflow using LangGraph with shared memory for customer support ticket classification and resolution. The system uses three specialized agents working together to process customer support transcripts.

## Overview

The application implements a customer support automation system with three agents:

1. **Classifier Agent**: Analyzes customer transcripts to determine issue type and urgency
2. **Knowledge Finder Agent**: Provides solution steps based on the classified issue
3. **Resolution Writer Agent**: Creates a detailed resolution script

Each agent updates shared memory state and timestamps their contributions, creating an audit trail of the workflow.

## Architecture

- **Framework**: LangGraph for workflow orchestration
- **LLM**: Azure OpenAI (GPT-4o-mini)
- **Memory**: In-memory checkpointing with MemorySaver
- **State Management**: TypedDict for shared state between agents

## Prerequisites

- Python 3.8+
- Azure OpenAI account and API key
- Virtual environment (recommended)

## Setup

1. **Clone the repository and navigate to the project directory**:
   ```bash
   cd langraph-sample-memory-flow
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the project root with your Azure OpenAI credentials:
   ```env
   AZURE_OPENAI_ENDPOINT="https://your-resource-name.openai.azure.com/"
   AZURE_OPENAI_KEY="your-api-key-here"
   AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini"
   AZURE_OPENAI_API_VERSION="2025-01-01-preview"
   ```

## Usage

Run the application:

```bash
python main.py
```

The system will process a sample customer support transcript and output the workflow progression through each agent.

## Example Output

```
[After Classifier] {'transcript': 'Hi, I was double charged on my invoice. This is urgent.', 'issue_type': 'billing', 'urgency': 'high', 'last_updated_iso': '2025-09-27T21:46:02.343425+00:00'}

[After Knowledge Finder] {...}

[After Resolution Writer] {...}

=== Final Shared Memory ===
transcript: Hi, I was double charged on my invoice. This is urgent.
issue_type: billing
urgency: high
solution_steps: [...]
resolution_script: [...]
last_updated_iso: 2025-09-27T21:46:02.343425+00:00
```

## State Schema

The shared state includes:

- `transcript`: Original customer message
- `issue_type`: Classified issue category (billing, general, etc.)
- `urgency`: Priority level (high, normal)
- `solution_steps`: List of recommended solution steps
- `resolution_script`: Final resolution script for the agent
- `last_updated_iso`: ISO timestamp of last update

## Customization

To modify the workflow:

1. **Add new agents**: Create new functions and add them to the graph
2. **Modify classification logic**: Update the `classifier_agent` function
3. **Change LLM model**: Update the Azure deployment name in `.env`
4. **Extend state schema**: Add fields to the `SupportState` TypedDict

## Dependencies

- `langgraph`: Workflow orchestration
- `langchain-openai`: Azure OpenAI integration
- `python-dotenv`: Environment variable management

