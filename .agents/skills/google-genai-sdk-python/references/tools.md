# Tools & Grounding

## Grounding (Google Search)
Enable the model to access real-time information.
```python
tools = [types.Tool(google_search=types.GoogleSearch())]
response = client.models.generate_content(..., config=types.GenerateContentConfig(tools=tools))
```

## Code Execution
Enable Python code generation and execution.
```python
tools = [types.Tool(code_execution=types.ToolCodeExecution())]
```

## Function Calling
Pass Python functions to the model.

### Definition
```python
def get_weather(city: str) -> str:
    """Returns weather for a city."""
    return "Sunny"

tools = [get_weather]
```

### Configuration
```python
config = types.GenerateContentConfig(
    tools=tools,
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.AUTO, # or ANY, NONE
            stream_function_call_arguments=True # For streaming args
        )
    )
)
```

### Handling (Automatic)
Use `client.chats` or preserve history, and the SDK handles execution automatically.

### Handling (Manual)
Check `response.function_calls`, execute, and return `types.Part.from_function_response`.
