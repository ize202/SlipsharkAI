#!/bin/bash

# Script to set up environment variables for the sports betting research assistant
# Usage: source setup_env.sh [environment]
# Where environment is one of: dev, staging, prod (default: dev)

# Default to dev environment if not specified
ENV=${1:-dev}
echo "Setting up environment variables for $ENV environment"

# Base configuration
export OPENAI_API_KEY="your-openai-api-key"
export PERPLEXITY_API_KEY="your-perplexity-api-key"
export GOALSERVE_API_KEY="your-goalserve-api-key"

# Langfuse configuration
export LANGFUSE_PUBLIC_KEY="your-langfuse-public-key"
export LANGFUSE_SECRET_KEY="your-langfuse-secret-key"
export LANGFUSE_HOST="https://cloud.langfuse.com"

# Environment-specific configuration
case $ENV in
  dev)
    # Development environment - use local Redis
    export REDIS_URL="redis://localhost:6379"
    export SUPABASE_URL="your-dev-supabase-url"
    export SUPABASE_KEY="your-dev-supabase-key"
    export LOG_LEVEL="DEBUG"
    ;;
  staging)
    # Staging environment - use managed Redis
    export REDIS_URL="redis://your-staging-redis-host:6379"
    export SUPABASE_URL="your-staging-supabase-url"
    export SUPABASE_KEY="your-staging-supabase-key"
    export LOG_LEVEL="INFO"
    ;;
  prod)
    # Production environment - use managed Redis with TLS
    export REDIS_URL="rediss://your-production-redis-host:6379"
    export SUPABASE_URL="your-production-supabase-url"
    export SUPABASE_KEY="your-production-supabase-key"
    export LOG_LEVEL="WARNING"
    ;;
  *)
    echo "Unknown environment: $ENV"
    echo "Usage: source setup_env.sh [environment]"
    echo "Where environment is one of: dev, staging, prod"
    return 1
    ;;
esac

# Optional: Set up Redis password if needed
if [ "$ENV" != "dev" ]; then
  export REDIS_PASSWORD="your-redis-password"
fi

# Optional: Set up API rate limiting
export API_RATE_LIMIT="100/minute"

# Print confirmation
echo "Environment variables set up for $ENV environment"
echo "REDIS_URL: $REDIS_URL"
echo "SUPABASE_URL: $SUPABASE_URL"
echo "LOG_LEVEL: $LOG_LEVEL"

# Reminder to use source
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "⚠️  This script should be sourced, not executed directly."
  echo "Please run: source setup_env.sh [$ENV]"
  exit 1
fi 