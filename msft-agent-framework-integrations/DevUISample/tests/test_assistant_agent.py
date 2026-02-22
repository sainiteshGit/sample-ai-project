"""Tests for the assistant agent tool functions (no LLM calls)."""
from __future__ import annotations

import pytest

from agents.assistant_agent import calculate, get_current_datetime, word_count


class TestCalculate:
    @pytest.mark.parametrize("expr,expected", [
        ("2 + 3",       "5"),
        ("10 - 4",      "6"),
        ("3 * 4",       "12"),
        ("10 / 4",      "2.5"),
        ("(2 + 3) * 4", "20"),
    ])
    def test_valid_expressions(self, expr: str, expected: str):
        result = calculate(expr)
        assert expected in result

    def test_invalid_expression_returns_error(self):
        result = calculate("2 ** 31")   # ** contains * which is now blocked
        assert "Unsafe" in result

    def test_division_by_zero(self):
        result = calculate("1 / 0")
        assert "Could not evaluate" in result or "division by zero" in result.lower()

    def test_result_includes_original_expression(self):
        result = calculate("7 + 8")
        assert "7 + 8" in result


class TestGetCurrentDatetime:
    def test_returns_utc_string(self):
        result = get_current_datetime()
        assert "UTC" in result

    def test_contains_date_parts(self):
        result = get_current_datetime()
        import re
        # Expect format: 2026-02-21 ...
        assert re.search(r"\d{4}-\d{2}-\d{2}", result)


class TestWordCount:
    def test_simple_sentence(self):
        result = word_count("hello world foo")
        assert "3 words" in result

    def test_character_count(self):
        text = "hello"
        result = word_count(text)
        assert "5 characters" in result

    def test_empty_string(self):
        result = word_count("")
        assert "0 words" in result
