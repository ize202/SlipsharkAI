from openai import OpenAI
from dotenv import load_dotenv
from exa_py import Exa

import os

# Use .env to store your API key or paste it directly into the code
load_dotenv()

#--------------------------------
# Exa Chat Completion
#--------------------------------

client = OpenAI(
  base_url="https://api.exa.ai",
  api_key=os.getenv('EXA_API_KEY'),
)

completion = client.chat.completions.create(
  model="exa", # or exa-pro
  messages = [
  {"role": "system", "content": "You are a helpful Sports research assistant."},
  {"role": "user", "content": "nba games today"}
],

  extra_body={
    "text": True
  }
)
print(completion.choices[0].message.content)

#--------------------------------
# Search and Crawl
#--------------------------------

exa = Exa(os.getenv('EXA_API_KEY'))
result = exa.search_and_contents(
  "Nba games today",
  type="auto",
  text=True,
)

print(result)






