"""Chat model boundary. Agents depend on the ChatModel protocol, not on a vendor SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from dotenv import load_dotenv

from sandbox_agent.config import ConfigError


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the model produced it


@dataclass(frozen=True)
class ModelReply:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply: ...


class AzureOpenAIChatModel:
    def __init__(self, client: Any, deployment: str):
        self._client = client
        self._deployment = deployment

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        kwargs: dict[str, Any] = {"model": self._deployment, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        calls = [
            ToolCallRequest(id=c.id, name=c.function.name, arguments=c.function.arguments)
            for c in (message.tool_calls or [])
        ]
        return ModelReply(content=message.content, tool_calls=calls)


def azure_openai_chat_model_from_env() -> AzureOpenAIChatModel:
    from openai import AzureOpenAI

    load_dotenv()
    client = AzureOpenAI(
        azure_endpoint=_required("AZURE_OPENAI_ENDPOINT"),
        api_key=_required("AZURE_OPENAI_API_KEY"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        timeout=90,
        max_retries=0,
    )
    return AzureOpenAIChatModel(client, deployment=_required("AZURE_OPENAI_DEPLOYMENT"))


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing environment variable {name} (see .env.example)")
    return value
