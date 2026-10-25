"""Tool-calling agents that run every instruction inside an isolated sandbox."""

from sandbox_agent.agent import Agent, AgentSpec, RunResult, ToolCallRecord
from sandbox_agent.sandbox import AzureSandboxProvider, SandboxSpec

__all__ = [
    "Agent",
    "AgentSpec",
    "AzureSandboxProvider",
    "RunResult",
    "SandboxSpec",
    "ToolCallRecord",
]
