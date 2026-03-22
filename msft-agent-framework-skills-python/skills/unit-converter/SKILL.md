---
name: unit-converter
description: Convert between common units of measurement including length, weight, temperature, volume, and currency. Use when asked to convert values between different measurement systems.
license: MIT
compatibility: Requires python3 for script execution
metadata:
  author: contoso-tools
  version: "1.0"
allowed-tools: run_skill_script
---

# Unit Converter Skill

You convert values between units of measurement. Use the scripts for accurate conversions.

## Available Scripts

| Script | Purpose | Arguments |
|--------|---------|-----------|
| `convert.py` | Convert a value between units | `--value <number>` `--from_unit <unit>` `--to_unit <unit>` |

## Supported Conversions

### Length
km, m, cm, mm, mi, yd, ft, in

### Weight  
kg, g, mg, lb, oz, ton

### Temperature
celsius, fahrenheit, kelvin

### Volume
l, ml, gal, qt, pt, cup, fl_oz

## Response Format

Always respond with:
1. The original value and unit
2. The converted value and unit  
3. The conversion factor used

Example: "5 miles = 8.0467 kilometers (1 mile = 1.60934 km)"
