"""
WorkflowViz Demo - Visualize AI Workflows
Blog: "Seeing How AI Thinks: Visualizing Agent Workflows"
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from agent_framework import WorkflowBuilder, WorkflowViz, Executor, WorkflowContext, handler


@dataclass
class Task:
    id: str
    content: str
    research: Optional[str] = None
    marketing: Optional[str] = None
    legal: Optional[str] = None
    is_spam: bool = False
    result: Optional[str] = None


# Fan-out/Fan-in Pattern Executors
class DispatcherExecutor(Executor):
    def __init__(self):
        super().__init__(id="dispatcher")
    
    @handler
    async def dispatch(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        await ctx.send_message(task)


class ResearcherExecutor(Executor):
    def __init__(self):
        super().__init__(id="researcher")
    
    @handler
    async def analyze(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.research = "Tech feasibility confirmed"
        await ctx.send_message(task)


class MarketerExecutor(Executor):
    def __init__(self):
        super().__init__(id="marketer")
    
    @handler
    async def analyze(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.marketing = "High market demand"
        await ctx.send_message(task)


class LegalExecutor(Executor):
    def __init__(self):
        super().__init__(id="legal")
    
    @handler
    async def analyze(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.legal = "Compliant with regulations"
        await ctx.send_message(task)


class AggregatorExecutor(Executor):
    def __init__(self):
        super().__init__(id="aggregator")
    
    @handler
    async def combine(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        if task.research and task.marketing and task.legal:
            task.result = f"Research: {task.research}\nMarketing: {task.marketing}\nLegal: {task.legal}"
        await ctx.send_message(task)


def create_fanout_workflow():
    dispatcher = DispatcherExecutor()
    researcher = ResearcherExecutor()
    marketer = MarketerExecutor()
    legal = LegalExecutor()
    aggregator = AggregatorExecutor()
    
    return (
        WorkflowBuilder()
        .set_start_executor(dispatcher)
        .add_edge(dispatcher, researcher)
        .add_edge(dispatcher, marketer)
        .add_edge(dispatcher, legal)
        .add_edge(researcher, aggregator)
        .add_edge(marketer, aggregator)
        .add_edge(legal, aggregator)
        .build()
    )


# Conditional Routing Executors
class ClassifierExecutor(Executor):
    def __init__(self):
        super().__init__(id="classifier")
    
    @handler
    async def classify(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.is_spam = "spam" in task.content.lower()
        await ctx.send_message(task)


class SpamHandlerExecutor(Executor):
    def __init__(self):
        super().__init__(id="spam_handler")
    
    @handler
    async def handle(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.result = "QUARANTINED"
        await ctx.send_message(task)


class NormalProcessorExecutor(Executor):
    def __init__(self):
        super().__init__(id="normal_processor")
    
    @handler
    async def process(self, task: Task, ctx: WorkflowContext[Task]) -> None:
        task.result = "PROCESSED"
        await ctx.send_message(task)


def create_conditional_workflow():
    classifier = ClassifierExecutor()
    spam_handler = SpamHandlerExecutor()
    normal_processor = NormalProcessorExecutor()
    
    return (
        WorkflowBuilder()
        .set_start_executor(classifier)
        .add_edge(classifier, spam_handler, condition=lambda t: t.is_spam)
        .add_edge(classifier, normal_processor, condition=lambda t: not t.is_spam)
        .build()
    )


def save_visualization(workflow, name):
    viz = WorkflowViz(workflow)
    
    # Save Mermaid
    mermaid = viz.to_mermaid()
    md_file = f"{name}.md"
    with open(md_file, "w") as f:
        f.write(f"# {name.replace('_', ' ').title()}\n\n```mermaid\n{mermaid}\n```\n")
    print(f"✅ {md_file}")
    
    # Save PNG
    try:
        png_file = viz.save_png(f"{name}.png")
        print(f"✅ {png_file}")
    except Exception:
        print(f"⚠️  {name}.png (install: pip install agent-framework[viz] && brew install graphviz)")


async def main():
    print("\nWorkflowViz Demo\n" + "="*50)
    
    # Demo 1: Fan-out/Fan-in
    print("\n1. Fan-out/Fan-in (Parallel Processing)")
    workflow1 = create_fanout_workflow()
    save_visualization(workflow1, "fanout_fanin")
    
    task = Task(id="T1", content="Launch AI chatbot")
    async for _ in workflow1.run_stream(task):
        pass
    print(f"Result: {task.result}\n")
    
    # Demo 2: Conditional Routing
    print("2. Conditional Routing (Smart Decisions)")
    workflow2 = create_conditional_workflow()
    save_visualization(workflow2, "conditional_routing")
    
    for content in ["Meeting at 3pm", "SPAM: Free money!"]:
        task = Task(id="M1", content=content)
        async for _ in workflow2.run_stream(task):
            pass
        print(f"{content[:20]:20s} → {task.result}")
    
    print("\n" + "="*50)
    print("✅ Done! Check the .md and .png files above.\n")


if __name__ == "__main__":
    asyncio.run(main())
