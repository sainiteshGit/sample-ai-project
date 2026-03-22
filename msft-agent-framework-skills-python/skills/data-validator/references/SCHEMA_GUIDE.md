# Schema Guide

## CSV Schema Format

```json
{
  "required_fields": ["id", "name", "email"],
  "field_types": {
    "id": "integer",
    "name": "string",
    "email": "email"
  }
}
```

## JSON Schema Format

```json
{
  "required_fields": ["id", "name", "status"],
  "field_types": {
    "id": "int",
    "name": "str",
    "status": "str"
  }
}
```

## Type Reference

| Type | CSV | JSON Python Type |
|------|-----|-----------------|
| string / str | Any text | `str` |
| integer / int | `42` | `int` |
| float | `3.14` | `float` |
| boolean / bool | `true` / `false` | `bool` |
| date | `2024-01-15` | `str` (ISO 8601) |
| email | `user@example.com` | `str` (with @) |
