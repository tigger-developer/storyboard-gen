# ABOUTME: Google GenAI client factory for storyboard-gen.
# ABOUTME: Creates a client configured for Vertex AI or Gemini Developer API.

from google.genai import Client

from storyboard_gen.config import get_env_config


def create_client() -> Client:
    """Create and return a Google GenAI client.

    Uses environment variables to determine the backend:
    - USE_VERTEX=true: Vertex AI with project and location
    - Otherwise: Gemini Developer API with API key

    Raises:
        ValueError: If required credentials are missing.
    """
    config = get_env_config()

    if config["use_vertex"]:
        if not config["project"]:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set when USE_VERTEX=true")
        if not config["location"]:
            raise ValueError(
                "GOOGLE_CLOUD_LOCATION must be set when USE_VERTEX=true"
            )
        return Client(
            vertexai=True,
            project=config["project"],
            location=config["location"],
        )

    if not config["api_key"]:
        raise ValueError(
            "No API credentials found. Set GEMINI_API_KEY or USE_VERTEX=true "
            "with GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION."
        )
    return Client(api_key=config["api_key"])
