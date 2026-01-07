# utils/health_score.py
from database import get_db_connection
import json

def calculate_health_score(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return 0, "No Data", "Please add your health data to generate score."

    latest = {}
    for row in rows:
        if row["category"] not in latest:
            try:
                latest[row["category"]] = json.loads(row["input_value"])
            except:
                latest[row["category"]] = row["input_value"]

    modules = ["sleep", "hydration", "nutrition", "fitness", "stress", "mood"]
    filled_modules = sum(1 for m in modules if m in latest and latest[m] not in [None, "", {}])

    score_per_module = 100 // len(modules)
    score = filled_modules * score_per_module

    if score < 40:
        wellness = "Needs Improvement"
        tip = "You have provided limited health data. Add more details to get accurate insights."
    elif score < 70:
        wellness = "Average"
        tip = "Good start! Try completing all health modules for better wellness tracking."
    else:
        wellness = "Excellent"
        tip = "Great work! Keep maintaining your healthy lifestyle."

    return score, wellness, tip
