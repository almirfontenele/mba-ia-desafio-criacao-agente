# Text Generation & Configuration

## Basic Generation
```python
response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents='Why is the sky blue?',
)
print(response.text)
```

## Streaming
Reduces time-to-first-token.
```python
response = client.models.generate_content_stream(
    model='gemini-3-flash-preview',
    contents='Write a long story about a space pirate.'
)
for chunk in response:
    print(chunk.text, end='')
```

## Configuration (`GenerateContentConfig`)
Control generation parameters, system instructions, and safety.

### System Instructions
```python
config = types.GenerateContentConfig(
    system_instruction='You are a pirate. Speak like one.',
)
```

### Hyperparameters
**Note:** For Gemini 3 models, keep `temperature` at `1.0` (default) for optimal reasoning.
```python
config = types.GenerateContentConfig(
    temperature=1.0,
    max_output_tokens=500,
    top_p=0.95,
)
```

### Safety Settings
Avoid setting these unless explicitly requested.
```python
config = types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        ),
    ]
)
```

## Content & Part Hierarchy
For complex requests (e.g., specific roles), use `Content` and `Part` objects explicitly.
```python
contents=[
    types.Content(
        role='user',
        parts=[types.Part.from_text(text='Hello')]
    )
]
```
