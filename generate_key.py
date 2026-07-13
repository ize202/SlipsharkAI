import base64
import json
import secrets


def generate_api_key(prefix: str = "sk_v1") -> str:
    """Generate a versioned server-to-server API key."""
    random_bytes = secrets.token_bytes(32)
    encoded = base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")
    return f"{prefix}_{encoded}"


if __name__ == "__main__":
    api_key = generate_api_key()
    principals = json.dumps({"local-cli": api_key}, separators=(",", ":"))
    print("Add this server-side value to the local environment or secret store:")
    print(f"SLIPSHARK_API_KEYS={principals}")
