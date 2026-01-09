from database import get_db_connection
from werkzeug.security import generate_password_hash

def init_db():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return

    cursor = conn.cursor()

    # ---------------- USERS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        gender TEXT,
        email TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        role TEXT DEFAULT 'user',
        auth_provider TEXT DEFAULT 'manual',
        is_active INTEGER DEFAULT 1,  -- 1 = Active, 0 = Inactive
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- SLEEP DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sleep_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        hours INTEGER,
        quality TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- STRESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stress_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        level TEXT,
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- HYDRATION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hydration_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        level TEXT DEFAULT 'Unknown',  -- Low / Moderate / High
        reason TEXT DEFAULT 'Unspecified',  -- Required for Low / Moderate
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- MOOD DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mood TEXT,
        reason TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- FITNESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fitness_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        minutes INTEGER DEFAULT 0,
        steps INTEGER DEFAULT 0,
        workout_type TEXT DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- NUTRITION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quality TEXT DEFAULT 'Unknown',  -- Good / Average / Poor
        reason TEXT DEFAULT 'Unspecified',  -- Only if Average / Poor
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- HEALTH DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        input_value TEXT,
        recommendation TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- REMINDERS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reminder_type TEXT,
        reminder_time TEXT,
        reminder_date TEXT,
        reminder_email TEXT,
        reminder_phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)


   # ---------------- FEEDBACK (FIXED) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,

        -- STRICT rating: only 1 to 5 allowed
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),

        usefulness TEXT,
        feedback_type TEXT,
        improve TEXT,
        feature TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)


    # ---------------- DEFAULT ADMIN ----------------
    cursor.execute("SELECT * FROM users WHERE role='admin'")
    admin_exists = cursor.fetchone()
    if not admin_exists:
        admin_email = "admin0202@gmail.com"
        admin_password = generate_password_hash("Admin@0202")
        admin_name = "Admin"
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (admin_name, admin_email, admin_password, "admin")
        )
        print("Default admin created:", admin_email)

    # ---------------- PERIOD TRACKING ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS period_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        last_period_date TEXT NOT NULL,
        cycle_length INTEGER DEFAULT 28,
        period_duration INTEGER DEFAULT 5,
        symptoms TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("SQLite database initialized successfully with all tables!")

if __name__ == "__main__":
    init_db()
