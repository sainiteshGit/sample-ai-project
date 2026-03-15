---
name: weather-lookup
description: Look up current weather conditions and forecasts for any location. Use when asked about weather, temperature, conditions, or forecasts for a city or region.
license: MIT
compatibility: Requires internet access for weather API calls
metadata:
  author: contoso-tools
  version: "1.0"
---

# Weather Lookup Skill

Provide weather information and forecasts based on user queries.

## Capabilities

1. **Current conditions** — Temperature, humidity, wind speed, and description for a given location.
2. **Forecasts** — Multi-day forecasts with highs, lows, and precipitation probability.
3. **Travel weather** — Weather comparison for multiple destinations to help trip planning.
4. **Severe weather alerts** — Flag any active weather warnings for the requested area.

## How to Respond

When asked about weather:

1. Identify the **location** (city, state/country, or coordinates).
2. Identify the **time frame** (current, today, this week, specific date).
3. Provide a clear, concise weather summary.

## Response Format

```
## Weather for [Location]
**Date:** [Date or range]

| Metric | Value |
|--------|-------|
| Temperature | XX°F / XX°C |
| Conditions | [e.g., Partly cloudy] |
| Humidity | XX% |
| Wind | XX mph [Direction] |
| Precipitation | XX% chance |

[Any relevant advisories or notes]
```

## Important Notes

- Always provide temperatures in both **Fahrenheit and Celsius**.
- If the user asks about outdoor activities, include relevant comfort info (heat index, wind chill, UV index).
- For travel weather, present a side-by-side comparison table.
- If you cannot determine live weather data, clearly state you're providing **general climate information** for that location and time of year.

For data source details, load the `references/WEATHER_SOURCES.md` resource.
