LOCAL_ONLY_KEYWORDS = {"password", "salary", "confidential", "ssn", "medical"}
CLOUD_RESIDENT_CATEGORIES = {"global_report", "public_announcement"}

def classify_data(text: str, category: str) -> str:
    text_lower = text.lower()

    # Rule 1: sensitive content never leaves the device
    if any(keyword in text_lower for keyword in LOCAL_ONLY_KEYWORDS):
        return "LOCAL_ONLY"

    # Rule 2: explicitly global/shared categories go straight to cloud
    if category in CLOUD_RESIDENT_CATEGORIES:
        return "CLOUD_RESIDENT"

    # Rule 3: everything else is shared but not high-priority
    return "HYBRID"