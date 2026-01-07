# ================================
# SMART HEALTH PLUS - RECOMMENDATIONS
# Rule-based intelligent logic
# ================================

# -------- SLEEP --------
def sleep_recommendation(hours):
    if hours < 6:
        return "You are sleeping too little. Aim for at least 7–8 hours for proper recovery."
    elif 6 <= hours < 7:
        return "Try to increase your sleep slightly for better energy."
    elif 7 <= hours <= 8:
        return "Excellent sleep duration! Keep maintaining this routine."
    else:
        return "You are sleeping well, but avoid oversleeping regularly."

# -------- STRESS --------
def stress_recommendation(level):
    if level == "High":
        return "Your stress level is high. Try meditation, breathing exercises, or short walks."
    elif level == "Medium":
        return "Moderate stress detected. Take short breaks and stay relaxed."
    else:
        return "Great! Your stress level is well managed."

# -------- FITNESS --------
def fitness_recommendation(steps):
    if steps < 3000:
        return "You are not very active today. Try walking more or doing light exercise."
    elif 3000 <= steps < 7000:
        return "Good activity level. Try to push a little more for better fitness."
    elif 7000 <= steps <= 10000:
        return "Excellent fitness activity! You are meeting daily activity goals."
    else:
        return "Amazing! You are highly active today. Keep it up, but don’t overdo it."

# -------- NUTRITION --------
def nutrition_recommendation(calories):
    if calories < 1500:
        return "Your calorie intake seems low. Ensure you eat balanced meals."
    elif 1500 <= calories <= 2200:
        return "Good nutrition intake. Maintain a balanced diet."
    else:
        return "High calorie intake detected. Try to avoid excess junk food."

# -------- HYDRATION --------
def hydration_recommendation(glasses):
    if glasses < 4:
        return "You are drinking very little water. Increase your water intake."
    elif 4 <= glasses < 8:
        return "You are doing okay, but try to drink at least 8 glasses a day."
    else:
        return "Excellent hydration level! Keep drinking enough water."

# -------- MOOD --------
def mood_recommendation(mood):
    if mood == "Sad":
        return "It’s okay to feel sad. Talk to someone you trust or write your feelings."
    elif mood == "Anxious":
        return "Try deep breathing or relaxation techniques to calm your mind."
    elif mood == "Happy":
        return "Great mood! Keep doing what makes you happy."
    else:
        return "Stay balanced and take care of your emotional health."

# -------- GOALS --------
def goal_recommendation(status):
    if status == "Not Started":
        return "Start small. Even small progress helps achieve big goals."
    elif status == "In Progress":
        return "You’re doing well. Stay consistent and focused."
    else:
        return "Congratulations! You achieved your goal. Set a new one to stay motivated."

# -------- health score --------
def calculate_health_score(user_data):
    score = 0

    # Sleep
    sleep = user_data.get("sleep", 0)
    if sleep >= 7:
        score += 20
    elif sleep >= 5:
        score += 10

    # Hydration
    water = user_data.get("hydration", 0)
    if water >= 3:
        score += 20
    elif water >= 2:
        score += 10

    # Fitness
    fitness = user_data.get("fitness", 0)
    if fitness >= 30:
        score += 20
    elif fitness >= 15:
        score += 10

    # Stress
    stress = user_data.get("stress", 10)
    if stress <= 3:
        score += 20
    elif stress <= 6:
        score += 10

    # Mood
    mood = user_data.get("mood", "")
    if mood.lower() in ["happy", "positive", "good"]:
        score += 20
    elif mood.lower() in ["neutral", "okay"]:
        score += 10

    return score


def wellness_index(score):
    if score >= 80:
        return "Excellent 🌟"
    elif score >= 60:
        return "Good 🙂"
    elif score >= 40:
        return "Fair 😐"
    else:
        return "Poor 😟"
