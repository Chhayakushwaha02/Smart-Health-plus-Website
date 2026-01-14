# utils/female_cycle.py
from datetime import datetime, date

def get_cycle_phase(last_period_date, cycle_length=28):
    """
    Returns the current phase of the cycle based on last_period_date.
    Handles last_period_date as string (VARCHAR in DB).
    """
    today = date.today()

    # Convert string to date if needed
    if isinstance(last_period_date, str):
        try:
            last_period_date = datetime.strptime(last_period_date, "%Y-%m-%d").date()
        except ValueError:
            return "Unknown"  # fallback if invalid format

    days_passed = (today - last_period_date).days
    if days_passed < 0:
        return "Unknown"

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

    female_health_summary = f"""- Cycle Length: {record['cycle_length']} days
- Period Duration: {record['period_duration']} days
- Symptoms: {record['symptoms'] or "None"}"""

    # Wellness Suggestions
    if phase == "Menstrual Phase":
        wellness_suggestions = "- Focus on rest, hydration, iron-rich foods, and light stretching."
    elif phase == "Follicular Phase":
        wellness_suggestions = "- Energy levels improve. Good time for planning, workouts, and learning."
    elif phase == "Ovulation Phase":
        wellness_suggestions = "- Peak confidence and strength. Maintain hydration and balanced nutrition."
    else:  # Luteal Phase
        wellness_suggestions = "- Mood may fluctuate. Prioritize sleep, stress control, and self-care."

    # Add common line
    wellness_suggestions += "\n\nFor more suggestions and good advice, click the button below to talk to the chatbot."

    return female_health_summary, wellness_suggestions  # <-- return TWO values
