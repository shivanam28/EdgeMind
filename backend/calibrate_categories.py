from app.services.categorization_service import score_categories, MIN_SCORE

TESTS = [
    "patient has a sore throat and high temperature",
    "the clinic freezer is broken and vaccines may spoil",
    "malaria cases decreased across the district this quarter",
    "let's have lunch on Friday",
    "banana keyboard purple seventeen",
]

for t in TESTS:
    scores = score_categories(t)
    best = max(scores, key=scores.get)
    print(f"{t}\n   best = {best} ({scores[best]:.3f})")
    print("   all  =", {k: round(v, 3) for k, v in scores.items()})
print("MIN_SCORE =", MIN_SCORE)