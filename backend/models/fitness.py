from database import get_db

def save_fitness(user_id, steps):
    db = get_db()
    db.execute("""
        INSERT INTO fitness (user_id, steps)
        VALUES (?, ?)
    """, (user_id, steps))
    db.commit()
    db.close()
