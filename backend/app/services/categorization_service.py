from app.services.embedding_service import embed
from app.services.qdrant_service import cosine_similarity

CATEGORY_EXAMPLES = {
    "patient_visit": [
        "patient reports cough, fever and fatigue during home visit",
        "diagnosis, symptoms and treatment notes for a patient",
        "prescribed medication and scheduled a follow-up for the patient",
        "blood pressure and vital signs recorded for a patient",
    ],
    "clinic_ops": [
        "clinic is running low on bandages and antiseptic, restock needed",
        "medical equipment maintenance and supply orders for the clinic",
        "staff schedule and vehicle logistics for the health team",
    ],
    "public_health_report": [
        "regional flu cases increased this month, report shared with the health ministry",
        "vaccination coverage statistics for the district",
        "disease outbreak summary published for public health authorities",
    ],
    "general": [
        "reminder about the team meeting on Thursday",
        "general notes, lunch plans and casual reminders",
    ],
}

MIN_SCORE = 0.5  # first guess; tuned with calibrate_categories.py

_example_vectors = None


def _get_example_vectors():
    global _example_vectors
    if _example_vectors is None:
        _example_vectors = {
            cat: [embed(example) for example in examples]
            for cat, examples in CATEGORY_EXAMPLES.items()
        }
    return _example_vectors


def score_categories(text: str) -> dict:
    """Best similarity to any example sentence, per category."""
    text_vector = embed(text)
    return {
        cat: max(cosine_similarity(text_vector, ref) for ref in refs)
        for cat, refs in _get_example_vectors().items()
    }


def auto_categorize(text: str) -> str:
    scores = score_categories(text)
    best = max(scores, key=scores.get)
    return best if scores[best] >= MIN_SCORE else "general"