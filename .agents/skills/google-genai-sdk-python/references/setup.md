# Setup and Initialization

## Installation
**Golden Rule:** Always use the `google-genai` SDK. Do not use legacy `google-generativeai`.

```bash
pip install google-genai
```

## Initialization
The SDK requires a client object. It implicitly uses the `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) environment variable.

```python
from google import genai
from google.genai import types

# Standard initialization
client = genai.Client()

# Explicit API key (avoid hardcoding in production)
# client = genai.Client(api_key='YOUR_API_KEY')

# Vertex AI Initialization
# client = genai.Client(
#     vertexai=True,
#     project='your-project-id',
#     location='us-central1'
# )
```

## Best Practices
- **Imports:** Use `from google import genai` and `from google.genai import types`.
- **Statelessness:** The client is predominantly stateless. Access methods via `client.models`, `client.chats`, etc.
