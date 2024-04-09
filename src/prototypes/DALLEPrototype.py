import base64

from openai import OpenAI
client = OpenAI()

response = client.images.generate(
    model="dall-e-3",
    prompt="A cute anime girl with blonde hair",
    size="1024x1024",
    quality="standard",
    n=1,
    response_format="b64_json"
)

b64_str = response.data[0].b64_json

print(b64_str)

print(f'Generation tokens: ')
print(f'Total tokens: ')

try:
    image_data = base64.b64decode(b64_str)

    with open("output.png", "wb") as file:
        file.write(image_data)
except Exception as e:
    print(f'Error: {e}')