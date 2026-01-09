# backend/init_db.py
from database import get_db_connection
from werkzeug.security import generate_password_hash


def init_db():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to PostgreSQL")
        return

    try:
        with conn:
            with conn.cursor() as cursor:

                # ---------------- USERS ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    age INTEGER,
                    gender VARCHAR(20),
                    email VARCHAR(255) UNIQUE,
                    mobile VARCHAR(20),
                    password TEXT,
                    role VARCHAR(20) DEFAULT 'user',
                    auth_provider VARCHAR(20) DEFAULT 'manual',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- SLEEP DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sleep_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    hours INTEGER,
                    quality VARCHAR(50) DEFAULT 'Unknown',
                    reason TEXT DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- STRESS DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS stress_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    level VARCHAR(50),
                    reason TEXT DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- HYDRATION DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS hydration_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    level VARCHAR(50) DEFAULT 'Unknown',
                    reason TEXT DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- MOOD DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS mood_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    mood VARCHAR(50),
                    reason TEXT DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- FITNESS DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS fitness_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    minutes INTEGER DEFAULT 0,
                    steps INTEGER DEFAULT 0,
                    workout_type VARCHAR(100) DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- NUTRITION DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    quality VARCHAR(50) DEFAULT 'Unknown',
                    reason TEXT DEFAULT 'Unspecified',
                    suggestion TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- HEALTH DATA ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    category VARCHAR(100),
                    input_value TEXT,
                    recommendation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- REMINDERS ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    reminder_type VARCHAR(100),
                    reminder_time VARCHAR(20),
                    reminder_date VARCHAR(20),
                    reminder_email VARCHAR(255),
                    reminder_phone VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- FEEDBACK ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
                    usefulness TEXT,
                    feedback_type TEXT,
                    improve TEXT,
                    feature TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- PERIOD TRACKING ----------------
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS period_tracking (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    last_period_date DATE NOT NULL,
                    cycle_length INTEGER DEFAULT 28,
                    period_duration INTEGER DEFAULT 5,
                    symptoms TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # ---------------- DEFAULT ADMIN ----------------
                cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                admin_exists = cursor.fetchone()

                if not admin_exists:
                    cursor.execute(
                        """
                        INSERT INTO users (name, email, password, role)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            "Admin",
                            "admin0202@gmail.com",
                            generate_password_hash("Admin@0202"),
                            "admin"
                        )
                    )
                    print("✅ Default admin created")

        print("✅ PostgreSQL database initialized successfully")

    except Exception as e:
        print("❌ Error initializing database:", e)

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
