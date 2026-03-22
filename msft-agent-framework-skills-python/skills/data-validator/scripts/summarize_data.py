#!/usr/bin/env python3
"""Generate summary statistics for a dataset."""

import argparse
import csv
import json
from pathlib import Path


def summarize_csv(file_path: str) -> dict:
    resolved = Path(file_path).resolve()
    if not resolved.is_file():
        return {"error": f"File not found: {file_path}"}

    with open(resolved, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    field_stats: dict[str, dict] = {}
    for header in headers:
        values = [r[header] for r in rows if r[header].strip()]
        empty_count = len(rows) - len(values)
        numeric_values: list[float] = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except ValueError:
                pass

        stats: dict = {"total": len(rows), "non_empty": len(values), "empty": empty_count, "unique": len(set(values))}
        if numeric_values:
            stats.update({"numeric": True, "min": min(numeric_values), "max": max(numeric_values), "mean": round(sum(numeric_values) / len(numeric_values), 2)})
        else:
            stats["numeric"] = False
            if values:
                stats["sample_values"] = list(set(values))[:5]
        field_stats[header] = stats

    return {"format": "csv", "row_count": len(rows), "column_count": len(headers), "columns": headers, "field_stats": field_stats}


def summarize_json(file_path: str) -> dict:
    resolved = Path(file_path).resolve()
    if not resolved.is_file():
        return {"error": f"File not found: {file_path}"}

    with open(resolved, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        all_keys: set[str] = set()
        for item in data:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        field_stats = {}
        for key in sorted(all_keys):
            values = [item.get(key) for item in data if isinstance(item, dict) and key in item]
            non_null = [v for v in values if v is not None and v != ""]
            field_stats[key] = {"present": len(values), "non_null": len(non_null), "types": list(set(type(v).__name__ for v in non_null)), "unique": len(set(str(v) for v in non_null))}
        return {"format": "json", "record_count": len(data), "fields": sorted(all_keys), "field_stats": field_stats}
    elif isinstance(data, dict):
        return {"format": "json", "record_count": 1, "fields": list(data.keys())}
    return {"format": "json", "top_level_type": type(data).__name__}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize a data file")
    parser.add_argument("--file", required=True)
    parser.add_argument("--format", choices=["csv", "json"], required=True)
    args = parser.parse_args()
    result = summarize_csv(args.file) if args.format == "csv" else summarize_json(args.file)
    print(json.dumps(result, indent=2))
