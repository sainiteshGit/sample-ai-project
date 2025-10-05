# Microsoft Agent Framework: Chat History Management Demo

This demo explores two different approaches to managing conversation history in the Microsoft Agent Framework using Azure OpenAI.

## What This Demo Shows

- **🔵 Thread-Based Approach**: Automatic conversation management using `AgentThread`
- **🟢 Custom Manual Approach**: Complete control over conversation storage and retrieval
- **🔍 Storage Analysis**: Real-time inspection of where and how conversations are stored

## Prerequisites

- Python 3.8 or higher
- Azure OpenAI resource with a deployed model
- Azure OpenAI API key

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

### Step 5: Run the Demo
```bash
python main.py
```

## Expected Output

The demo will show:
1. **Thread-based conversation** with automatic context management
2. **Storage analysis** showing actual storage location (in-memory vs service)
3. **Custom history conversation** with manual context management
4. **Detailed comparison** of both approaches

## Key Findings

- The "service" approach actually uses **in-memory storage** with process-shared threads
- True Azure service storage requires additional configuration
- Custom approach gives complete control but requires manual history management

## Troubleshooting

**Import Error**: Make sure you're in the activated virtual environment
**API Key Error**: Verify your Azure OpenAI credentials are correct
**API Version Error**: Ensure you're using a supported API version (2024-10-01-preview or later)
