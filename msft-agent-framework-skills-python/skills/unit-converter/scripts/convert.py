#!/usr/bin/env python3
"""Convert between common units of measurement."""

import argparse
import json

CONVERSIONS: dict[str, dict[str, float]] = {
    # Length (base: meters)
    "km": {"m": 1000}, "m": {"m": 1}, "cm": {"m": 0.01}, "mm": {"m": 0.001},
    "mi": {"m": 1609.344}, "yd": {"m": 0.9144}, "ft": {"m": 0.3048}, "in": {"m": 0.0254},
    # Weight (base: grams)
    "kg": {"g": 1000}, "g": {"g": 1}, "mg": {"g": 0.001},
    "lb": {"g": 453.592}, "oz": {"g": 28.3495}, "ton": {"g": 907184.74},
    # Volume (base: liters)
    "l": {"l": 1}, "ml": {"l": 0.001},
    "gal": {"l": 3.78541}, "qt": {"l": 0.946353}, "pt": {"l": 0.473176},
    "cup": {"l": 0.236588}, "fl_oz": {"l": 0.0295735},
}

TEMP_UNITS = {"celsius", "fahrenheit", "kelvin"}


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    # Normalize to Celsius first
    if from_unit == "fahrenheit":
        celsius = (value - 32) * 5 / 9
    elif from_unit == "kelvin":
        celsius = value - 273.15
    else:
        celsius = value

    # Convert from Celsius to target
    if to_unit == "fahrenheit":
        return celsius * 9 / 5 + 32
    elif to_unit == "kelvin":
        return celsius + 273.15
    return celsius


def convert(value: float, from_unit: str, to_unit: str) -> dict:
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()

    if from_unit in TEMP_UNITS and to_unit in TEMP_UNITS:
        result = convert_temperature(value, from_unit, to_unit)
        return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": round(result, 4)}

    if from_unit not in CONVERSIONS:
        return {"error": f"Unknown unit: {from_unit}"}
    if to_unit not in CONVERSIONS:
        return {"error": f"Unknown unit: {to_unit}"}

    from_info = CONVERSIONS[from_unit]
    to_info = CONVERSIONS[to_unit]
    from_base = list(from_info.keys())[0]
    to_base = list(to_info.keys())[0]

    if from_base != to_base:
        return {"error": f"Cannot convert between {from_unit} and {to_unit} (different categories)"}

    base_value = value * from_info[from_base]
    result = base_value / to_info[to_base]
    factor = from_info[from_base] / to_info[to_base]

    return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": round(result, 4), "factor": round(factor, 6)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert between units")
    parser.add_argument("--value", type=float, required=True)
    parser.add_argument("--from_unit", required=True)
    parser.add_argument("--to_unit", required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.value, args.from_unit, args.to_unit), indent=2))
