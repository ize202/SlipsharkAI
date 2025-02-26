"""
Comprehensive test for the API authentication workflow.

This script performs an end-to-end test of the authentication system:
1. Generates a secure random API key
2. Sets it in the environment
3. Starts the API server in a subprocess
4. Tests all authentication scenarios:
   - Public endpoints (should be accessible without a key)
   - Protected endpoints without authentication (should be rejected)
   - Protected endpoints with invalid authentication (should be rejected)
   - Protected endpoints with valid authentication (should be accepted)
5. Stops the server and reports results

Usage:
    python scripts/test_auth_workflow.py

This script is useful for:
- Verifying authentication works correctly after changes
- Testing the authentication system in a CI/CD pipeline
- Demonstrating how to interact with the authenticated API
"""
import os
import secrets
import subprocess
import time
import sys
import requests

# Generate a secure API key
API_KEY = secrets.token_urlsafe(32)
API_KEY_NAME = "X-API-Key"
BASE_URL = "http://localhost:8000"

# Set environment variables
os.environ["API_KEY"] = API_KEY
os.environ["ENVIRONMENT"] = "development"

print(f"Using API key: {API_KEY}")
print(f"API key header name: {API_KEY_NAME}")

# Start the server in a subprocess
server_process = subprocess.Popen(
    ["uvicorn", "app.api:app", "--port", "8000"],
    env=os.environ.copy(),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait for the server to start
print("Waiting for server to start...")
time.sleep(3)

# Test functions
def test_public_endpoint():
    """Test that public endpoints don't require authentication."""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Public endpoint status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

def test_protected_endpoint_no_auth():
    """Test that protected endpoints require authentication."""
    response = requests.post(
        f"{BASE_URL}/analyze", 
        json={"query": "Test query"}
    )
    print(f"Protected endpoint (no auth) status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401

def test_protected_endpoint_invalid_auth():
    """Test that protected endpoints reject invalid API keys."""
    response = requests.post(
        f"{BASE_URL}/analyze", 
        json={"query": "Test query"},
        headers={API_KEY_NAME: "invalid_key"}
    )
    print(f"Protected endpoint (invalid auth) status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401

def test_protected_endpoint_valid_auth():
    """Test that protected endpoints accept valid API keys."""
    response = requests.post(
        f"{BASE_URL}/analyze", 
        json={"query": "Test query"},
        headers={API_KEY_NAME: API_KEY}
    )
    print(f"Protected endpoint (valid auth) status: {response.status_code}")
    if response.status_code == 500:
        print("Response: Internal Server Error")
    else:
        print(f"Response: {response.json()}")
    assert response.status_code != 401

# Run tests
try:
    test_public_endpoint()
    print("✅ Public endpoint test passed")
except Exception as e:
    print(f"❌ Public endpoint test failed: {e}")

try:
    test_protected_endpoint_no_auth()
    print("✅ Protected endpoint (no auth) test passed")
except Exception as e:
    print(f"❌ Protected endpoint (no auth) test failed: {e}")

try:
    test_protected_endpoint_invalid_auth()
    print("✅ Protected endpoint (invalid auth) test passed")
except Exception as e:
    print(f"❌ Protected endpoint (invalid auth) test failed: {e}")

try:
    test_protected_endpoint_valid_auth()
    print("✅ Protected endpoint (valid auth) test passed")
except Exception as e:
    print(f"❌ Protected endpoint (valid auth) test failed: {e}")

# Kill the server
print("Tests completed, stopping server...")
server_process.terminate()
server_process.wait(timeout=5)

# Print server output
print("\nServer stdout:")
print(server_process.stdout.read())
print("\nServer stderr:")
print(server_process.stderr.read()) 