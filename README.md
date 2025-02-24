# Sports Betting Research Assistant

An AI-powered sports betting research assistant that provides quick and deep research for betting queries.

## Features

- **Quick Research**: Fast, concise answers to betting questions using Perplexity AI
- **Deep Research**: Comprehensive analysis with insights, risk factors, and recommended bets
- **Caching**: Redis-based caching for improved performance and reduced API costs
- **Observability**: Langfuse integration for monitoring and tracing
- **Modern UI**: Clean, responsive interface for easy interaction

## Beta Testing Instructions

### Prerequisites

- Python 3.9+
- Redis (optional, but recommended for caching)
- API keys for:
  - OpenAI
  - Perplexity AI
  - Supabase (optional)
  - Goalserve (optional)
  - Langfuse (optional)

### Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd SlipsharkAI
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables by copying the example file:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_key
   PERPLEXITY_API_KEY=your_perplexity_key
   REDIS_URL=redis://localhost:6379  # Optional
   SUPABASE_URL=your_supabase_url    # Optional
   SUPABASE_KEY=your_supabase_key    # Optional
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key  # Optional
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key  # Optional
   ```

### Running the Application

1. Start the application:
   ```
   uvicorn app.api:app --reload
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

3. Enter a sports betting query and test both quick and deep research modes.

### Beta Testing Feedback

Please provide feedback on:

1. **Accuracy**: How accurate and helpful are the research results?
2. **Speed**: How fast are the responses for both quick and deep research?
3. **User Experience**: Is the interface intuitive and easy to use?
4. **Bugs**: Any issues or errors encountered during testing?
5. **Feature Requests**: What additional features would you like to see?

Send your feedback to: [your-email@example.com]

## Cache Management

The application includes Redis caching to improve performance and reduce API costs. Cache settings can be adjusted in the code:

- Quick research results: 30-minute TTL
- Sports API data: Various TTLs based on data type
- User data: 15-minute to 1-hour TTL

To clear the cache via API:
```
curl -X POST http://localhost:8000/cache/clear -H "Content-Type: application/json" -d '{"pattern": "*"}'
```

To view cache statistics:
```
curl http://localhost:8000/cache/stats
```

## Architecture

The application follows a modular architecture:

- **API Layer**: FastAPI endpoints for user interaction
- **Workflow Layer**: Orchestrates the research process
- **Service Layer**: Integrates with external APIs
- **Model Layer**: Defines data structures
- **Utility Layer**: Provides shared functionality like caching

## License

[Your License] 