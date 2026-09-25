# Media Generation

## Image Generation (Imagen)
Use `gemini-2.5-flash-image` (Nano Banana) or `gemini-3-pro-image-preview` (Nano Banana Pro).

```python
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='A futuristic city',
    config=types.GenerateContentConfig(
        image_config=types.ImageConfig(number_of_images=1)
    )
)
for part in response.parts:
    part.as_image().save('image.png')
```

## Image Editing
Use `chats` for editing workflows.
```python
chat = client.chats.create(model='gemini-2.5-flash-image')
response = chat.send_message(['Change the sky to purple', image])
```

## Video Generation (Veo)
Use `veo-3.0-generate-001` or `veo-3.0-fast-generate-001`.
```python
operation = client.models.generate_videos(
    model='veo-3.0-fast-generate-001',
    prompt='A cat driving a car',
)
while not operation.done:
    time.sleep(5)
    operation = client.operations.get(operation)

# Download
for video in operation.response.generated_videos:
    video.video.save('video.mp4')
```
