from openai import OpenAI
import base64

client = OpenAI()

# Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

base64_image = encode_image("astronaut.png")

response = client.chat.completions.create(
  model="gpt-4-vision-preview",
  messages=[
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What’s in this image?"},
        {
          "type": "image_url",
          "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}",
              "detail": "high",
          },
        },
      ],
    }
  ],
  max_tokens=300,
)

print(response.choices[0].message.content)
print(f'Input tokens:  {response.usage.prompt_tokens}')
print(f'Total tokens: {response.usage.total_tokens}')



# features to add
# user can load an image (select from explorer OR drag and drop) --> AI can interpret and react to it (same prompt; + image specific prompts -- e.g. the recognition of self)
# saving memories -- any images the user sends will be saved to image memory. Add to remember function -- when user mentions image/picture/photo -- search in image memory (in addition to vectorstore) --> interpret image using vision
# when saving memories, have gpt assign a name and a description that is associated with the image (may be easily searched in the future)
