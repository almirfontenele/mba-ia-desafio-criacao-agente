# Structured Output

Enforce specific response structures using `response_schema`.

## Pydantic Models (Recommended)
```python
from pydantic import BaseModel

class Recipe(BaseModel):
    name: str
    ingredients: list[str]

response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents='Cookie recipe',
    config=types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=Recipe,
    ),
)
# Access parsed object directly
print(response.parsed)
```

## JSON Schema (Dict)
```python
schema = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "age": {"type": "INTEGER"}
    }
}
response = client.models.generate_content(
    ...,
    config=types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=schema
    )
)
```

## Enums
You can also restrict output to a specific enum.
```python
import enum
class Grade(enum.Enum):
    A = "A"
    B = "B"

config=types.GenerateContentConfig(
    response_mime_type='text/x.enum',
    response_schema=Grade
)
```
