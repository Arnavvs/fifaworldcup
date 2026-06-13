import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dashboard" / "data"

# Read the CSV
csv_path = ROOT / "research_ready_dataset" / "wc2026_team_strength.csv"
teams = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        teams.append({
            "team": row["team"],
            "squad_overall": float(row["squad_overall"]),
            "gk_overall": float(row["gk_overall"]) if row["gk_overall"] else None,
            "def_overall": float(row["def_overall"]) if row["def_overall"] else None,
            "mid_overall": float(row["mid_overall"]) if row["mid_overall"] else None,
            "att_overall": float(row["att_overall"]) if row["att_overall"] else None,
            "top3_att_mean": float(row["top3_att_mean"]) if row["top3_att_mean"] else None,
            "squad_caps_total": int(float(row["squad_caps_total"])) if row["squad_caps_total"] else None,
        })

# Sort by squad_overall
teams.sort(key=lambda x: x["squad_overall"], reverse=True)

# Write JS
data = {
    "generated_at": "2026-06-13",
    "teams": teams,
}

(DATA / "team_strength_data.js").write_text(
    f"window.TEAM_STRENGTH = {json.dumps(data, ensure_ascii=False)};\n", encoding="utf-8")

print(f"Wrote team_strength_data.js with {len(teams)} teams")
print("Top 5:", teams[:5])
