# Weather Data Sources

## Recommended APIs

| Service | Free Tier | Rate Limit | Coverage |
|---------|-----------|------------|----------|
| OpenWeatherMap | 1,000 calls/day | 60/min | Global |
| Weather.gov | Unlimited | Reasonable use | US only |
| Open-Meteo | Unlimited | 10,000/day | Global |

## OpenWeatherMap API

- **Current Weather:** `https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric`
- **5-Day Forecast:** `https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={key}&units=metric`

## Weather.gov API (US)

- **Points:** `https://api.weather.gov/points/{lat},{lon}`
- **Forecast:** Use the forecast URL from the points response
- No API key required; set a descriptive `User-Agent` header

## Open-Meteo API

- **Forecast:** `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true`
- No API key required
- Supports hourly and daily forecasts

## Data Accuracy Notes

- Free tier APIs may have a 10-30 minute delay for current conditions
- Forecast accuracy degrades significantly beyond 7 days
- Severe weather alerts are best sourced from Weather.gov (US) or national meteorological services
