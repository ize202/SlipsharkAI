# SlipsharkAI

SlipsharkAI is a FastAPI backend for a sports research assistant. It takes a sports question, decides when to search the web with Exa, and streams back an answer with sources.

## What it is

This repo is the API layer behind a sports assistant prototype. It exposes a `/research` endpoint for streamed answers plus a simple root health check.

## What problem it solves

The goal was to answer sports questions with current information instead of relying on the model alone. The API adds search, basic access control, and streaming so a frontend can show answers as they come in.

## What I built

- A FastAPI service that streams responses over server-sent events
- `X-API-Key` request validation for the main research endpoint
- An Exa-powered search flow that pulls in current sources when the model needs them
- HTML-safe response formatting for mobile and web clients
- Railway deployment files and a local dotenv setup

## Stack

- Python
- FastAPI
- OpenAI
- Exa
- Railway

## Screenshots or demo

```bash
curl -X POST "http://localhost:8000/research" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_v1_your_generated_key" \
  -d '{"query":"What NBA games are on tonight?","platform":"mobile"}'
```

The endpoint streams chunks back as server-sent events.

## Local setup

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Add these values to `.env`:

```env
OPENAI_API_KEY=...
EXA_API_KEY=...
API_KEY=sk_v1_generated_key
```

4. If you need a valid app key, run `python generate_key.py`.
5. Start the API with `uvicorn main:app --reload`.

## Current status

MVP backend for a sports assistant. The core flow works. What is left is product polish and better deployment setup.
