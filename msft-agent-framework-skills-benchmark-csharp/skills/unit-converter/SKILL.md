---
name: unit-converter
description: Converts between common units of distance, weight, temperature, and volume. Use whenever the user asks to convert physical units.
metadata:
  author: contoso-eng
  version: "1.0"
---

# Unit Converter

Apply the table below. Always show the formula, then the result rounded to 4 decimal places.

## Distance
| From       | To         | Multiply by |
|------------|------------|-------------|
| miles      | kilometers | 1.60934     |
| kilometers | miles      | 0.621371    |
| feet       | meters     | 0.3048      |
| meters     | feet       | 3.28084     |
| inches     | cm         | 2.54        |
| cm         | inches     | 0.393701    |

## Weight
| From       | To         | Multiply by |
|------------|------------|-------------|
| pounds     | kilograms  | 0.453592    |
| kilograms  | pounds     | 2.20462     |
| ounces     | grams      | 28.3495     |
| grams      | ounces     | 0.035274    |

## Temperature (formula, not factor)
- F → C : (F − 32) × 5/9
- C → F : C × 9/5 + 32
- C → K : C + 273.15

## Volume
| From    | To      | Multiply by |
|---------|---------|-------------|
| gallons | liters  | 3.78541     |
| liters  | gallons | 0.264172    |
| cups    | ml      | 236.588     |
| ml      | cups    | 0.00422675  |

## Output format
1. Formula used.
2. Numeric result with both units.
3. One-line sanity check ("e.g. 100 km ≈ 62 mi, makes sense").
