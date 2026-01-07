from database import get_db

def add_glass(user_id):
    db = get_db()
    db.execute("""
        INSERT INTO hydration (user_id, glasses)
        VALUES (?, 1)
    """, (user_id,))
    db.commit()
    db.close()
