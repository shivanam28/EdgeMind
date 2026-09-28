import re

# Layer 1: deterministic safety net. Catches identifiers even if categorization is wrong.
SENSITIVE_KEYWORDS = ("patient", "diagnos", "prescri", "symptom", "medical record", "password", "ssn")
PII_PATTERNS = [
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",      # phone number
    r"[\w.+-]+@[\w-]+\.[\w.]+",                # email
    r"\b\d{3}-\d{2}-\d{4}\b",                  # SSN-style id
]

LOCAL_ONLY_CATEGORIES = {"patient_visit"}
CLOUD_RESIDENT_CATEGORIES = {"public_health_report"}


def classify_data(text: str, category: str) -> str:
    text_lower = text.lower()

    # Rule 1: explicit identifiers or clinical wording never leave the device
    if any(k in text_lower for k in SENSITIVE_KEYWORDS) or any(re.search(p, text_lower) for p in PII_PATTERNS):
        return "LOCAL_ONLY"

    # Rule 2: semantically inferred patient notes stay local
    if category in LOCAL_ONLY_CATEGORIES:
        return "LOCAL_ONLY"

    # Rule 3: aggregate public-health reports go to the cloud
    if category in CLOUD_RESIDENT_CATEGORIES:
        return "CLOUD_RESIDENT"

    # Rule 4: everything else is shareable
    return "HYBRID"