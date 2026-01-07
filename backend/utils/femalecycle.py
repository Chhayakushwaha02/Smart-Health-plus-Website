from datetime import date, datetime

def get_cycle_phase(last_period_date, cycle_length=28):
    """
    Returns the current phase of the cycle based on the last period date.
    """
    today = date.today()
    if isinstance(last_period_date, str):
        last_period_date = datetime.strptime(last_period_date, "%Y-%m-%d").date()

    days_passed = (today - last_period_date).days
    if days_passed < 0:
        return "unknown"

    day_in_cycle = days_passed % cycle_length

    if day_in_cycle <= 5:
        return "Menstrual Phase"
    elif day_in_cycle <= 13:
        return "Follicular Phase"
    elif day_in_cycle <= 16:
        return "Ovulation Phase"
    else:
        return "Luteal Phase"

def generate_female_health_summary(record):
    phase = get_cycle_phase(record["last_period_date"], int(record["cycle_length"]))

    summary = f"""
Female Health Summary:
- Current Cycle Phase: {phase}
- Cycle Length: {record["cycle_length"]} days
- Period Duration: {record["period_duration"]} days
- Symptoms: {record["symptoms"] or "None"}

Wellness Suggestions:
"""

    if phase == "Menstrual Phase":
        summary += "- Focus on rest, hydration, iron-rich foods, and light stretching."
    elif phase == "Follicular Phase":
        summary += "- Energy levels improve. Good time for planning, workouts, and learning."
    elif phase == "Ovulation Phase":
        summary += "- Peak confidence and strength. Maintain hydration and balanced nutrition."
    else:
        summary += "- Mood may fluctuate. Prioritize sleep, stress control, and self-care."

    return summary.strip()
