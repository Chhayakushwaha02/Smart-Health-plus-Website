from database import get_db

def save_mood(user_id, mood):
    db = get_db()
    db.execute("""
        INSERT INTO mood (user_id, mood)
        VALUES (?, ?)
    """, (user_id, mood))
    db.commit()
    db.close()
