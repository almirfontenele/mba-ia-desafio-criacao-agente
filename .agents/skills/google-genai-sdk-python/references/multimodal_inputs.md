# Multimodal Inputs

Gemini supports Text, Images, Audio, Video, and PDF documents.

## Images (PIL & Bytes)
```python
# PIL
from PIL import Image
img = Image.open('image.jpg')

# Bytes
with open('image.jpg', 'rb') as f:
    img_bytes = f.read()

response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents=[
        img, # Or types.Part.from_bytes(img_bytes, mime_type='image/jpeg')
        'Describe this.'
    ]
)
```

## Audio & Video (File API)
For large files (video, long audio), use the Files API.
```python
# Upload
video_file = client.files.upload(file='video.mp4')

# Generate
response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents=[video_file, 'What happens in this video?']
)

# Cleanup
client.files.delete(name=video_file.name)
```

## Media Resolution
Control vision detail vs. token usage. Levels: `LOW`, `MEDIUM`, `HIGH`, `ULTRA_HIGH`.
```python
# Per-part configuration
part = types.Part.from_uri(
    file_uri='...',
    mime_type='image/jpeg',
    media_resolution=types.PartMediaResolution(
        level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW
    )
)
```
