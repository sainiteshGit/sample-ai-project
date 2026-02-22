"""Tests for the weather agent tool functions (no LLM calls)."""
from __future__ import annotations

import pytest

# Import tool functions directly — no LLM call needed
from agents.weather_agent import get_current_weather, get_5_day_forecast


class TestGetCurrentWeather:
    def test_known_city_returns_condition(self):
        result = get_current_weather("Seattle")
        assert "Seattle" in result
        assert "°F" in result
        assert "°C" in result

    def test_city_with_country_code(self):
        result = get_current_weather("London, UK")
        assert "London" in result

    def test_unknown_city_returns_simulated(self):
        result = get_current_weather("Atlantis")
        assert "Atlantis" in result
        assert "simulated" in result.lower()

    def test_case_insensitive(self):
        lower = get_current_weather("tokyo")
        upper = get_current_weather("TOKYO")
        # Function preserves the original casing of `location` in the output
        # but the lookup is case-insensitive — both should find weather data
        assert "sunny" in lower
        assert "sunny" in upper

    @pytest.mark.parametrize("city", [
        "New York", "London", "Tokyo", "Sydney", "Paris", "Chicago", "Miami"
    ])
    def test_all_known_cities(self, city: str):
        result = get_current_weather(city)
        assert city in result or city.lower() in result.lower()


class TestGet5DayForecast:
    def test_contains_location(self):
        result = get_5_day_forecast("Seattle")
        assert "Seattle" in result

    def test_contains_five_days(self):
        result = get_5_day_forecast("London")
        for day in range(1, 6):
            assert f"Day {day}" in result

    def test_contains_simulated_note(self):
        result = get_5_day_forecast("Paris")
        assert "Simulated" in result or "simulated" in result
