#!/usr/bin/env python3
"""Validate CSV file structure and data quality."""

import argparse
import csv
import json
from pathlib import Path


def validate_csv(file_path: str, schema_path: str | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    row_count = 0

    resolved = Path(file_path).resolve()
    if not resolved.is_file():
        return {
            "status": "invalid",
            "errors": [{"row": 0, "field": "", "message": f"File not found: {file_path}"}],
            "warnings": [],
            "summary": "Validation failed: file not found",
        }

    schema = None
    if schema_path:
        schema_resolved = Path(schema_path).resolve()
        if schema_resolved.is_file():
            with open(schema_resolved, encoding="utf-8") as f:
                schema = json.load(f)

    with open(resolved, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return {
                "status": "invalid",
                "errors": [{"row": 0, "field": "", "message": "Empty file"}],
                "warnings": [],
                "summary": "Validation failed: empty file",
            }

        expected_cols = len(headers)
        seen: set[str] = set()
        for h in headers:
            if h in seen:
                warnings.append({"row": 0, "field": h, "message": f"Duplicate header: {h}"})
            seen.add(h)

        if schema and "required_fields" in schema:
            for field in schema["required_fields"]:
                if field not in headers:
                    errors.append({"row": 0, "field": field, "message": f"Required field missing: {field}"})

        for row_idx, row in enumerate(reader, start=2):
            row_count += 1
            if len(row) != expected_cols:
                errors.append({"row": row_idx, "field": "", "message": f"Expected {expected_cols} columns, got {len(row)}"})
            for col_idx, value in enumerate(row):
                if col_idx < len(headers) and value.strip() == "":
                    field_name = headers[col_idx]
                    if schema and field_name in schema.get("required_fields", []):
                        errors.append({"row": row_idx, "field": field_name, "message": "Required field is empty"})
                    else:
                        warnings.append({"row": row_idx, "field": field_name, "message": "Empty value"})

    status = "invalid" if errors else ("warning" if warnings else "valid")
    return {
        "status": status,
        "headers": headers,
        "row_count": row_count,
        "errors": errors[:50],
        "warnings": warnings[:50],
        "summary": f"Processed {row_count} rows, {len(errors)} error(s), {len(warnings)} warning(s)",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a CSV file")
    parser.add_argument("--file", required=True)
    parser.add_argument("--schema", default=None)
    args = parser.parse_args()
    print(json.dumps(validate_csv(args.file, args.schema), indent=2))
