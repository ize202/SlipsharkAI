"""
Generate a secure API key for production deployment.

This script:
1. Generates a cryptographically secure random API key
2. Saves it to api_key.txt for reference
3. Outputs the key to the console

Usage:
    python scripts/generate_api_key.py

When deploying to Railway:
1. Run this script to generate a key
2. Add the key as an environment variable named API_KEY in Railway
3. Set ENVIRONMENT=production in Railway
"""
import os
import secrets

# Generate a secure API key
API_KEY = secrets.token_urlsafe(32)

# Save it to a file
with open("api_key.txt", "w") as f:
    f.write(API_KEY)

print(f"API key generated and saved to api_key.txt: {API_KEY}")
print("Use this key in your test requests with header: X-API-Key")
print("\nFor Railway deployment:")
print("1. Add this as an environment variable named API_KEY")
print("2. Set ENVIRONMENT=production")

# Set environment variables (for local testing only)
os.environ["API_KEY"] = API_KEY
os.environ["ENVIRONMENT"] = "development" 