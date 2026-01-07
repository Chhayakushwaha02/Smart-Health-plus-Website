from database import get_db

def create_user(username, email, password):
    db = get_db()
    db.execute("""
        INSERT INTO users (username, email, password)
        VALUES (?, ?, ?)
    """, (username, email, password))
    db.commit()
    db.close()

def get_user(email, password):
    db = get_db()
    user = db.execute("""
        SELECT * FROM users WHERE email=? AND password=?
    """, (email, password)).fetchone()
    db.close()
    return user

def get_user_profile(user_id):
    db = get_db()
    data = db.execute("""
        SELECT * FROM users WHERE id=?
    """, (user_id,)).fetchone()
    db.close()
    return data
