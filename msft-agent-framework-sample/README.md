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

### 3. Travel Assistant with Shared State (`travel_assistant_shared_state.py`)
Demonstrates advanced workflow patterns using shared state:
- **Shared State Management**: Multiple executors collaborate through a common memory space
- **Multi-Step Information Collection**: Destination, dates, and preferences collected separately
- **Scalable Architecture**: New executors added without modifying existing ones (hotel recommender)
- **Clean Data Flow**: Lightweight messages with centralized state management
- **Real-World Application**: Complete travel planning with flights, hotels, and itineraries

### 4. Checkpoint-Based Document Processing (`simple_checkpoint.py`)
Demonstrates fault-tolerant workflows with automatic checkpointing:
- **Automatic Checkpoints**: State saved automatically after each workflow stage
- **Failure Recovery**: Resume from last successful checkpoint without re-running completed work
- **Cost Optimization**: Avoid redundant API calls by skipping completed stages
- **3-Stage Pipeline**: Document Classifier → Summarizer → Risk Assessor
- **Real-World Resilience**: Simulated network failures with automatic recovery

## Workflow Overview

The morning routine workflow consists of 5 stages:

1. **Weather Analyst**: Analyzes weather conditions and provides clothing/activity recommendations
2. **Schedule Analyzer**: Optimizes timing based on work commitments and preferences
3. **Routine Planner**: Creates detailed step-by-step morning routine activities
4. **Timeline Optimizer**: Optimizes for efficiency and identifies parallel activities
5. **Routine Finalizer**: Packages and validates the complete morning routine

The checkpoint-based document processing workflow consists of 3 stages:

1. **Document Classifier**: Classifies documents as CONTRACT, INVOICE, or REPORT
2. **Summarizer**: Generates concise 2-sentence summaries (simulates failure on first run)
3. **Risk Assessor**: Evaluates risk level from 0.0 (low) to 1.0 (high)

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

**Run Travel Assistant with Shared State Demo:**
```bash
python travel_assistant_shared_state.py
```

**Run Checkpoint-Based Document Processing Demo:**
```bash
python simple_checkpoint.py
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

### Travel Assistant with Shared State Demo (`travel_assistant_shared_state.py`)
The shared state demo will show:
1. **Destination collection** from user input (e.g., Paris)
2. **Date collection** with shared state reading (Dec 20-30, 2025)
3. **Preference collection** accessing all previous data from shared state
4. **Flight recommendations** generated from complete shared state
5. **Hotel recommendations** added without modifying existing executors
6. **Complete travel itinerary** with day-by-day plans

### Checkpoint-Based Document Processing Demo (`simple_checkpoint.py`)
The checkpoint demo will show:
1. **RUN 1**: Classifier completes successfully, Summarizer fails (simulated network error)
2. **Checkpoint saved** automatically after Classifier stage
3. **RUN 2**: Resume from checkpoint, Classifier stage is SKIPPED
4. **Summarizer succeeds** on retry without re-running Classifier
5. **Risk Assessor completes** the pipeline with final risk score
6. **Cost savings** demonstrated by skipping already-completed work

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

### Travel Assistant with Shared State
- **Shared State Pattern**: Key-value based state management accessible across all executors
- **Modular Architecture**: New executors added without modifying existing pipeline
- **Multi-Stage Collection**: Information gathered at different times and stored centrally
- **Scalability**: Easy to add new recommendation engines (flights → hotels → activities)
- **Clean Message Flow**: Messages stay lightweight while shared state contains full context
- **Real-World Application**: Complete travel planning workflow from destination to itinerary

### Checkpoint-Based Document Processing
- **Automatic State Persistence**: Checkpoints created after each superstep without manual intervention
- **Resume Capability**: Workflow resumes from last successful checkpoint after failures
- **Stage Skipping**: Completed stages are never re-executed, saving time and API costs
- **File-Based Storage**: Checkpoints persisted to disk for cross-session recovery
- **Workflow Validation**: Ensures workflow graph consistency when resuming
- **Production-Ready Pattern**: Fault tolerance for long-running or expensive AI pipelines

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

### Travel Assistant with Shared State Demo
```
Microsoft Agent Framework - Travel Assistant with Shared State

TRAVEL ASSISTANT WITH SHARED STATE
This example shows how shared state enables:
  - Multiple executors to access the same data
  - Information collection at different times
  - Clean, lightweight message passing
  - Easy addition of new executors (hotel recommender)

Setting up Travel Assistant Workflow with Shared State...
Travel Assistant Workflow created successfully

Step 1 - User Input: I want to go to Paris for a romantic getaway
Destination collected: Paris
Collecting travel dates based on previous stage...
Reading from shared state - Destination: Paris
Travel dates collected: {'start': '2025-12-20', 'end': '2025-12-30'}
Collecting travel preferences based on previous stage...
Reading from shared state:
  - Destination: Paris
  - Travel Dates: {'start': '2025-12-20', 'end': '2025-12-30'}
Travel preferences collected: {'budget level': 'Budget-friendly', 'travel style': 'Adventure travel', 'accommodation type': 'Unique experiences'}
Shared state now complete with all user information

Recommending flights based on shared state data...
Flight recommendations added to shared state
Recommending hotels based on shared state data...
Hotel recommendations added to shared state
Building complete travel itinerary...
Travel itinerary completed

COMPLETE TRAVEL PLAN GENERATED
Destination: Paris
Travel Dates: {'start': '2025-12-20', 'end': '2025-12-30'}
Preferences: {'budget level': 'Budget-friendly', 'travel style': 'Adventure travel', 'accommodation type': 'Unique experiences'}

Flight Recommendations:
  - Air France: Direct flights, $750-$900 round trip
  - Norwegian Air: Budget option, $650-$800 round trip
  - Lufthansa: with connections, $700-$850 round trip

Hotel Recommendations:
  - Generator Paris: Modern hostel, $40-60/night, 10th Arrondissement
  - Le Village Montmartre: Boutique hotel, $80-120/night, Montmartre
  - Generator Paris La Bellevilloise: Budget hostel, $35-50/night, Belleville

Full Itinerary:
  Day 1 (Dec 20): Arrival at CDG Airport, hotel check-in, evening stroll
  Day 2 (Dec 21): Louvre Museum, Seine River walk, dinner in Latin Quarter
  Day 3 (Dec 22): Eiffel Tower, Trocadéro viewpoint, street food tour
  ... 7 more days of curated activities and attractions
```

### Checkpoint-Based Document Processing Demo
```
CHECKPOINT DEMO - Document Processing Workflow
======================================================================

RUN 1: Initial Execution
----------------------------------------------------------------------
[Classifier] Processing doc-001...
  ✅ CONTRACT
[Summarizer] Processing doc-001...

💥 FAILED: Network timeout (simulated)
💾 Checkpoints saved: 1

RUN 2: Resume from Checkpoint
----------------------------------------------------------------------
[Summarizer] Processing doc-001...
  ✅ Summary generated
[Risk Assessor] Processing doc-001...
  ✅ Risk: 0.30 (LOW)

✅ SUCCESS!
   Classification: CONTRACT
   Risk: 0.30 (LOW)

======================================================================
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
- **Fault Tolerance**: Checkpoint-based recovery for long-running workflows
- **Cost Optimization**: Avoiding redundant work through intelligent state management