# Sports Research AI

AI-powered sports research and analysis system using prompt chaining workflows.

## Setup

1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if you haven't already

2. Create and activate the conda environment:
```bash
conda env create -f environment.yml
conda activate sports-research-ai
```

3. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=your_api_key_here
```

## Development

Start the server:
```bash
uvicorn app.api:app --reload
```

## Project Structure

```
.
├── app/
│   ├── chains/         # Prompt chain definitions
│   ├── models/         # Pydantic models
│   ├── prompts/        # Prompt templates
│   └── api.py         # FastAPI application
├── .env               # Environment variables
├── environment.yml    # Conda environment specification
└── README.md         # This file
```

## Features

- Modular prompt chain architecture
- Sports-specific research workflows
- API endpoints for easy integration
- Extensible design for adding new research capabilities 