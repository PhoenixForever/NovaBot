
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

image_path = input("Enter the path to a test image: ").strip().strip('"')

with open(image_path, "rb") as image_file:
    import base64
    image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="qwen/qwen3.8-27b",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Read the text visible in this image. If there is no text, describe the main object."                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        }
    ],
    temperature=0.3,
    max_tokens=200
)

print("\nVision model response:")
print(response.choices[0].message.content)
