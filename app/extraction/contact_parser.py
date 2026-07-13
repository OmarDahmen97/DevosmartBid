import re
import unicodedata

def extract_contact_info(text: str) -> dict:
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phone_match = re.search(r'(\+\d{1,3}[\s.-]?)?\d{2,3}[\s.-]?\d{3}[\s.-]?\d{3,4}', text)
    linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', text)
    github_match = re.search(r'github\.com/[\w-]+', text)

    return {
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "linkedin": linkedin_match.group(0) if linkedin_match else None,
        "github": github_match.group(0) if github_match else None,
    }

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower()


def validate_email_matches_name(email: str, name: str) -> bool:
    if not email or not name:
        return bool(email)

    local_part = _normalize(email.split("@")[0])
    name_tokens = [t for t in _normalize(name).split() if len(t) >= 3]

    return any(token in local_part for token in name_tokens)