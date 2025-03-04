import os
from openai import OpenAI
from dotenv import load_dotenv
import requests
import json

# Load environment variables
load_dotenv()


url = "https://api.perplexity.ai/chat/completions"

payload = {
    "model": "sonar",
    "messages": [
        {
            "role": "system",
            "content": "Be precise and concise."
        },
        {
            "role": "user",
            "content": "How many stars are there in our galaxy?"
        }
    ],
}
headers = {
    "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)
response_json = response.json()

# Print just the content from the assistant's message
print("\nAssistant's response:")
print(response_json['choices'][0]['message']['content'])

# Optionally print citations if you want them
print("\nCitations:")
for citation in response_json['citations']:
    print(f"- {citation}")