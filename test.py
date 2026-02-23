from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": "Say hello briefly"}],
    temperature=0,
    max_tokens=20,
)

print(resp.choices[0].message.content)
print(resp.usage)