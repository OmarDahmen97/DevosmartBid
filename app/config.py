import os


def get_groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before running the application."
        )
    return key
