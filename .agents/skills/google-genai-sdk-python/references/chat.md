# Chat

For multi-turn conversations, use the `chats` service. It manages history automatically.

## Basic Chat
```python
chat = client.chats.create(model='gemini-3-flash-preview')

response = chat.send_message('Hello, I am a developer.')
print(response.text)

response = chat.send_message('What did I just say I am?')
print(response.text)
```

## History Access
```python
for message in chat.get_history():
    print(f'{message.role}: {message.parts[0].text}')
```

## Custom History
Initialize a chat with existing history.
```python
history = [
    types.Content(role='user', parts=[types.Part.from_text(text='Hi')]),
    types.Content(role='model', parts=[types.Part.from_text(text='Hello')])
]
chat = client.chats.create(model='gemini-3-flash-preview', history=history)
```
