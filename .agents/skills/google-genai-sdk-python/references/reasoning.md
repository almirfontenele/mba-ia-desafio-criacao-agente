# Reasoning (Thinking)

Reasoning models generate "thoughts" before the final response to improve accuracy on complex tasks.

## Configuration

### Gemini 3 Series
Use `thinking_level` to control reasoning depth.
*   `MINIMAL`: Minimal reasoning, lowest latency.
*   `LOW`: Simple tasks.
*   `MEDIUM`: Balanced.
*   `HIGH`: Maximum depth (default).

```python
config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.HIGH,
        include_thoughts=True # Returns thoughts in response
    )
)
```

### Gemini 2.5 Series
Use `thinking_budget` (token count).
*   `0`: Thinking OFF.
*   `1024`: Specific token budget.

```python
config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        thinking_budget=1024,
        include_thoughts=True
    )
)
```

## Accessing Thoughts
If `include_thoughts=True`, thoughts are returned as parts.
```python
for part in response.candidates[0].content.parts:
    if part.thought:
        print(f"Thought: {part.text}")
    else:
        print(f"Response: {part.text}")
```

## Thought Signatures
When using tools with reasoning models, the API returns an encrypted `thought_signature`.
*   **Automatic:** The SDK handles this automatically when using `chats` or preserving the full `response` object in history.
*   **Manual:** If manually constructing history, you **must** include the `thought_signature` from the model's turn in the next request to avoid errors.
