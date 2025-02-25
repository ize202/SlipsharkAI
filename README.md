# Sports Betting Research Assistant

A prompt chaining workflow for a sports betting research assistant that analyzes user queries, integrates external data sources, and generates informed betting insights.

## Features

- **Query Analysis**: Extracts intent, entities, and required data sources from user queries
- **Two-Tier Research**:
  - **Quick Research**: Fast, web-based insights using Perplexity AI
  - **Deep Research**: Comprehensive analysis using multiple data sources
- **Data Integration**:
  - Sports data from Goalserve API
  - Web search via Perplexity AI
  - User history from Supabase
- **Robust Caching**: Redis-based caching with in-memory fallback
- **Observability**: Integrated with Langfuse for tracing and monitoring

## Setup

### Prerequisites

- Python 3.11+
- Redis (optional, but recommended)
- Docker and Docker Compose (for containerized setup)

### Environment Variables

Create a `.env` file or use the provided `setup_env.sh` script:

```bash
# Source the environment setup script
source setup_env.sh dev  # Options: dev, staging, prod
```

Required environment variables:

```
OPENAI_API_KEY=your-openai-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key
GOALSERVE_API_KEY=your-goalserve-api-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
REDIS_URL=redis://localhost:6379  # Optional, but recommended
SUPABASE_URL=your-supabase-url    # Optional for development
SUPABASE_KEY=your-supabase-key    # Optional for development
```

### Local Development

#### Option 1: Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

Redis Commander will be available at http://localhost:8081 for monitoring Redis.

#### Option 2: Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (if not using Docker)
redis-server

# Start the API server
uvicorn app.api:app --reload
```

### Production Deployment

#### Using Docker

```bash
# Build the Docker image
docker build -t sports-betting-assistant .

# Run the container
docker run -d -p 8000:8000 \
  --env-file .env.prod \
  --name sports-betting-assistant \
  sports-betting-assistant
```

#### Using Docker Compose

```bash
# Set environment to production
export COMPOSE_FILE=docker-compose.prod.yml

# Start services
docker-compose up -d
```

## API Usage

### Analyze a Query

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I bet on the Lakers to cover the spread against the Warriors?", "force_deep_research": true}'
```

## Architecture

The system follows a prompt chaining workflow:

1. **Query Analysis**: Extracts intent, entities, and required data sources
2. **Research Path Selection**: Determines whether to use quick or deep research
3. **Data Collection**: Gathers data from multiple sources in parallel
4. **Analysis**: Processes collected data to generate insights
5. **Response Generation**: Creates a natural, conversational response

## Caching Strategy

- **Redis**: Primary caching mechanism with configurable TTLs
- **In-Memory Fallback**: Automatic fallback when Redis is unavailable
- **TTL Configuration**: Different TTLs for different types of data:
  - Team IDs: 24 hours
  - Team stats: 1 hour
  - Player stats: 1 hour
  - Injuries: 2 hours
  - Upcoming games: 30 minutes
  - Live scores: 1 minute

## Observability

The system is integrated with Langfuse for observability:

- **Traces**: Each function is decorated with `@observe`
- **Metrics**: Performance metrics are collected automatically
- **Logs**: Structured logging is used throughout

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 