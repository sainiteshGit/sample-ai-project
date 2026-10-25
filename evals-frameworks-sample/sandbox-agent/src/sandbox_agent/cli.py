"""Command-line entry point: sandbox-agent "task" [--agent NAME] [--json]."""

from __future__ import annotations

import argparse
import json
import sys

from sandbox_agent.agent import Agent
from sandbox_agent.agents import get_agent_spec
from sandbox_agent.config import ConfigError
from sandbox_agent.llm import azure_openai_chat_model_from_env
from sandbox_agent.sandbox import AzureSandboxProvider, SandboxSettings
from sandbox_agent.tools import select_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sandbox-agent", description=__doc__)
    parser.add_argument("task", help="Instruction for the agent to carry out in a sandbox.")
    parser.add_argument("--agent", default="default", help="Named agent spec (default: default).")
    parser.add_argument(
        "--file",
        dest="file",
        help="Local file uploaded to /workspace/data.csv in the sandbox before the run.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full run trace as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        spec = get_agent_spec(args.agent)
        agent = Agent(
            spec=spec,
            model=azure_openai_chat_model_from_env(),
            provider=AzureSandboxProvider(SandboxSettings.from_env()),
            tools=select_tools(spec.tools),
        )
        attachments = None
        if args.file:
            with open(args.file, "rb") as fh:
                attachments = {"/workspace/data.csv": fh.read()}
        result = agent.run(args.task, attachments=attachments)
    except (ConfigError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.final_answer or f"(no final answer; stop_reason={result.stop_reason})")
    return 0 if result.stop_reason == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
