#!/usr/bin/env python3
"""Validate JSON file against an optional JSON Schema."""

import argparse
import json
from pathlib import Path


def validate_json(file_path: str, schema_path: str | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    resolved = Path(file_path).resolve()
    if not resolved.is_file():
        return {
            "status": "invalid",
            "errors": [{"row": 0, "field": "", "message": f"File not found: {file_path}"}],
            "warnings": [],
            "summary": "Validation failed: file not found",
        }

    try:
        with open(resolved, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "status": "invalid",
            "errors": [{"row": e.lineno, "field": "", "message": f"JSON parse error: {e.msg}"}],
            "warnings": [],
            "summary": f"Invalid JSON at line {e.lineno}",
        }

    schema = None
    if schema_path:
        schema_resolved = Path(schema_path).resolve()
        if schema_resolved.is_file():
            with open(schema_resolved, encoding="utf-8") as f:
                schema = json.load(f)

    record_count = 0
    if isinstance(data, list):
        record_count = len(data)
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                warnings.append({"row": idx + 1, "field": "", "message": f"Expected object, got {type(item).__name__}"})
                continue
            if schema and "required_fields" in schema:
                for field in schema["required_fields"]:
                    if field not in item:
                        errors.append({"row": idx + 1, "field": field, "message": f"Required field missing: {field}"})
                    elif item[field] is None or item[field] == "":
                        errors.append({"row": idx + 1, "field": field, "message": "Required field is null or empty"})
            if schema and "field_types" in schema:
                for field, expected in schema["field_types"].items():
                    if field in item and item[field] is not None:
                        actual = type(item[field]).__name__
                        if actual != expected:
                            warnings.append({"row": idx + 1, "field": field, "message": f"Expected '{expected}', got '{actual}'"})
    elif isinstance(data, dict):
        record_count = 1
        if schema and "required_fields" in schema:
            for field in schema["required_fields"]:
                if field not in data:
                    errors.append({"row": 1, "field": field, "message": f"Required field missing: {field}"})

    status = "invalid" if errors else ("warning" if warnings else "valid")
    return {
        "status": status,
        "record_count": record_count,
        "errors": errors[:50],
        "warnings": warnings[:50],
        "summary": f"Processed {record_count} record(s), {len(errors)} error(s), {len(warnings)} warning(s)",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a JSON file")
    parser.add_argument("--file", required=True)
    parser.add_argument("--schema", default=None)
    args = parser.parse_args()
    print(json.dumps(validate_json(args.file, args.schema), indent=2))
