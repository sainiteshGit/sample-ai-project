---
name: code-style
description: Reviews Python or C# code against the Contoso engineering style guide. Use when the user asks to review code, check style, or apply naming/formatting conventions.
metadata:
  author: contoso-eng
  version: "4.1"
---

# Contoso Engineering Style Guide

## 1. Universal rules
- Lines ≤ 120 chars.
- No tabs — 4 spaces.
- Trailing newline on every file.
- One concept per commit; commit messages in imperative mood.

## 2. Python
- `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE` for constants.
- Type hints required on every public function. Use `from __future__ import annotations`.
- Prefer `pathlib.Path` over `os.path`.
- Use `logging`, never `print`, in library code.
- Format with `ruff format`; lint with `ruff check --select E,F,I,UP,B,SIM`.
- Async functions must have `_async` suffix only if a sync sibling exists.

## 3. C#
- `PascalCase` for types, methods, properties; `_camelCase` for private fields.
- File-scoped namespaces. One public type per file.
- Prefer `var` only when the type is obvious from the right-hand side.
- Async methods end with `Async`. Always pass `CancellationToken`.
- Use `Microsoft.Extensions.Logging`, never `Console.WriteLine`, in library code.
- Format with `dotnet format`. Treat warnings as errors in CI.

## 4. Anti-patterns to flag
- Catching bare `Exception` / `catch {}` without rethrow or logging.
- Mutable default arguments in Python (`def f(x=[])`).
- `Task.Result` / `.Wait()` in C# async paths.
- Magic numbers — extract to named constants.

## 5. Output format
1. `STATUS`: PASS | NEEDS_CHANGES
2. Numbered list of findings: file/line, rule violated, suggested fix.
3. End with a one-line summary.
