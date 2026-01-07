from database import get_db
import json

def save_stress(user_id, data):
    db = get_db()
    db.execute("""
        INSERT INTO stress (user_id, data)
        VALUES (?, ?)
    """, (user_id, json.dumps(data)))
    db.commit()
    db.close()
from database import get_db
import json

def save_stress(user_id, data):
    db = get_db()
    db.execute(
        "INSERT INTO stress (user_id, data) VALUES (?, ?)",
        (user_id, json.dumps(data))
    )
    db.commit()
    db.close()
