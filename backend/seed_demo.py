import requests

API = "http://localhost:8000"

NOTES = [
    "Elderly patient with difficulty breathing, suspected asthma, referred to district hospital",
    "Child with high fever and rash, prescribed paracetamol, follow-up in two days",
    "Diabetic patient blood sugar 280, insulin dose adjusted, revisit next week",
    "Pregnant woman in third trimester with swelling in feet, advised rest and clinic check-up",
    "Patient reports persistent cough, fatigue and mild fever for three days",
    "Clinic running low on bandages and antiseptic, restock needed by Friday",
    "Vaccine refrigerator stopped cooling, technician needed",
    "Health team vehicle scheduled for service on Monday, visits shifted",
    "Regional flu cases up 12 percent this month, summary shared with the health ministry",
    "District vaccination coverage reached 84 percent for children under five",
    "Dengue outbreak reported in two villages, public advisory issued",
    "Team meeting on Thursday at 4 pm",
]

for text in NOTES:
    r = requests.post(f"{API}/memory", json={"text": text}).json()["payload"]
    print(f"{r['security_tier']:15} {r['category']:22} {text[:60]}")