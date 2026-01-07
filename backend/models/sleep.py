from database import get_db

def save_sleep(user_id, hours):
    db = get_db()
    db.execute("""
        INSERT INTO sleep (user_id, hours)
        VALUES (?, ?)
    """, (user_id, hours))
    db.commit()
    db.close()

def get_sleep(user_id):
    db = get_db()
    data = db.execute("""
        SELECT hours FROM sleep WHERE user_id=?
    """, (user_id,)).fetchall()
    db.close()
    return data
