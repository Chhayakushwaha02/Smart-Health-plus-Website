# ---------------- PROFILE ----------------
@app.route("/profile")
@login_required
def profile():
    user_id = session.get("user_id")

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ----------------- USER INFO -----------------
    cursor.execute(
        "SELECT name, email, mobile, age, gender FROM users WHERE id=?",
        (user_id,)
    )
    user = cursor.fetchone()

    # ----------------- TIMELINE DATA -----------------
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT category, input_value, recommendation, created_at
        FROM health_data
        WHERE user_id=? AND created_at >= ?
        ORDER BY created_at DESC
    """, (user_id, seven_days_ago))

    rows = cursor.fetchall()

    timeline_data = defaultdict(list)

    for row in rows:
        day = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%d %b %Y")

        category = row["category"]
        value = row["input_value"]

        # ---------------- FITNESS ----------------
        if category == "fitness":
            try:
                d = json.loads(value)
                value = (
                    f"Workout Minutes: {d.get('minutes', 0)} mins | "
                    f"Workout Type: {d.get('type', 'Not specified')} | "
                    f"Daily Steps: {d.get('steps', 0)} steps"
                )
            except:
                pass

        # ---------------- NUTRITION ----------------
        elif category == "nutrition":
            try:
                d = json.loads(value)
                value = (
                    f"Nutrition Quality: {d.get('quality', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- HYDRATION ----------------
        elif category == "hydration":
            try:
                d = json.loads(value)
                value = (
                    f"Hydration Level: {d.get('level', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- SLEEP ----------------
        elif category == "sleep":
            try:
                d = json.loads(value)
                value = (
                    f"Sleep Duration: {d.get('hours', 0)} hours | "
                    f"Quality: {d.get('quality', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- STRESS ----------------
        elif category == "stress":
            try:
                d = json.loads(value)
                value = (
                    f"Stress Level: {d.get('level', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- MOOD ----------------
        elif category == "mood":
            try:
                d = json.loads(value)
                value = (
                    f"Mood: {d.get('mood', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        timeline_data[day].append({
            "category": category,
            "input_value": value,
            "recommendation": row["recommendation"]
        })


    # ---------------- HELPER FUNCTION ----------------
    def calculate_summary(data_dict):
        summary = {
            "dates": [], "sleep": [], "hydration": [], "nutrition": [],
            "fitness_minutes": [], "fitness_steps": [],
            "stress": [], "mood": [],
            "health_score": [], "summary_text": ""
        }

        for day, v in data_dict.items():
            summary["dates"].append(day)
            sleep_avg = mean(v["sleep"]) if v["sleep"] else 0
            hydration_sum = sum(v["hydration"])
            nutrition_avg = mean(v["nutrition"]) if v["nutrition"] else 0
            fitness_minutes_sum = sum(v["fitness_minutes"])
            fitness_steps_sum = sum(v["fitness_steps"])
            stress_avg = mean(v["stress"]) if v["stress"] else 0
            mood_avg = mean(v["mood"]) if v["mood"] else 0

            health_score = round((sleep_avg*10 + hydration_sum*5 + nutrition_avg*10 + 
                                  fitness_minutes_sum*0.5 + (5-stress_avg)*10 + mood_avg*10) / 6, 1)

            summary["sleep"].append(sleep_avg)
            summary["hydration"].append(hydration_sum)
            summary["nutrition"].append(nutrition_avg)
            summary["fitness_minutes"].append(fitness_minutes_sum)
            summary["fitness_steps"].append(fitness_steps_sum)
            summary["stress"].append(stress_avg)
            summary["mood"].append(mood_avg)
            summary["health_score"].append(health_score)

        if summary["dates"]:
            summary["summary_text"] = (
                f"Over this period, your average sleep was {round(mean(summary['sleep']),1)} hrs/day. "
                f"Hydration totaled {sum(summary['hydration'])} liters. "
                f"Nutrition quality averaged {round(mean(summary['nutrition']),1)}. "
                f"Fitness included {sum(summary['fitness_minutes'])} mins and {sum(summary['fitness_steps'])} steps. "
                f"Stress averaged {round(mean(summary['stress']),1)}, mood stability was {round(mean(summary['mood']),1)}. "
                f"Overall health score indicates a trend of improvement. "
                f"Keep tracking to maintain and enhance your wellness!"
            )
        return summary

    # ---------------- WEEKLY SUMMARY ----------------
    weekly_data = defaultdict(lambda: {
        "sleep": [], "hydration": [], "nutrition": [],
        "fitness_minutes": [], "fitness_steps": [],
        "stress": [], "mood": []
    })

    cursor.execute("""
        SELECT category, input_value, created_at
        FROM health_data
        WHERE user_id=? AND DATE(created_at) >= DATE('now','-7 day')
    """, (user_id,))
    weekly_rows = cursor.fetchall()

    for r in weekly_rows:
        day = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%d %b")
        if r["category"] == "fitness":
            try:
                d = json.loads(r["input_value"])
                weekly_data[day]["fitness_minutes"].append(d.get("minutes", 0))
                weekly_data[day]["fitness_steps"].append(d.get("steps", 0))
            except:
                pass
        else:
            try:
                weekly_data[day][r["category"]].append(float(r["input_value"]))
            except:
                pass

    weekly_summary = calculate_summary(weekly_data)

    # ---------------- MONTHLY SUMMARY ----------------
    monthly_data = defaultdict(lambda: {
        "sleep": [], "hydration": [], "nutrition": [],
        "fitness_minutes": [], "fitness_steps": [],
        "stress": [], "mood": []
    })

    cursor.execute("""
        SELECT category, input_value, created_at
        FROM health_data
        WHERE user_id=? AND DATE(created_at) >= DATE('now','-30 day')
    """, (user_id,))
    monthly_rows = cursor.fetchall()

    for r in monthly_rows:
        day = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%d %b")
        if r["category"] == "fitness":
            try:
                d = json.loads(r["input_value"])
                monthly_data[day]["fitness_minutes"].append(d.get("minutes", 0))
                monthly_data[day]["fitness_steps"].append(d.get("steps", 0))
            except:
                pass
        else:
            try:
                monthly_data[day][r["category"]].append(float(r["input_value"]))
            except:
                pass

    monthly_summary = calculate_summary(monthly_data)

    cursor.close()
    conn.close()

    # ---------------- RENDER TEMPLATE ----------------
    return render_template(
        "profile.html",
        name=user["name"],
        email=user["email"],
        mobile=user["mobile"],  # ✅ now mobile is passed to template
        age=user["age"],
        gender=user["gender"],
        timeline_data=timeline_data,  # now a dict grouped by date
        weekly_summary=weekly_summary if weekly_summary["dates"] else None,
        monthly_summary=monthly_summary if monthly_summary["dates"] else None
    )
