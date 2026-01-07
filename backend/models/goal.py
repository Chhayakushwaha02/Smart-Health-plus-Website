from database import get_db

def save_goal(user_id, goal_text):
    db = get_db()
    db.execute("""
        INSERT INTO goals (user_id, goal)
        VALUES (?, ?)
    """, (user_id, goal_text))
    db.commit()
    db.close()
