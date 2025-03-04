# Sports Research Assistant MVP

A simple sports research chatbot that uses OpenAI's GPT-4 and Exa's web search capabilities to provide up-to-date sports information.

## Overview

This MVP demonstrates a basic implementation of a sports research assistant that can:
- Process natural language queries about sports
- Perform real-time web searches for current information
- Provide accurate, sourced responses about games, scores, stats, and news
- Access via REST API endpoint

## Flow Diagram

```mermaid
sequenceDiagram
    participant User
    participant System
    participant GPT4
    participant ExaSearch
    
    User->>System: Sports Query
    System->>GPT4: Initialize with System Message
    GPT4-->>GPT4: Analyze Query
    
    alt Search Needed
        GPT4->>ExaSearch: Request Web Search
        ExaSearch-->>GPT4: Return Search Results
        GPT4-->>GPT4: Analyze Results
        GPT4->>System: Generate Final Response
    else No Search Needed
        GPT4->>System: Direct Response
    end
    
    System->>User: Return Answer
```

## How It Works

1. **Query Input**
   - User submits a sports-related question
   - System initializes conversation with sports assistant context

2. **Query Analysis**
   - GPT-4 analyzes the query
   - Determines if web search is needed
   - Formulates search strategy if required

3. **Web Search (if needed)**
   - Executes targeted web search via Exa API
   - Retrieves relevant sports information
   - Limited to top 5 most relevant results

4. **Response Generation**
   - GPT-4 processes search results
   - Synthesizes information into coherent answer
   - Returns formatted response to user

## Quick Start

1. Install dependencies:
```bash
pip install openai exa-py python-dotenv fastapi uvicorn
```

2. Set up environment variables in `.env`:
```
OPENAI_API_KEY=your_openai_key
EXA_API_KEY=your_exa_key
```

3. Run the API:
```bash
uvicorn main:app --reload
```

## API Usage

### REST Endpoint

POST `/research`

Request body:
```json
{
    "query": "What NBA games are scheduled for tonight?"
}
```

Response:
```json
{
    "answer": "Based on the search results..."
}
```

Example using curl:
```bash
curl -X POST "http://localhost:8000/research" \
     -H "Content-Type: application/json" \
     -d '{"query": "What NBA games are scheduled for tonight?"}'
```

### Command Line Usage

You can also use the direct script:
```bash
python exa_search.py "What NBA games are scheduled for tonight?"
```

## Example Usage

```bash
# Basic query
python exa_search.py "What NBA games are scheduled for tonight?"

# Specific team query
python exa_search.py "What is the Warriors' current record?"

# Player stats query
python exa_search.py "How many points did Jokic score in his last game?"
```

## Technical Details

- **Model**: GPT-4
- **Search Engine**: Exa Search API
- **Results Limit**: 5 most relevant results per search
- **Error Handling**: Basic error catching and reporting
- **API Framework**: FastAPI

## Next Steps

Future enhancements could include:
- Conversation history support
- Multiple search tools for different data sources
- Enhanced error handling and retry logic
- Response caching for common queries
- Rate limiting and API key authentication