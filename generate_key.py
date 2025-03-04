import secrets
import base64

def generate_api_key(prefix="sk_v1"):
    """Generate a secure API key with a versioned prefix"""
    # Generate 32 random bytes and encode them in base64
    random_bytes = secrets.token_bytes(32)
    encoded = base64.b64encode(random_bytes).decode('utf-8')
    # Create key with prefix (e.g., sk_v1_...)
    return f"{prefix}_{''.join(encoded.split('='))}"

if __name__ == "__main__":
    api_key = generate_api_key()
    print("\nGenerated API Key:")
    print("------------------")
    print(api_key)
    print("\nAdd this to your .env file as:")
    print("------------------")
    print(f"API_KEY={api_key}")
    print("\nNOTE: This new key format (sk_v1_) will invalidate any old keys.")
    print("------------------\n") 