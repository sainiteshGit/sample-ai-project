"""
Checkpoint Demo - Document Processing Workflow
Based on Official MS Learn Documentation

Workflow: Document Classifier → Summarizer → Risk Assessor
- Stage 1: Classify document type (CONTRACT, INVOICE, REPORT)
- Stage 2: Generate summary (will fail first time - simulated)
- Stage 3: Assess risk level (0.0 to 1.0)

Demonstrates:
- Checkpoints saved automatically after each stage
- Resume from checkpoint to skip completed work
- Fault tolerance and progress recovery
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework import FileCheckpointStorage, WorkflowOutputEvent
from agent_framework.azure import AzureOpenAIResponsesClient


@dataclass
class Document:
    """Document to process through the workflow"""
    id: str
    content: str
    
    # Results from each stage
    classification: Optional[str] = None
    summary: Optional[str] = None
    risk_score: Optional[float] = None


class DocumentClassifierExecutor(Executor):
    """Stage 1: Classify document type"""

    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="classifier")

    @handler
    async def classify(self, doc: Document, ctx: WorkflowContext[Document]) -> None:
        print(f"[Classifier] Processing {doc.id}...")
        
        agent = self.responses_client.create_agent(
            name="DocumentClassifier",
            instructions="Classify the document as: CONTRACT, INVOICE, or REPORT. Return only the classification."
        )
        
        response = await agent.run(f"Classify this document:\n\n{doc.content}")
        
        doc.classification = response.text.strip().upper()
        print(f" {doc.classification}")
        
        await ctx.send_message(doc)


class SummarizerExecutor(Executor):
    """Stage 2: Generate summary (will fail on first run)"""

    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="summarizer")

    @handler
    async def summarize(self, doc: Document, ctx: WorkflowContext[Document]) -> None:
        print(f"[Summarizer] Processing {doc.id}...")
        
        # Simulate failure on first run
        if os.getenv("SIMULATE_FAILURE") == "true":
            os.environ["SIMULATE_FAILURE"] = "false"
            raise Exception("Network timeout (simulated)")
        
        agent = self.responses_client.create_agent(
            name="Summarizer",
            instructions="Create a brief 2-sentence summary of the document."
        )
        
        response = await agent.run(f"Summarize this {doc.classification}:\n\n{doc.content}")
        
        doc.summary = response.text.strip()
        print(f" Summary generated")
        
        await ctx.send_message(doc)


class RiskAssessorExecutor(Executor):
    """Stage 3: Assess risk level"""

    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="risk_assessor")

    @handler
    async def assess_risk(self, doc: Document, ctx: WorkflowContext[Document]) -> None:
        print(f"[Risk Assessor] Processing {doc.id}...")
        
        agent = self.responses_client.create_agent(
            name="RiskAssessor",
            instructions="Rate the risk level from 0.0 (low) to 1.0 (high). Return only a decimal number."
        )
        
        response = await agent.run(
            f"Assess risk for this {doc.classification}:\n"
            f"Summary: {doc.summary}\n\n"
            f"Risk score (0.0-1.0):"
        )
        
        try:
            doc.risk_score = float(response.text.strip())
        except ValueError:
            doc.risk_score = 0.5
        
        risk_level = "HIGH" if doc.risk_score > 0.7 else "MEDIUM" if doc.risk_score > 0.4 else "LOW"
        print(f"  Risk: {doc.risk_score:.2f} ({risk_level})")
        
        # Output final result
        await ctx.yield_output({
            "document_id": doc.id,
            "classification": doc.classification,
            "summary": doc.summary,
            "risk_score": doc.risk_score,
            "risk_level": risk_level,
            "status": "SUCCESS"
        })


async def main():
    print("\n" + "="*70)
    print("CHECKPOINT DEMO - Document Processing Workflow")
    print("="*70)

    # Initialize Azure OpenAI client
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError("Azure OpenAI environment variables required")
    
    responses_client = AzureOpenAIResponsesClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )

    # Create checkpoint storage
    checkpoint_storage = FileCheckpointStorage(storage_path="./checkpoints")

    # Create executors
    classifier = DocumentClassifierExecutor(responses_client)
    summarizer = SummarizerExecutor(responses_client)
    risk_assessor = RiskAssessorExecutor(responses_client)

    # Build workflow with checkpointing enabled
    builder = WorkflowBuilder()
    builder.set_start_executor(classifier)
    builder.add_edge(classifier, summarizer)
    builder.add_edge(summarizer, risk_assessor)
    workflow = builder.with_checkpointing(checkpoint_storage).build()

    # ========================================
    # RUN 1: Execute workflow (will fail at Summarizer)
    # ========================================
    print("\nRUN 1: Initial Execution")
    print("-" * 70)
    
    os.environ["SIMULATE_FAILURE"] = "true"
    
    document = Document(
        id="doc-001",
        content="""
        Service Agreement between TechCorp Inc. and GlobalBiz LLC.
        This agreement covers cloud infrastructure services including 24/7 monitoring,
        99.9% uptime guarantee, automated backups, and SOC 2 compliance.
        Contract term: 12 months. Payment: $50,000 annually.
        Renewal terms: Auto-renewal unless terminated with 30 days notice.
        """
    )

    try:
        async for event in workflow.run_stream(document):
            if isinstance(event, WorkflowOutputEvent):
                print(f"\n Result: {event.data}")
    except Exception as e:
        print(f"\n FAILED: {e}")

    # Check checkpoints
    checkpoints = await checkpoint_storage.list_checkpoints()
    print(f"💾 Checkpoints saved: {len(checkpoints)}")

    if not checkpoints:
        print(" No checkpoints saved")
        return

    # ========================================
    # RUN 2: Resume from checkpoint
    # ========================================
    print("\nRUN 2: Resume from Checkpoint")
    print("-" * 70)

    saved_checkpoint = checkpoints[-1]
    
    try:
        async for event in workflow.run_stream_from_checkpoint(saved_checkpoint.checkpoint_id):
            if isinstance(event, WorkflowOutputEvent):
                result = event.data
                print(f"\n SUCCESS!")
                print(f"   Classification: {result['classification']}")
                print(f"   Risk: {result['risk_score']:.2f} ({result['risk_level']})")
    except Exception as e:
        print(f"\n Recovery failed: {e}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
