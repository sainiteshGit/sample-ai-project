# Microsoft Agent Framework - Python Script Execution Skills

Python implementation of [Agent Skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python) with script execution capabilities using the Microsoft Agent Framework SDK.

## Project Structure

```
msft-agent-framework-skills-python/
├── main.py                          # Demo runner (4 demos)
├── requirements.txt
├── .env.example
├── README.md
└── skills/
    ├── data-validator/
    │   ├── SKILL.md                 # Skill definition (YAML frontmatter)
    │   ├── references/
    │   │   └── SCHEMA_GUIDE.md      # Schema documentation resource
    │   └── scripts/
    │       ├── validate_csv.py      # CSV validation script
    │       ├── validate_json.py     # JSON validation script
    │       └── summarize_data.py    # Data summarization script
    └── unit-converter/
        ├── SKILL.md                 # Skill definition
        └── scripts/
            └── convert.py           # Unit conversion script
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

## Usage

```bash
python main.py
```

## Demos

### Demo 1: File-Based Skills
Loads skills from `skills/` directories using `SkillsProvider(skill_paths=...)` with a custom `script_runner` that executes Python scripts in subprocesses.

### Demo 2: Code-Defined Skills
Creates a `text-analyzer` skill entirely in code using `@skill.script` and `@skill.resource` decorators — no files on disk.

### Demo 3: Mixed Skills with Approval
Combines file-based and code-defined skills with `require_script_approval=True` for controlled script execution.

### Demo 4: Direct Script Execution
Runs scripts directly via the `run_skill_script` runner without an LLM agent, demonstrating the script execution pipeline.

## Key Concepts

### SkillsProvider
```python
skills_provider = SkillsProvider(
    skill_paths=["skills/data-validator", "skills/unit-converter"],
    skills=[code_defined_skill],
    script_runner=my_runner,
    require_script_approval=True,
)
```

### Custom Script Runner
Implements the `SkillScriptRunner` protocol: `(skill, script, args) -> str`

```python
def run_skill_script(skill: Skill, script: SkillScript, args: dict | None = None) -> str:
    # Execute the script file and return output
    ...
```

### Code-Defined Scripts
```python
skill = Skill(name="my-skill", description="...", content="...")

@skill.script(name="my_script", description="Does something")
def my_script(input: str = "") -> str:
    return json.dumps({"result": input.upper()})
```

### SKILL.md Format
Each file-based skill directory must contain a `SKILL.md` with YAML frontmatter:
```markdown
---
name: my-skill
description: What this skill does
---
Detailed instructions for the agent on how to use this skill.
```
