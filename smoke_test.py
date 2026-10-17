import os
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],   # don't hardcode
)

resp = client.chat.completions.create(
    model="openrouter/free",
    messages=[{"role": "user", "content": 'Reply with only the JSON {"ok": true}'}],
    response_format={"type": "json_object"},
    temperature=0.0,
)
print("RAW:", resp.choices[0].message.content)
print("MODEL USED:", resp.model)