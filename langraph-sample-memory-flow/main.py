from typing import TypedDict, List
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import AzureChatOpenAI

# Load environment variables
load_dotenv()

# Azure OpenAI setup
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    temperature=0
)

# Shared short-term memory schema
class SupportState(TypedDict, total=False):
    transcript: str
    issue_type: str
    urgency: str
    solution_steps: List[str]
    resolution_script: str
    last_updated_iso: str

def stamp(state: SupportState):
    state["last_updated_iso"] = datetime.now(timezone.utc).isoformat()

# Agent 1: Classifier
def classifier_agent(state: SupportState) -> SupportState:
    prompt = f"Classify the issue type and urgency from this transcript:\n{state['transcript']}"
    resp = llm.invoke(prompt)
    text = resp.content.lower()
    state["issue_type"] = "billing" if "billing" in text else "general"
    state["urgency"] = "high" if "high" in text else "normal"
    stamp(state)
    print("\n[After Classifier]", state)
    return state

# Agent 2: Knowledge Finder
def knowledge_agent(state: SupportState) -> SupportState:
    prompt = f"Give 3 steps to solve a {state['issue_type']} issue."
    resp = llm.invoke(prompt)
    steps = [s.strip() for s in resp.content.split("\n") if s.strip()]
    state["solution_steps"] = steps
    stamp(state)
    print("\n[After Knowledge Finder]", state)
    return state

# Agent 3: Resolution Writer
def resolution_agent(state: SupportState) -> SupportState:
    prompt = (
        f"Write a resolution script for a {state['issue_type']} issue "
        f"with urgency {state['urgency']}, using these steps: {state['solution_steps']}"
    )
    resp = llm.invoke(prompt)
    state["resolution_script"] = resp.content
    stamp(state)
    print("\n[After Resolution Writer]", state)
    return state

# Build LangGraph
graph = StateGraph(SupportState)
graph.add_node("classifier", classifier_agent)
graph.add_node("knowledge", knowledge_agent)
graph.add_node("resolution", resolution_agent)

graph.add_edge(START, "classifier")
graph.add_edge("classifier", "knowledge")
graph.add_edge("knowledge", "resolution")
graph.add_edge("resolution", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# Run
if __name__ == "__main__":
    initial_state: SupportState = {
        "transcript": "Hi, I was double charged on my invoice. This is urgent."
    }
    result = app.invoke(initial_state, config={"configurable": {"thread_id": "short-term-demo"}})

    print("\n=== Final Shared Memory ===")
    for k, v in result.items():
        print(f"{k}: {v}")
