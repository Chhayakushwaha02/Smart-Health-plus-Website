from database import get_db

def save_nutrition(user_id, calories):
    db = get_db()
    db.execute("""
        INSERT INTO nutrition (user_id, calories)
        VALUES (?, ?)
    """, (user_id, calories))
    db.commit()
    db.close()
