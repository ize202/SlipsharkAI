# Railway Deployment Guide

This guide provides instructions for deploying the Sports Research API on Railway with rate limiting enabled to control costs.

## Prerequisites

- A Railway account
- Access to the GitHub repository
- Redis instance (optional but recommended for production)

## Environment Variables

The following environment variables should be set in your Railway project:

### Required Variables

- `OPENAI_API_KEY`: Your OpenAI API key
- `API_KEY`: Your API key for authenticating requests
- `ENVIRONMENT`: Set to `production` for Railway deployment

### Rate Limiting Variables

- `DEFAULT_RATE_LIMIT`: Default rate limit for all endpoints (default: "60/minute")
- `ANALYZE_RATE_LIMIT`: Rate limit for the /analyze endpoint (default: "30/minute")
- `EXTEND_RATE_LIMIT`: Rate limit for the /extend endpoint (default: "10/minute")

### Logging Configuration

- `LOG_LEVEL`: Logging level (default: "INFO", options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
- `ENABLE_JSON_LOGGING`: Whether to enable JSON-formatted logging for better log aggregation (default: "false")

### Redis Configuration (Recommended)

- `REDIS_URL`: URL for your Redis instance (format: `redis://username:password@host:port`)

## Deployment Steps

1. **Create a new project in Railway**

   - Go to [Railway](https://railway.app/) and create a new project
   - Choose "Deploy from GitHub repo"
   - Select your repository

2. **Add a Redis service (Recommended)**

   - Click "New Service" and select "Redis"
   - This will be used for rate limiting and caching

3. **Configure environment variables**

   - Go to the "Variables" tab in your project
   - Add all the required environment variables listed above
   - If you added a Redis service, Railway will automatically set the `REDIS_URL` variable

4. **Deploy the application**

   - Railway will automatically deploy your application
   - You can trigger a manual deployment by pushing to your repository

## Monitoring Rate Limits

The API includes built-in monitoring for rate limits and usage:

- **Usage Statistics**: Access `/admin/usage` with your API key to view usage statistics
- **Logs**: Check the Railway logs for rate limit exceeded messages
- **Redis**: If using Redis, you can inspect the rate limit keys directly

## Adjusting Rate Limits

Rate limits can be adjusted by changing the environment variables:

- Format: `"number/timeunit"` (e.g., `"60/minute"`, `"1000/hour"`, `"10000/day"`)
- Timeunits: `second`, `minute`, `hour`, `day`

For example, to allow 100 requests per minute to the analyze endpoint:

```
ANALYZE_RATE_LIMIT=100/minute
```

### Handling Viral Growth

If your app experiences viral growth, you can quickly adjust rate limits without code changes:

#### Option 1: Quick Environment Variable Updates

1. Log in to your Railway dashboard
2. Navigate to your project
3. Go to the "Variables" tab
4. Update the rate limit variables with higher values:
   ```
   DEFAULT_RATE_LIMIT="200/minute"
   ANALYZE_RATE_LIMIT="100/minute"
   EXTEND_RATE_LIMIT="50/minute"
   ```
5. Railway will automatically restart your service with the new limits

This is the fastest way to respond to increased demand without any code changes.

#### Option 2: Implement Tiered Rate Limiting

For different user tiers with different rate limits:

1. Create multiple API keys for different user tiers
2. Add tier-specific environment variables:
   ```
   PREMIUM_DEFAULT_RATE_LIMIT="300/minute"
   PREMIUM_ANALYZE_RATE_LIMIT="150/minute"
   PREMIUM_EXTEND_RATE_LIMIT="75/minute"
   
   BASIC_DEFAULT_RATE_LIMIT="100/minute"
   BASIC_ANALYZE_RATE_LIMIT="50/minute"
   BASIC_EXTEND_RATE_LIMIT="25/minute"
   ```
3. Distribute different API keys to users based on their tier
4. Update the rate limit configuration to check for the user's tier and apply the appropriate limit

#### Option 3: Dynamic Rate Limiting

For more sophisticated automatic adjustments:

1. Create a scheduled task (using Railway cron jobs or a separate service) that:
   - Runs every hour or at specific intervals
   - Analyzes usage patterns from Redis usage tracking data
   - Calculates optimal rate limits based on current load and time of day
   - Uses Railway's API to programmatically update environment variables
2. Implement time-based rate limiting:
   - Higher limits during off-peak hours
   - Lower limits during peak usage times
3. Set up alerts when usage approaches thresholds to proactively adjust limits

## Error Handling and Debugging

The API includes comprehensive error handling and logging to make debugging easier:

### Standardized Error Responses

All API errors follow a standardized format:

```json
{
  "error": {
    "id": "unique-error-id",
    "timestamp": "2023-06-01T12:34:56.789Z",
    "status_code": 400,
    "error_code": "validation_error",
    "message": "Human-readable error message",
    "details": {
      "additional": "error details"
    }
  }
}
```

### Request Tracking

- Each request is assigned a unique `X-Request-ID` header
- This ID is included in all logs related to the request
- Include this ID when reporting issues for faster troubleshooting

### Logging Configuration

Adjust logging behavior with environment variables:

- Set `LOG_LEVEL=DEBUG` for more detailed logs during troubleshooting
- Enable `ENABLE_JSON_LOGGING=true` for structured logs that can be parsed by log aggregation tools

### Common Error Codes

- `validation_error`: Request validation failed (HTTP 422)
- `authentication_error`: Authentication failed (HTTP 401)
- `authorization_error`: Not authorized to access resource (HTTP 403)
- `rate_limit_exceeded`: Rate limit exceeded (HTTP 429)
- `external_api_error`: Error from external API (HTTP 502)

### Viewing Logs in Railway

1. Go to your Railway project dashboard
2. Click on your service
3. Go to the "Logs" tab
4. Use the search functionality to filter logs by:
   - Request ID
   - Error code
   - Endpoint path

## Troubleshooting

### Rate Limit Errors

If clients are receiving 429 Too Many Requests errors:

1. Check the current rate limits in the environment variables
2. Consider increasing the limits if necessary
3. Implement client-side retry logic with exponential backoff

### Redis Connection Issues

If Redis connection fails:

1. The system will fall back to in-memory rate limiting
2. Check the `REDIS_URL` environment variable
3. Verify that the Redis service is running

### API Errors

If you're seeing unexpected errors:

1. Check the logs for the specific error details using the error ID
2. Verify that all required environment variables are set correctly
3. For external API errors, check the status of the dependent services

## Best Practices

1. **Start Conservative**: Begin with lower rate limits and increase as needed
2. **Monitor Usage**: Regularly check the usage statistics to understand patterns
3. **Adjust Dynamically**: Adjust rate limits based on actual usage and cost considerations
4. **Use Redis**: For production, always use Redis for rate limiting to ensure consistency across instances
5. **Enable JSON Logging**: In production, enable JSON logging for better log aggregation
6. **Set Appropriate Log Level**: Use INFO in production, DEBUG for troubleshooting

## API Endpoints

- `POST /analyze`: Analyze a sports betting query (rate limited to control costs)
- `POST /extend`: Extend a quick research into deep research (heavily rate limited)
- `GET /cache/stats`: Get cache statistics
- `POST /cache/clear`: Clear cache entries
- `POST /admin/usage`: Get API usage statistics (admin only)
- `GET /health`: Health check endpoint for monitoring

## Cost Control Strategies

1. **Rate Limiting**: Prevents excessive API calls
2. **Caching**: Reduces duplicate API calls
3. **Tiered Access**: Implement different rate limits for different API keys
4. **Usage Monitoring**: Track usage to identify patterns and optimize costs 