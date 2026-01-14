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
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        age INT,
        gender VARCHAR(20),
        email VARCHAR(150) UNIQUE,
        mobile VARCHAR(20),
        password VARCHAR(255),
        role VARCHAR(20) DEFAULT 'user',
        auth_provider VARCHAR(50) DEFAULT 'manual',
        is_active TINYINT DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- SLEEP DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sleep_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        hours INT,
        quality VARCHAR(50) DEFAULT 'Unknown',
        reason VARCHAR(255) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- STRESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stress_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        level VARCHAR(50),
        reason VARCHAR(255) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- HYDRATION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hydration_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        level VARCHAR(50) DEFAULT 'Unknown',
        reason VARCHAR(255) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- MOOD DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        mood VARCHAR(50),
        reason VARCHAR(255) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- FITNESS DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fitness_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        minutes INT DEFAULT 0,
        steps INT DEFAULT 0,
        workout_type VARCHAR(100) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- NUTRITION DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        quality VARCHAR(50) DEFAULT 'Unknown',
        reason VARCHAR(255) DEFAULT 'Unspecified',
        suggestion TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- HEALTH DATA ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        category VARCHAR(100),
        input_value VARCHAR(255),
        recommendation TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- REMINDERS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        reminder_type VARCHAR(100),
        reminder_time VARCHAR(50),
        reminder_date VARCHAR(50),
        reminder_email VARCHAR(150),
        reminder_phone VARCHAR(20),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- FEEDBACK ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        rating VARCHAR(50) NOT NULL,
        usefulness VARCHAR(50) NOT NULL,
        feedback_type VARCHAR(100),
        improve TEXT,
        feature TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)


    # ---------------- PERIOD TRACKING ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS period_tracking (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        last_period_date varchar(20) NOT NULL,
        cycle_length INT DEFAULT 28,
        period_duration INT DEFAULT 5,
        symptoms TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------------- DEFAULT ADMIN ----------------
    cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    admin_exists = cursor.fetchone()

    if not admin_exists:
        admin_email = "admin0202@gmail.com"
        admin_password = generate_password_hash("Admin@0202")
        admin_name = "Admin"

        cursor.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            """,
            (admin_name, admin_email, admin_password, "admin")
        )

        print("✅ Default admin created:", admin_email)

    cursor.close()
    conn.close()
    print("✅ MySQL database initialized successfully with all tables!")

if __name__ == "__main__":
    init_db()
