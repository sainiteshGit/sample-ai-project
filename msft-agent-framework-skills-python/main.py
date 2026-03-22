"""
Microsoft Agent Framework - Python Script Execution Skills Demo

Demonstrates:
1. File-based skills with SkillsProvider (loading from disk)
2. Code-defined skills with @skill.script and @skill.resource decorators
3. Custom script_runner for executing file-based scripts
4. require_script_approval flow
5. Using skills as context_providers with an Azure OpenAI agent
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentSession,
    Skill,
    SkillResource,
    SkillScript,
    SkillsProvider,
)
from agent_framework.azure import AzureOpenAIResponsesClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SKILLS_DIR = Path(__file__).parent / "skills"


# ---------------------------------------------------------------------------
# Script runner: executes file-based Python scripts from skill directories
# ---------------------------------------------------------------------------

def run_skill_script(skill: Skill, script: SkillScript, args: dict[str, Any] | None = None) -> str:
    """Custom script runner that executes Python scripts in a subprocess."""
    if script.path is None:
        return json.dumps({"error": "Script has no file path"})

    # Resolve relative to skill path
    script_path = Path(script.path)
    if not script_path.is_absolute() and skill.path:
        script_path = Path(skill.path).parent / script_path

    if not script_path.exists():
        return json.dumps({"error": f"Script not found: {script_path}"})

    cmd = [sys.executable, str(script_path)]
    if args:
        for key, value in args.items():
            cmd.extend([f"--{key}", str(value)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(script_path.parent),
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr.strip() or f"Exit code {result.returncode}"})
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Script timed out after 30 seconds"})


# ---------------------------------------------------------------------------
# Code-defined skill: text-analyzer (no files on disk)
# ---------------------------------------------------------------------------

def create_text_analyzer_skill() -> Skill:
    """Create a code-defined skill for text analysis with @skill.script and @skill.resource."""
    text_skill = Skill(
        name="text-analyzer",
        description="Analyzes text content - word count, readability, and sentiment",
        content=(
            "Use this skill to analyze text. Available scripts:\n"
            "- word_count: Count words, sentences, and characters\n"
            "- readability: Estimate reading level\n"
        ),
    )

    @text_skill.script(name="word_count", description="Count words, sentences, and characters in text")
    def word_count(text: str = "") -> str:
        words = text.split()
        sentences = text.count(".") + text.count("!") + text.count("?")
        return json.dumps({
            "characters": len(text),
            "words": len(words),
            "sentences": max(sentences, 1),
            "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 1),
        })

    @text_skill.script(name="readability", description="Estimate reading level of text")
    def readability(text: str = "") -> str:
        words = text.split()
        sentences = max(text.count(".") + text.count("!") + text.count("?"), 1)
        syllables = sum(max(1, sum(1 for c in w.lower() if c in "aeiou")) for w in words)
        word_count = max(len(words), 1)
        # Flesch-Kincaid Grade Level approximation
        grade = 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59
        return json.dumps({
            "grade_level": round(max(grade, 1), 1),
            "word_count": word_count,
            "avg_sentence_length": round(word_count / sentences, 1),
        })

    @text_skill.resource(name="supported_formats", description="List of supported text formats")
    def supported_formats() -> str:
        return json.dumps(["plain text", "markdown", "csv", "json"])

    return text_skill


# ---------------------------------------------------------------------------
# Demo 1: File-based skills with script execution
# ---------------------------------------------------------------------------

async def demo_file_based_skills(client: AzureOpenAIResponsesClient) -> None:
    print("=" * 70)
    print("DEMO 1: File-Based Skills with Script Execution")
    print("=" * 70)

    skills_provider = SkillsProvider(
        skill_paths=[str(SKILLS_DIR / "data-validator"), str(SKILLS_DIR / "unit-converter")],
        script_runner=run_skill_script,
    )

    agent = client.as_agent(
        name="DataAssistant",
        instructions=(
            "You are a data validation and unit conversion assistant. "
            "Use your available skills to help users validate data files "
            "and convert between units of measurement."
        ),
        context_providers=[skills_provider],
    )

    session = AgentSession()

    prompts = [
        "What skills do you have available? List them briefly.",
        "Convert 100 kilometers to miles.",
        "Convert 72 fahrenheit to celsius.",
    ]

    for prompt in prompts:
        print(f"\nUser: {prompt}")
        response = await agent.run(prompt, session=session)
        print(f"Agent: {response.text}\n")


# ---------------------------------------------------------------------------
# Demo 2: Code-defined skill with decorators
# ---------------------------------------------------------------------------

async def demo_code_defined_skill(client: AzureOpenAIResponsesClient) -> None:
    print("=" * 70)
    print("DEMO 2: Code-Defined Skill with @skill.script / @skill.resource")
    print("=" * 70)

    text_skill = create_text_analyzer_skill()

    skills_provider = SkillsProvider(
        skills=[text_skill],
    )

    agent = client.as_agent(
        name="TextAnalyzer",
        instructions=(
            "You are a text analysis assistant. Use your text-analyzer skill "
            "to help users analyze text content."
        ),
        context_providers=[skills_provider],
    )

    session = AgentSession()
    sample_text = (
        "The quick brown fox jumps over the lazy dog. "
        "This sentence contains every letter of the English alphabet. "
        "It is commonly used for font testing and typing practice."
    )

    prompts = [
        f"Analyze this text: '{sample_text}'",
        "What formats do you support for text analysis?",
    ]

    for prompt in prompts:
        print(f"\nUser: {prompt}")
        response = await agent.run(prompt, session=session)
        print(f"Agent: {response.text}\n")


# ---------------------------------------------------------------------------
# Demo 3: Mixed skills (file-based + code-defined) with approval
# ---------------------------------------------------------------------------

async def demo_mixed_with_approval(client: AzureOpenAIResponsesClient) -> None:
    print("=" * 70)
    print("DEMO 3: Mixed Skills with Script Approval")
    print("=" * 70)

    text_skill = create_text_analyzer_skill()

    skills_provider = SkillsProvider(
        skill_paths=[str(SKILLS_DIR / "data-validator"), str(SKILLS_DIR / "unit-converter")],
        skills=[text_skill],
        script_runner=run_skill_script,
        require_script_approval=True,
    )

    agent = client.as_agent(
        name="MultiSkillAssistant",
        instructions=(
            "You are a versatile assistant with data validation, unit conversion, "
            "and text analysis capabilities. Use the appropriate skill for each request."
        ),
        context_providers=[skills_provider],
    )

    session = AgentSession()

    print("\nUser: What are all the skills and scripts you have access to?")
    response = await agent.run(
        "What are all the skills and scripts you have access to? List each skill and its scripts.",
        session=session,
    )
    print(f"Agent: {response.text}\n")

    print("(Script approval is enabled - the agent would request approval before running scripts)")


# ---------------------------------------------------------------------------
# Demo 4: Standalone script execution (no agent, direct runner)
# ---------------------------------------------------------------------------

def demo_direct_script_execution() -> None:
    print("=" * 70)
    print("DEMO 4: Direct Script Execution (no agent)")
    print("=" * 70)

    # Create a temporary CSV for testing
    test_csv = SKILLS_DIR / "data-validator" / "scripts" / "_test_data.csv"
    test_csv.write_text("id,name,email\n1,Alice,alice@example.com\n2,Bob,\n3,,charlie@test.com\n")

    # Create a SkillScript pointing to the validate_csv script
    script = SkillScript(
        name="validate_csv",
        description="Validate a CSV file",
        path=str(SKILLS_DIR / "data-validator" / "scripts" / "validate_csv.py"),
    )
    skill = Skill(
        name="data-validator",
        description="Data validation",
        content="Validate data files",
        path=str(SKILLS_DIR / "data-validator" / "SKILL.md"),
    )

    print(f"\nRunning validate_csv on test data...")
    result = run_skill_script(skill, script, {"file": str(test_csv)})
    parsed = json.loads(result)
    print(json.dumps(parsed, indent=2))

    # Run summarize_data
    script2 = SkillScript(
        name="summarize_data",
        description="Summarize data file",
        path=str(SKILLS_DIR / "data-validator" / "scripts" / "summarize_data.py"),
    )
    print(f"\nRunning summarize_data on test data...")
    result2 = run_skill_script(skill, script2, {"file": str(test_csv), "format": "csv"})
    parsed2 = json.loads(result2)
    print(json.dumps(parsed2, indent=2))

    # Run unit converter
    converter_script = SkillScript(
        name="convert",
        description="Convert units",
        path=str(SKILLS_DIR / "unit-converter" / "scripts" / "convert.py"),
    )
    converter_skill = Skill(
        name="unit-converter",
        description="Unit conversion",
        content="Convert units",
        path=str(SKILLS_DIR / "unit-converter" / "SKILL.md"),
    )
    print(f"\nRunning convert: 5 miles to km...")
    result3 = run_skill_script(converter_skill, converter_script, {"value": "5", "from_unit": "mi", "to_unit": "km"})
    parsed3 = json.loads(result3)
    print(json.dumps(parsed3, indent=2))

    # Cleanup
    test_csv.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

    if not all([endpoint, api_key, deployment]):
        print("ERROR: Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT")
        print("       Copy .env.example to .env and fill in your values.")
        sys.exit(1)

    client = AzureOpenAIResponsesClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
    )

    # Demo 4 runs without Azure credentials (direct script execution)
    demo_direct_script_execution()

    # Demos 1-3 require Azure OpenAI
    await demo_file_based_skills(client)
    await demo_code_defined_skill(client)
    await demo_mixed_with_approval(client)

    print("\n" + "=" * 70)
    print("All demos complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
