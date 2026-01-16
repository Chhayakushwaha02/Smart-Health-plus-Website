from database import get_db_connection
from werkzeug.security import generate_password_hash

def init_db():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database.")
        return

    cursor = conn.cursor()

    # ---------------- USERS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT,
        email TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        role TEXT DEFAULT 'user',
        auth_provider TEXT DEFAULT 'manual',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- SLEEP DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sleep_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        hours INTEGER,
        quality TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- STRESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stress_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        level TEXT,
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- HYDRATION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hydration_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        level TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- MOOD DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        mood TEXT,
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- FITNESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fitness_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        minutes INTEGER DEFAULT 0,
        steps INTEGER DEFAULT 0,
        workout_type TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- NUTRITION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        quality TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- HEALTH DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_data (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        category TEXT,
        input_value TEXT,
        recommendation TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- REMINDERS (TIME FIXED) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        reminder_type TEXT,
        reminder_at TIMESTAMPTZ NOT NULL,
        reminder_email TEXT,
        reminder_phone TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- FEEDBACK ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        usefulness TEXT,
        feedback_type TEXT,
        improve TEXT,
        feature TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- PERIOD TRACKING ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS period_tracking (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        last_period_date DATE NOT NULL,
        cycle_length INTEGER DEFAULT 28,
        period_duration INTEGER DEFAULT 5,
        symptoms TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- DEFAULT ADMIN ----------------
    cursor.execute("SELECT 1 FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES (%s, %s, %s, %s)
        """, (
            "Admin",
            "admin0202@gmail.com",
            generate_password_hash("Admin@0202"),
            "admin"
        ))
        print("✅ Default admin created")

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ PostgreSQL database initialized successfully")

if __name__ == "__main__":
    init_db()
