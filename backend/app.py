# backend/app.py
from flask import Flask, render_template, request, session, jsonify, redirect, send_file, url_for, flash
import os, json
from functools import wraps
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from collections import defaultdict
import pytz
from database import get_db_connection  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.tables import Table as RLTable
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
import requests
from collections import Counter
from fpdf import FPDF
import io
from statistics import mean
from werkzeug.security import generate_password_hash, check_password_hash
from utils.chatbot_recommendation import get_user_health_summary
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from utils.female_cycle import get_cycle_phase, generate_female_health_summary
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_dance.contrib.google import make_google_blueprint, google
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import urlencode
import mysql.connector
from mysql.connector import Error

# ---------------- Load .env ----------------
load_dotenv()  # This loads your .env file into environment variables

# ---------------- Load environment variables ----------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ---------------- MySQL Connection ----------------
def get_db_connection():
    """Connect to MySQL DB"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            autocommit=True
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# ---------------- SECURITY CONFIG ----------------
app.secret_key = os.environ.get("SMART_HEALTH_PLUS_SECRET_KEY")

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqlconnector://{}:{}@{}/{}".format(
    os.environ.get("MYSQL_USER", "root"),
    os.environ.get("MYSQL_PASSWORD", ""),
    os.environ.get("MYSQL_HOST", "localhost"),
    os.environ.get("MYSQL_DB", "smarthealthplus")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ---------------- Database ----------------
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    role = db.Column(db.String(50), default="user")
    auth_provider = db.Column(db.String(50), default="google")
    is_active = db.Column(db.Boolean, default=True)

# ---------------- LOGIN REQUIRED ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/auth")
        return f(*args, **kwargs)
    return decorated_function

# ---------------- SPLASH ----------------
@app.route("/")
def splash():
    return render_template("splash.html")

# ---------------- AUTH PAGE ----------------
@app.route("/auth")
def auth():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("auth.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)  # ensures JSON is read

    # Get data
    name = str(data.get("name", "")).strip()
    age = data.get("age")
    gender = str(data.get("gender", "")).strip()
    mobile = str(data.get("mobile", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    role = str(data.get("role", "user")).strip().lower()

    # ---------------- VALIDATIONS ----------------

    if not name:
        return jsonify(success=False, message="Name is required")
    if not email:
        return jsonify(success=False, message="Email is required")
    if not mobile.isdigit() or len(mobile) != 10:
        return jsonify(success=False, message="Mobile number must be 10 digits")
    if role == "admin":
        return jsonify(success=False, message="Admin registration is not allowed")
    if not password or len(password) < 6:
        return jsonify(success=False, message="Password must be at least 6 characters")
    if not gender:
        return jsonify(success=False, message="Gender is required")
    if not age:
        return jsonify(success=False, message="Age is required")

    hashed = generate_password_hash(password)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify(success=False, message="Email already exists")

        # Insert user
        cursor.execute("""
            INSERT INTO users (name, age, gender, mobile, email, password, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, age, gender, mobile, email, hashed, role))

        conn.commit()
        conn.close()

        return jsonify(success=True, message="Registration successful")

    except Exception as e:
        print("Error during registration:", e)  # Check the console
        return jsonify(success=False, message=f"Error: {str(e)}")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    # --- Admin hardcoded login ---
    if email == os.environ.get("ADMIN_EMAIL") and password == os.environ.get("ADMIN_PASSWORD"):
        session["email"] = email
        session["role"] = "admin"
        session["name"] = "Admin"
        return jsonify(success=True, redirect_url="/admin/dashboard")

    # --- Normal user login from MySQL ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify(success=False, message="Invalid email or password")

    # Check password
    if not check_password_hash(user["password"], password):
        return jsonify(success=False, message="Invalid email or password")

    # Set session variables
    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"] if user["role"] else "user"
    session["gender"] = user["gender"].lower() if user["gender"] else "male"  # default male

    # Determine redirect URL based on gender
    if session["role"] == "user":
        if session["gender"] == "female":
            redirect_url = "/female/dashboard"
        else:
            redirect_url = "/dashboard"
    else:
        # fallback (in case you add other roles)
        redirect_url = "/dashboard"

    return jsonify(success=True, redirect_url=redirect_url)


# ---------------- GOOGLE OAUTH CONFIG ----------------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")  # e.g., http://127.0.0.1:5000/auth/google/callback
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

# ---------------- START GOOGLE LOGIN ----------------
@app.route("/auth/google")
def google_login():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"  # <- Forces account selection
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}%s{urlencode(params)}")


@app.route("/auth/google/callback")
def google_callback():
    code = request.args.get("code")
    if not code:
        return "Error: no code returned from Google", 400

    # Exchange code for access token
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    token_res = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data).json()
    access_token = token_res.get("access_token")
    if not access_token:
        return "Error fetching access token", 400

    # Fetch user info
    headers = {"Authorization": f"Bearer {access_token}"}
    user_info = requests.get(GOOGLE_USERINFO_ENDPOINT, headers=headers).json()

    email = user_info.get("email")
    name = user_info.get("name", "Google User")

    if not email:
        return "Error fetching email from Google", 400

    # Check / insert user in MySQL
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, role, gender FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (name, email, role, auth_provider) VALUES (%s, %s, %s, %s)",
            (name, email, "user", "google")
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "user"
        gender = None
    else:
        user_id, role, gender = user["id"], user["role"], user["gender"]

    # Set session variables
    session["user_id"] = user_id
    session["role"] = role
    session["name"] = name
    session["gender"] = gender

    conn.close()

    # Redirect to the correct dashboard based on role/gender
    if role == "admin":
        return redirect("/admin/dashboard")
    elif gender and gender.lower() == "female":
        return redirect("/female/dashboard")
    else:
        return redirect("/dashboard")  # male / other / unknown


# ---------------- Google LOGIN SESSION ----------------
@app.route("/auth/google-session", methods=["POST"])
def google_session():
    data = request.get_json(force=True)

    email = data.get("email")
    name = data.get("name", "Google User")  # default if name not present

    if not email:
        return jsonify({"success": False, "error": "Invalid user"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user including gender
    cursor.execute("SELECT id, role, name, gender FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        # If new Google user, insert into DB without gender (can ask later)
        cursor.execute(
            "INSERT INTO users (name, email, role, auth_provider) VALUES (%s, %s, %s, %s)",
            (name, email, "user", "google")
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "user"
        gender = None
    else:
        user_id, role, existing_name, gender = user["id"], user["role"], user["name"], user["gender"]
        name = existing_name  # use name from DB

    # Set session variables
    session["user_id"] = user_id
    session["role"] = role
    session["name"] = name
    session["gender"] = gender  # <-- important for dashboard redirect

    conn.close()

    # Decide dashboard redirect based on gender
    if role == "admin":
        redirect_url = "/admin/dashboard"
    elif gender and gender.lower() == "female":
        redirect_url = "/female/dashboard"
    else:
        redirect_url = "/dashboard"  # male / other / unknown

    return jsonify({
        "success": True,
        "redirect_url": redirect_url
    })


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/auth")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    # Admin dashboard
    if session.get("role") == "admin":
        return redirect("/admin/dashboard")

    # Female dashboard
    if session.get("gender") == "female":
        return render_template("female_dashboard.html", name=session["name"])

    # Default (male / others)
    return render_template("dashboard.html", name=session["name"])


@app.route("/female/dashboard")
def female_dashboard():
    if "user_id" not in session:
        return redirect("/")

    if session.get("gender") != "female":
        return redirect("/dashboard")

    return render_template("female_dashboard.html")


# ---------------- MODULE PAGES ----------------
@app.route("/sleep")
@login_required
def sleep():
    return render_template("sleep.html")

@app.route("/stress")
@login_required
def stress():
    return render_template("stress.html")

@app.route("/nutrition")
@login_required
def nutrition():
    return render_template("nutrition.html")

@app.route("/fitness")
@login_required
def fitness():
    return render_template("fitness.html")

@app.route("/mood")
@login_required
def mood():
    return render_template("mood.html")

@app.route("/hydration")
@login_required
def hydration():
    return render_template("hydration.html")


@app.route("/goal")
@login_required
def goal():
    score, wellness, _ = calculate_health_score(session["user_id"])

    # Fetch latest data from MySQL
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (session["user_id"],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    latest = {}
    for row in rows:
        if row["category"] not in latest:
            latest[row["category"]] = row["input_value"]

    ai_tip = generate_ai_tip(score, wellness, latest)

    return render_template(
        "goal.html",
        health_score=score,
        wellness_index=wellness,
        tip=ai_tip
    )

@app.route("/reminder")
@login_required
def reminder():
    return render_template("reminder.html")


@app.route("/test-email")
def test_email():
    send_email(
        "YOUR_EMAIL@gmail.com",
        "TEST EMAIL",
        "If you received this, email is working ✅"
    )
    return "Email sent"


# ---------------- Email Function (ONLY ONE) ----------------
def send_email(to_email, subject, body):
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("❌ Email credentials missing")
        return False

    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print("❌ Email error:", e)
        return False


# ---------------- Twilio SMS Function ----------------
def send_sms(to_phone, message):
    from twilio.rest import Client

    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        print("❌ Twilio ENV missing!")
        return False

    to_phone = to_phone.strip()
    if not to_phone.startswith("+"):
        to_phone = "+91" + to_phone

    if to_phone == TWILIO_FROM_NUMBER:
        print("❌ To and From numbers cannot be the same")
        return False

    if not to_phone[1:].isdigit():
        print("❌ Invalid phone number")
        return False

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to_phone
        )
        print(f"✅ SMS sent to {to_phone}! SID: {msg.sid}")
        return True
    except Exception as e:
        print("❌ Twilio SMS error:", e)
        return False


# ---------------- Daily Reminder ----------------
def send_daily_reminder():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT u.name, r.reminder_phone, r.reminder_email
        FROM reminders r
        JOIN users u ON u.id = r.user_id
        WHERE r.reminder_type = 'daily'
    """)

    reminders = cursor.fetchall()
    conn.close()

    for r in reminders:
        name = r["name"]
        phone = r["reminder_phone"]
        email = r["reminder_email"]

        message = f"Hello {name}! This is your daily health reminder 🌸"

        if phone:
            send_sms(phone, message)

        if email:
            send_email(email, "SmartHealthPlus Reminder", message)


# ---------------- Scheduler ----------------
scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_reminder, "interval", hours=24)  # use minutes=1 for testing
scheduler.start()

print("🟢 Scheduler started.")


@app.route("/save-reminder", methods=["POST"])
@login_required
def save_reminder():
    data = request.json

    reminder_type = data.get("type")
    reminder_time = data.get("time")
    reminder_email = data.get("email")      # 🔥 IMPORTANT
    reminder_phone = data.get("phone")      # 🔥 IMPORTANT

    if not reminder_type or not reminder_time:
        return jsonify({"message": "Reminder type and time are required"}), 400

    user_id = session["user_id"]

    # ---------------- Save reminder properly ----------------
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        INSERT INTO reminders (
            user_id,
            reminder_type,
            reminder_time,
            reminder_email,
            reminder_phone
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user_id,
        reminder_type,
        reminder_time,
        reminder_email,
        reminder_phone
    ))

    conn.commit()
    reminder_id = cursor.lastrowid
    cursor.close()
    conn.close()

    hour, minute = map(int, reminder_time.split(":"))

    # ---------------- Reminder Job ----------------
    def reminder_job(rem_id=reminder_id, rtype=reminder_type):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.reminder_email, r.reminder_phone, u.name
            FROM reminders r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = %s
        """, (rem_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            print("❌ Reminder not found")
            return

        email = row["reminder_email"]
        phone = row["reminder_phone"]
        name = row["name"]

        message = f"⏰ Hi {name}, this is your {rtype} reminder 🌸"

        if email:
            send_email(email, "SmartHealthPlus Reminder", message)

        if phone:
            send_sms(phone, message)

    # ---------------- Unique Job ID ----------------
    job_id = f"reminder_{reminder_id}"

    scheduler.add_job(
        reminder_job,
        trigger="cron",
        hour=hour,
        minute=minute,
        id=job_id,
        replace_existing=True
    )

    return jsonify({
        "message": f"{reminder_type.capitalize()} reminder set successfully"
    })


@app.route("/reminder-history")
@login_required
def reminder_history():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, reminder_type, reminder_time, created_at
        FROM reminders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    reminders = []
    for r in rows:
        time_str = r["reminder_time"]
        try:
            dt_obj = datetime.strptime(time_str, "%H:%M")
            formatted_time = dt_obj.strftime("%I:%M %p")  # 12-hour format
        except:
            formatted_time = time_str

        try:
            dt_created = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
            dt_created = dt_created.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
            reminder_date = dt_created.date()
        except:
            reminder_date = date.today()  # fallback

        reminders.append({
            "id": r["id"],
            "reminder_type": r["reminder_type"],
            "formatted_time": formatted_time,
            "reminder_date": reminder_date
        })

    return render_template(
        "reminder_history.html",
        reminders=reminders
    )


# ------------------- Delete Reminder -------------------
@app.route("/delete-reminder/<int:reminder_id>", methods=["POST"])
@login_required
def delete_reminder(reminder_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = %s AND user_id = %s", (reminder_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("reminder_history"))


@app.route("/recommendation")
@login_required
def recommendation():
    from flask import jsonify
    data = generate_recommendation()  # This returns a JSON response
    summary = data.get_json().get("health_summary", "")
    return render_template("recommendation.html", health_summary=summary)

# ---------------- CHATBOT PAGE ----------------
@app.route("/chatbot")
@login_required
def chatbot():
    return render_template("chatbot.html")



# ---------------- PROFILE ----------------
@app.route("/profile")
@login_required
def profile():
    user_id = session.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ----------------- USER INFO -----------------
    cursor.execute(
        "SELECT name, email, mobile, age, gender FROM users WHERE id=%s",
        (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return "User not found", 404

    # ----------------- TIMELINE DATA -----------------
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT category, input_value, recommendation, created_at
        FROM health_data
        WHERE user_id=%s AND created_at >= %s
        ORDER BY created_at DESC
    """, (user_id, seven_days_ago))

    rows = cursor.fetchall()
    timeline_data = defaultdict(list)

    for row in rows:
        day = row["created_at"].strftime("%d %b %Y") if isinstance(row["created_at"], datetime) else row["created_at"][:10]

        category = row["category"]
        value = row["input_value"]

        # ---------------- FITNESS ----------------
        if category == "fitness":
            try:
                d = json.loads(value)
                value = (
                    f"Workout Minutes: {d.get('minutes', 0)} mins | "
                    f"Workout Type: {d.get('type', 'Not specified')} | "
                    f"Daily Steps: {d.get('steps', 0)} steps"
                )
            except:
                pass

        # ---------------- NUTRITION ----------------
        elif category == "nutrition":
            try:
                d = json.loads(value)
                value = (
                    f"Nutrition Quality: {d.get('quality', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- HYDRATION ----------------
        elif category == "hydration":
            try:
                d = json.loads(value)
                value = (
                    f"Hydration Level: {d.get('level', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- SLEEP ----------------
        elif category == "sleep":
            try:
                d = json.loads(value)
                value = (
                    f"Sleep Duration: {d.get('hours', 0)} hours | "
                    f"Quality: {d.get('quality', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- STRESS ----------------
        elif category == "stress":
            try:
                d = json.loads(value)
                value = (
                    f"Stress Level: {d.get('level', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        # ---------------- MOOD ----------------
        elif category == "mood":
            try:
                d = json.loads(value)
                value = (
                    f"Mood: {d.get('mood', 'Not specified')} | "
                    f"Reason: {d.get('reason', 'Not specified')}"
                )
            except:
                pass

        timeline_data[day].append({
            "category": category,
            "input_value": value,
            "recommendation": row["recommendation"]
        })

    # ---------------- HELPER FUNCTION ----------------
    def calculate_summary(data_dict):
        summary = {
            "dates": [], "sleep": [], "hydration": [], "nutrition": [],
            "fitness_minutes": [], "fitness_steps": [],
            "stress": [], "mood": [],
            "health_score": [], "summary_text": ""
        }

        for day, v in data_dict.items():
            summary["dates"].append(day)
            sleep_avg = mean(v["sleep"]) if v["sleep"] else 0
            hydration_sum = sum(v["hydration"])
            nutrition_avg = mean(v["nutrition"]) if v["nutrition"] else 0
            fitness_minutes_sum = sum(v["fitness_minutes"])
            fitness_steps_sum = sum(v["fitness_steps"])
            stress_avg = mean(v["stress"]) if v["stress"] else 0
            mood_avg = mean(v["mood"]) if v["mood"] else 0

            health_score = round((sleep_avg*10 + hydration_sum*5 + nutrition_avg*10 +
                                  fitness_minutes_sum*0.5 + (5-stress_avg)*10 + mood_avg*10) / 6, 1)

            summary["sleep"].append(sleep_avg)
            summary["hydration"].append(hydration_sum)
            summary["nutrition"].append(nutrition_avg)
            summary["fitness_minutes"].append(fitness_minutes_sum)
            summary["fitness_steps"].append(fitness_steps_sum)
            summary["stress"].append(stress_avg)
            summary["mood"].append(mood_avg)
            summary["health_score"].append(health_score)

        if summary["dates"]:
            summary["summary_text"] = (
                f"Over this period, your average sleep was {round(mean(summary['sleep']),1)} hrs/day. "
                f"Hydration totaled {sum(summary['hydration'])} liters. "
                f"Nutrition quality averaged {round(mean(summary['nutrition']),1)}. "
                f"Fitness included {sum(summary['fitness_minutes'])} mins and {sum(summary['fitness_steps'])} steps. "
                f"Stress averaged {round(mean(summary['stress']),1)}, mood stability was {round(mean(summary['mood']),1)}. "
                f"Overall health score indicates a trend of improvement. "
                f"Keep tracking to maintain and enhance your wellness!"
            )
        return summary

    # ---------------- WEEKLY SUMMARY ----------------
    weekly_data = defaultdict(lambda: {
        "sleep": [], "hydration": [], "nutrition": [],
        "fitness_minutes": [], "fitness_steps": [],
        "stress": [], "mood": []
    })

    cursor.execute("""
        SELECT category, input_value, created_at
        FROM health_data
        WHERE user_id=%s AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, (user_id,))
    weekly_rows = cursor.fetchall()

    for r in weekly_rows:
        day = r["created_at"].strftime("%d %b") if isinstance(r["created_at"], datetime) else r["created_at"][:10]
        if r["category"] == "fitness":
            try:
                d = json.loads(r["input_value"])
                weekly_data[day]["fitness_minutes"].append(d.get("minutes", 0))
                weekly_data[day]["fitness_steps"].append(d.get("steps", 0))
            except:
                pass
        else:
            try:
                weekly_data[day][r["category"]].append(float(r["input_value"]))
            except:
                pass

    weekly_summary = calculate_summary(weekly_data)

    # ---------------- MONTHLY SUMMARY ----------------
    monthly_data = defaultdict(lambda: {
        "sleep": [], "hydration": [], "nutrition": [],
        "fitness_minutes": [], "fitness_steps": [],
        "stress": [], "mood": []
    })

    cursor.execute("""
        SELECT category, input_value, created_at
        FROM health_data
        WHERE user_id=%s AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """, (user_id,))
    monthly_rows = cursor.fetchall()

    for r in monthly_rows:
        day = r["created_at"].strftime("%d %b") if isinstance(r["created_at"], datetime) else r["created_at"][:10]
        if r["category"] == "fitness":
            try:
                d = json.loads(r["input_value"])
                monthly_data[day]["fitness_minutes"].append(d.get("minutes", 0))
                monthly_data[day]["fitness_steps"].append(d.get("steps", 0))
            except:
                pass
        else:
            try:
                monthly_data[day][r["category"]].append(float(r["input_value"]))
            except:
                pass

    monthly_summary = calculate_summary(monthly_data)

    cursor.close()
    conn.close()

    # ---------------- RENDER TEMPLATE ----------------
    return render_template(
        "profile.html",
        name=user["name"],
        email=user["email"],
        mobile=user["mobile"],
        age=user["age"],
        gender=user["gender"],
        timeline_data=timeline_data,
        weekly_summary=weekly_summary if weekly_summary["dates"] else None,
        monthly_summary=monthly_summary if monthly_summary["dates"] else None
    )

# ---------------- UPDATE PROFILE ----------------
@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    user_id = session.get("user_id")

    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    age = request.form.get("age")
    gender = request.form.get("gender")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not name or not email or not mobile:
        return jsonify({"status": "error", "message": "Name, Email, and Mobile are required"}), 400

    gender_normalized = gender.lower() if gender else None

    password_hashed = None
    if password or confirm_password:
        if password != confirm_password:
            return jsonify({"status": "error", "message": "Passwords do not match"}), 400
        password_hashed = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "UPDATE users SET name=%s, email=%s, mobile=%s, gender=%s, age=%s"
    params = [name, email, mobile, gender_normalized, age]

    if password_hashed:
        query += ", password=%s"
        params.append(password_hashed)

    query += " WHERE id=%s"
    params.append(user_id)

    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()

    # Update session
    session["name"] = name
    session["gender"] = gender_normalized

    # Decide redirect based on role
    if session.get("role") == "admin":
        redirect_url = "/admin/dashboard"
    elif gender_normalized == "female":
        redirect_url = "/female/dashboard"
    else:
        redirect_url = "/dashboard"

    return jsonify({
        "status": "success",
        "message": "Profile updated successfully",
        "redirect_url": redirect_url
    })


# ---------------- PDF DOWNLOAD WITH DATE RANGE ----------------
@app.route("/download-health-report")
@login_required
def download_health_report():
    user_id = session["user_id"]

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not start_date or not end_date:
        return "Start date and End date are required", 400

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user info
    cursor.execute("SELECT name, email, mobile FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return "User not found", 404

    # Fetch health data for the date range
    cursor.execute("""
        SELECT category, input_value, recommendation, created_at
        FROM health_data
        WHERE user_id = %s
          AND DATE(created_at) BETWEEN %s AND %s
        ORDER BY created_at ASC
    """, (user_id, start_dt, end_dt))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return "No health data found for selected date range", 404

    # ---------------- Helper ----------------
    def safe_float(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0

    # ---------------- PROCESS DATA ----------------
    timeline = defaultdict(list)
    sleep_vals, hydration_vals, stress_vals, mood_vals = [], [], [], []
    fitness_minutes, fitness_steps = 0, 0

    for r in rows:
        # Ensure created_at is datetime
        dt = r["created_at"]
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        date_str = dt.strftime("%Y-%m-%d")

        value = r["input_value"]
        display_value = ""

        try:
            data_json = json.loads(value)
        except:
            data_json = {}

        category = r["category"].lower()

        if category == "sleep":
            hours = safe_float(data_json.get("hours", 0))
            sleep_vals.append(hours)
            display_value = f"Sleep Duration: {hours} hours | Quality: {data_json.get('quality','N/A')} | Reason: {data_json.get('reason','N/A')}"

        elif category == "hydration":
            level = data_json.get("level", 0)
            hydration_vals.append(safe_float(level))
            display_value = f"Hydration Level: {level} | Reason: {data_json.get('reason','N/A')}"

        elif category == "stress":
            level = safe_float(data_json.get("level_value", 0))
            stress_vals.append(level)
            display_value = f"Stress Level: {data_json.get('level','N/A')} | Reason: {data_json.get('reason','N/A')}"

        elif category == "mood":
            score = safe_float(data_json.get("score", 0))
            mood_vals.append(score)
            display_value = f"Mood: {data_json.get('mood','N/A')} | Reason: {data_json.get('reason','N/A')}"

        elif category == "nutrition":
            display_value = f"Nutrition Quality: {data_json.get('quality', value)} | Reason: {data_json.get('reason','N/A')}"

        elif category == "fitness":
            minutes = int(safe_float(data_json.get("minutes", 0)))
            steps = int(safe_float(data_json.get("steps", 0)))
            fitness_minutes += minutes
            fitness_steps += steps
            display_value = f"Workout Minutes: {minutes} mins | Workout Type: {data_json.get('type','Unspecified')} | Daily Steps: {steps} steps"

        timeline[date_str].append({
            "category": category.capitalize(),
            "value": display_value,
            "recommendation": r.get("recommendation","")
        })

    # ---------------- SUMMARY ----------------
    avg_sleep = round(sum(sleep_vals)/len(sleep_vals),1) if sleep_vals else 0
    total_hydration = round(sum(hydration_vals),1)
    avg_stress = round(sum(stress_vals)/len(stress_vals),1) if stress_vals else 0
    avg_mood = round(sum(mood_vals)/len(mood_vals),1) if mood_vals else 0
    health_score = round((avg_sleep + avg_mood - avg_stress)/3,1) if avg_sleep else 0

    summary_text = (
        f"During the selected period, your average sleep was {avg_sleep} hours per day. "
        f"You logged a total hydration intake of {total_hydration} units. "
        f"Your physical activity included {fitness_minutes} minutes of exercise "
        f"and {fitness_steps} total steps. "
        f"Your average stress level was {avg_stress}/10, while your average mood score was {avg_mood}/10. "
        f"Overall, your calculated health score for this period is {health_score}/10."
    )

    # ---------------- CREATE PDF ----------------
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=20)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Smart Health Plus – Health Report</b>", styles["Title"]))
    elements.append(Spacer(1,12))
    elements.append(Paragraph(f"<b>Name:</b> {user['name']}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Email:</b> {user['email']}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Contact Number:</b> {user['mobile']}", styles["Normal"]))
    elements.append(Spacer(1,14))
    elements.append(Paragraph("<b>Health Summary</b>", styles["Heading2"]))
    elements.append(Spacer(1,6))
    elements.append(Paragraph(summary_text, styles["Normal"]))
    elements.append(Spacer(1,14))
    elements.append(Paragraph("<b>Health Data</b>", styles["Heading2"]))
    elements.append(Spacer(1,6))

    for date, entries in timeline.items():
        elements.append(Paragraph(f"<b>{date}</b>", styles["Heading3"]))
        elements.append(Spacer(1,4))
        for e in entries:
            elements.append(Paragraph(
                f"- <b>{e['category']}</b>: {e['value']}<br/><b>Recommendation:</b> {e['recommendation']}",
                styles["Normal"]
            ))
            elements.append(Spacer(1,6))
        elements.append(Spacer(1,10))

    doc.build(elements)
    pdf_buffer.seek(0)

    return send_file(pdf_buffer, as_attachment=True, download_name="health_report.pdf", mimetype="application/pdf")


# --------------- FORGOT PASSWORD -----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    # Hash the password
    hashed_password = generate_password_hash(password)

    # ---------------- MYSQL CONNECTION ----------------
    import mysql.connector
    from mysql.connector import Error

    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )

        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET password = %s WHERE email = %s",
            (hashed_password, email)
        )

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "User not found!"}), 404

        return jsonify({"success": True, "message": "Password reset successfully"})

    except Error as e:
        return jsonify({"success": False, "message": "Database error"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ---------------- SUGGESTION LOGIC ----------------
def generate_suggestion(category, value, include_chatbot_line=True):
    import json

    # Convert JSON string to dict safely
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except:
            value = {}

    chatbot_line = (
        "\n\nFor more personalized guidance, click the chatbot button above "
        "and ask for detailed advice."
    ) if include_chatbot_line else ""

    # Utility
    def to_int(v):
        try:
            return int(v)
        except:
            return 0

    # ---------------- FITNESS ----------------
    if category == "fitness":
        minutes = to_int(value.get("workoutMinutes") or value.get("workout_minutes") or value.get("minutes"))
        steps = to_int(value.get("dailySteps") or value.get("daily_steps") or value.get("steps"))
        workout_type = (value.get("workoutType") or value.get("workout_type") or value.get("type") or "").lower()

        if minutes < 30 and steps >= 6000:
            suggestion = (
                f"Your daily movement is good with {steps} steps, but workout time is a bit low. "
                f"Adding 15–20 more minutes of {workout_type or 'exercise'} can boost your fitness."
            )
        elif minutes >= 30 and steps < 6000:
            suggestion = (
                f"You maintained a solid workout routine today. "
                f"Try increasing daily steps through short walks or staying active between tasks."
            )
        elif minutes < 30 and steps < 6000:
            suggestion = (
                f"Activity levels were lower today, which is completely okay. "
                f"Start small by adding light workouts and more movement throughout the day."
            )
        else:
            suggestion = (
                f"Great balance of workouts and daily movement today. "
                f"Keep maintaining this routine for long-term physical strength and energy."
            )

        return suggestion + chatbot_line

    # ---------------- STRESS ----------------
    if category == "stress":
        level = value.get("level", "").lower()
        reason = value.get("reason", "").lower()

        if level == "low":
            suggestion = (
                "Your stress levels are well managed right now. "
                "Continue following habits that keep your mind calm and balanced."
            )
        elif level == "medium":
            base = "Some stress is present, which is quite normal in daily life."
            reason_map = {
                "workload": "Organizing tasks and taking short breaks can help you feel more in control.",
                "exam": "A structured study plan and rest breaks can reduce mental pressure.",
                "personal": "Giving yourself emotional space and talking to someone you trust may help.",
                "health": "Listening to your body and maintaining healthy routines is important right now."
            }
            suggestion = f"{base} {reason_map.get(reason, 'Simple relaxation techniques can improve mental clarity.')}"
        else:
            base = "Stress levels are high and deserve attention."
            reason_map = {
                "workload": "Prioritizing tasks and allowing proper rest can prevent burnout.",
                "exam": "Balanced preparation and relaxation are key to staying focused.",
                "personal": "Seeking support and practicing mindfulness can ease emotional strain.",
                "health": "Professional guidance and self-care should be prioritized."
            }
            suggestion = f"{base} {reason_map.get(reason, 'Reducing pressure and focusing on recovery is important.')}" 

        return suggestion + chatbot_line

    # ---------------- SLEEP ----------------
    if category == "sleep":
        hours = float(value.get("hours", 0))
        quality = value.get("quality", "").lower()
        reason = value.get("reason", "").lower()

        if hours < 7:
            line1 = "Your sleep duration is lower than recommended."
        elif 7 <= hours <= 8:
            line1 = "Your sleep duration is within a healthy range."
        elif 9 <= hours <= 10:
            line1 = "You slept longer than average, which may indicate fatigue."
        else:
            line1 = "Extended sleep hours may affect daily energy balance."

        quality_map = {
            "good": "Sleep quality is good, which supports recovery.",
            "average": "Sleep quality is moderate and can be improved.",
            "poor": "Poor sleep quality may impact focus and mood."
        }

        reason_map = {
            "stress": "Managing stress before bedtime can improve rest.",
            "workload": "Reducing late-night work may improve sleep consistency.",
            "exam": "Structured study schedules help improve sleep patterns.",
            "personal": "Emotional relaxation techniques can support better sleep.",
            "health": "Health-related sleep issues should not be ignored."
        }

        suggestion = (
            f"{line1} {quality_map.get(quality, '')} "
            f"{reason_map.get(reason, 'Maintaining a calming bedtime routine is beneficial.')}"
        )

        return suggestion.strip() + chatbot_line

    # ---------------- HYDRATION ----------------
    if category == "hydration":
        level = value.get("level", "").lower()
        reason = value.get("reason", "").lower()

        if level == "low":
            base = "Your water intake is currently low."
        elif level == "moderate":
            base = "Your hydration level is moderate."
        else:
            base = "You are well hydrated today."

        reason_map = {
            "forgot": "Setting reminders can help you stay hydrated.",
            "busy": "Keeping water nearby can improve intake during busy hours.",
            "weather": "Hot weather increases your body’s water needs."
        }

        suggestion = (
            f"{base} "
            f"{reason_map.get(reason, 'Maintaining regular water intake supports overall health.')}"
        )

        return suggestion + chatbot_line

    # ---------------- NUTRITION ----------------
    if category == "nutrition":
        quality = value.get("quality", "").lower()
        reason = value.get("reason", "").lower()

        if quality == "good":
         suggestion = (
            "Your nutrition habits are well balanced and supportive of your health. "
            "Continue this routine to maintain steady energy and overall well-being."
        )
        else:
         base = "Your current eating pattern could be improved for better health outcomes."
         reason_map = {
            "junk food": "Frequent junk food can reduce energy levels, so try adding more fresh and home-cooked meals.",
            "skipped meal": "Skipping meals may affect focus and metabolism, so regular meal timing is important.",
            "outside food": "Reducing outside food and choosing home meals can improve nutritional balance.",
            "lack of time": "Quick, healthy options can help you eat better even on busy days."
        }

         suggestion = (
            f"{base} "
            f"{reason_map.get(reason, 'Small dietary changes can make a noticeable difference over time.')}"
        )

        return suggestion + chatbot_line


    # ---------------- MOOD ----------------
    if category == "mood":
        mood = value.get("mood", "").lower()
        reason = value.get("reason", "").lower()

        if mood == "happy":
            suggestion = (
                "You are feeling positive and emotionally balanced today. "
                "Continue activities that support this uplifting mood."
            )
        elif mood in ["sad", "angry"]:
            reason_map = {
                "work stress": "Taking breaks and setting boundaries may help.",
                "family issue": "Open communication and emotional support can ease feelings.",
                "health problem": "Prioritizing self-care is important right now.",
                "others": "Mindfulness can help process emotions effectively."
            }
            suggestion = (
                f"Your current mood deserves care and understanding. "
                f"{reason_map.get(reason, 'Giving yourself time can help restore balance.')}"
            )
        else:
            suggestion = (
                "Your mood appears stable at the moment. "
                "Staying emotionally aware helps maintain mental well-being."
            )

        return suggestion + chatbot_line

    # ---------------- DEFAULT ----------------
    return "Your health journey is progressing steadily. Small consistent habits lead to big improvements." + chatbot_line


@app.route("/save-health-data", methods=["POST"])
@login_required
def save_health_data_route():
    import json
    from datetime import datetime
    import mysql.connector

    # ---------------- 1. Receive Data ----------------
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400

    category = data.get("category")
    value = data.get("value")

    if not category or value is None:
        return jsonify({"success": False, "error": "Category or value missing"}), 400

    # Ensure value is a dict
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except:
            value = {"raw": value}

    # ---------------- 2. Safe Conversions ----------------
    def safe_int(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    def safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0

    category_lower = category.lower()

    # ----------- Normalize Data ----------- 
    if category_lower == "fitness":
        value["minutes"] = safe_int(value.get("minutes") or value.get("workoutMinutes") or 0)
        value["steps"] = safe_int(value.get("steps") or value.get("dailySteps") or 0)
        value["type"] = value.get("type") or value.get("workoutType") or "Unspecified"

    elif category_lower == "sleep":
        value["hours"] = safe_float(value.get("hours") or 0)
        value["quality"] = value.get("quality") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    elif category_lower == "hydration":
        value["level"] = value.get("level") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    elif category_lower == "nutrition":
        value["quality"] = value.get("quality") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    elif category_lower == "stress":
        value["level"] = value.get("level") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    elif category_lower == "mood":
        value["mood"] = value.get("mood") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # ---------------- 3. Generate Suggestion ----------------
    suggestion = generate_suggestion(category, value, include_chatbot_line=False)

    # ---------------- 4. Save to MySQL ----------------
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "User not logged in"}), 401

    try:
        # Use proper environment variables
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO health_data 
            (user_id, category, input_value, recommendation, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            category,
            json.dumps(value),  # Always store JSON as string
            suggestion,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        # 🔥 MUST CALL COMMIT to save data
        conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # ---------------- 5. Return Suggestion ----------------
    suggestion_ui = generate_suggestion(category, value, include_chatbot_line=True)
    return jsonify({"success": True, "suggestion": suggestion_ui})


@app.route("/generate-recommendation")
@login_required
def generate_recommendation():
    import json

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return jsonify({
            "recommendation": "No health data found. Please save your data first.",
            "health_summary": ""
        })

    # ---------------- LATEST DATA PER CATEGORY ----------------
    latest_data = {}
    for row in rows:
        if row["category"] not in latest_data:
            try:
                latest_data[row["category"]] = json.loads(row["input_value"])
            except:
                latest_data[row["category"]] = {}

    rec_messages = []
    summary_lines = []

    def safe_int(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    def safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    # ---------------- FITNESS ----------------
    fitness = latest_data.get("fitness", {})
    minutes = safe_int(fitness.get("minutes"))
    steps = safe_int(fitness.get("steps"))
    workout_type = fitness.get("type") or "Unspecified"

    summary_lines.append(f"Fitness: {minutes} min ({workout_type}), Steps: {steps}")

    if minutes < 30 and steps < 6000:
        rec_messages.append("Workout duration and steps are below recommended levels.")
    elif minutes < 30:
        rec_messages.append("Workout duration is low. Increase activity time.")
    elif steps < 6000:
        rec_messages.append("Daily steps are low. Try to walk more.")
    else:
        rec_messages.append("Excellent fitness routine.")

    # ---------------- OTHER CATEGORIES ----------------
    for cat in ["sleep", "hydration", "nutrition", "stress", "mood"]:
        data = latest_data.get(cat, {})
        if not data:
            continue

        if cat == "sleep":
            hours = safe_float(data.get("hours"))
            quality = data.get("quality") or "Unspecified"
            reason = data.get("reason") or "Not specified"

            summary_lines.append(f"Sleep: {hours} hours, Quality: {quality}, Reason: {reason}")

            if hours < 6:
                rec_messages.append("Sleep is very low. Improve sleep hygiene.")
            elif hours < 7:
                rec_messages.append("Sleep duration slightly low. Aim for 7–8 hours.")
            else:
                rec_messages.append("Sleep duration is healthy.")

        elif cat == "hydration":
            level = (data.get("level") or "Unspecified").lower()
            reason = data.get("reason") or "Not specified"

            summary_lines.append(f"Hydration Level: {level}, Reason: {reason}")

            if level in ["low", "moderate"]:
                rec_messages.append("Hydration is low. Increase water intake.")
            else:
                rec_messages.append("Hydration level is good.")

        elif cat == "nutrition":
            quality = (data.get("quality") or "Unspecified").lower()
            reason = data.get("reason") or "Not specified"

            summary_lines.append(f"Nutrition Quality: {quality}, Reason: {reason}")

            if quality in ["poor", "average"]:
                rec_messages.append("Nutrition needs improvement.")
            else:
                rec_messages.append("Nutrition habits are healthy.")

        elif cat == "stress":
            level = (data.get("level") or "Unspecified").lower()
            reason = data.get("reason") or "Not specified"

            summary_lines.append(f"Stress Level: {level}, Reason: {reason}")

            if level == "high":
                rec_messages.append("High stress detected. Try relaxation techniques.")
            elif level == "medium":
                rec_messages.append("Moderate stress. Take regular breaks.")
            else:
                rec_messages.append("Stress levels are low.")

        elif cat == "mood":
            mood_val = (data.get("mood") or "Unspecified").lower()
            reason = data.get("reason") or "Not specified"

            summary_lines.append(f"Mood: {mood_val}, Reason: {reason}")

            if mood_val in ["sad", "angry"]:
                rec_messages.append("Mood seems low. Consider mindfulness.")
            else:
                rec_messages.append("Mood is positive.")

    final_recommendation = (
        " ".join(rec_messages)
        + " You can get personalized health guidance instantly. "
        + "Click the button below to receive recommendations from our chatbot!"
    )

    health_summary = (
        "Here is a summary of your recent health data:\n"
        + "\n".join(summary_lines)
    )

    return jsonify({
        "recommendation": final_recommendation,
        "health_summary": health_summary
    })


# ----------------health_score----------------
def calculate_health_score(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = %s
        AND DATE(created_at) = CURDATE()
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return 0, "No Data", "Please add today’s health data."

    latest = {}
    for row in rows:
        if row["category"] not in latest:
            try:
                latest[row["category"]] = json.loads(row["input_value"])
            except:
                latest[row["category"]] = row["input_value"]

    total_score = 0
    tips = []
    module_score = 100 / 6

    # 💤 Sleep
    sleep = latest.get("sleep")
    if isinstance(sleep, dict):
        hours = int(sleep.get("hours", 0))
        quality = sleep.get("quality", "").lower()
        if 7 <= hours <= 8 and quality == "good":
            total_score += module_score
        elif hours >= 6:
            total_score += module_score * 0.6
            tips.append("Increase sleep duration.")
        else:
            tips.append("Sleep is too low.")
    else:
        tips.append("Add sleep data.")

    # 💧 Hydration
    hydration = latest.get("hydration")
    if isinstance(hydration, dict):
        level = hydration.get("level", "").lower()
        if level == "high":
            total_score += module_score
        elif level == "moderate":
            total_score += module_score * 0.6
            tips.append("Drink more water.")
        else:
            tips.append("Very low hydration.")
    else:
        tips.append("Add hydration data.")

    # 🥗 Nutrition
    nutrition = latest.get("nutrition")
    if isinstance(nutrition, dict):
        quality = nutrition.get("quality", "").lower()
        if quality == "good":
            total_score += module_score
        else:
            total_score += module_score * 0.4
            tips.append("Improve nutrition quality.")
    else:
        tips.append("Add nutrition data.")

    # 🏃 Fitness
    fitness = latest.get("fitness")
    if isinstance(fitness, dict):
        minutes = int(fitness.get("minutes", 0))
        steps = int(fitness.get("steps", 0))
        if minutes >= 30 and steps >= 6000:
            total_score += module_score
        elif minutes >= 15 or steps >= 4000:
            total_score += module_score * 0.6
            tips.append("Increase activity.")
        else:
            tips.append("Very low physical activity.")
    else:
        tips.append("Add fitness data.")

    # 😟 Stress
    stress = latest.get("stress")
    if isinstance(stress, dict):
        level = stress.get("level", "").lower()
        if level == "low":
            total_score += module_score
        elif level == "medium":
            total_score += module_score * 0.6
            tips.append("Manage stress better.")
        else:
            tips.append("High stress detected.")
    else:
        tips.append("Add stress data.")

    # 😊 Mood
    mood = latest.get("mood")
    if isinstance(mood, dict):
        mood_val = mood.get("mood", "").lower()
        if mood_val == "happy":
            total_score += module_score
        else:
            total_score += module_score * 0.6
            tips.append("Mood seems low.")
    else:
        tips.append("Add mood data.")

    score = int(round(total_score))

    if score < 40:
        wellness = "Needs Improvement"
    elif score < 70:
        wellness = "Average"
    else:
        wellness = "Excellent"

    return score, wellness, " ".join(tips)

def generate_ai_tip(score, wellness, latest_data):
    """
    Generates AI-style tips (can be replaced with real AI API later)
    """

    # If data incomplete
    if not latest_data or len(latest_data) < 6:
        return (
            "You have provided limited health data today. "
            "Please complete all modules to receive personalized AI-based insights."
        )

    if score < 40:
        return (
            "Your health score indicates that improvements are needed. "
            "Start with better sleep, hydration, and light exercise. "
            "Try 10 minutes of meditation and short walks today."
        )

    elif score < 70:
        return (
            "You are on the right track! "
            "Maintain consistency in sleep and hydration. "
            "Consider breathing exercises or yoga to improve overall wellness."
        )

    else:
        return (
            "Excellent work! Your lifestyle habits are strong. "
            "Continue maintaining balance. "
            "You may explore advanced fitness routines or mindfulness meditation."
        )


def get_chatbot_recommendation(health_summary):
    
    url = "https://api.chatbase.co/api/v1/chat"

    headers = {
        "Authorization": "Bearer YOUR_CHATBOT_API_KEY",
        "Content-Type": "application/json"
    }

    payload = {
        "chatbotId": "YOUR_CHATBOT_ID",
        "messages": [
            {
                "role": "user",
                "content": f"""
You are Smart Health Plus AI Assistant.
Analyze the following health data and give personalized recommendations.
Include meditation or exercise only if needed.

Health Data:
{health_summary}
"""
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code != 200:
            return "Chatbot service is currently unavailable."

        data = response.json()
        # Safety check in case 'responses' or 'message' key missing
        if "responses" in data and data["responses"]:
            msg = data["responses"][0].get("message", {}).get("content")
            if msg:
                return msg

        return "Chatbot service returned unexpected data format."

    except Exception as e:
        print("Chatbot Error:", e)
        return "Unable to generate chatbot recommendation at the moment."



def generate_weekly_summary(user_id):
    import json

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = %s
        AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return "No sufficient data available for this week."

    sleep, hydration, stress, fitness = [], [], [], []
    mood_count = {}

    for r in rows:
        cat = r["category"]
        val = r["input_value"]

        try:
            data = json.loads(val)
        except:
            continue

        if cat == "sleep":
            sleep.append(float(data.get("hours", 0)))

        elif cat == "hydration":
            level = data.get("level", "").lower()
            hydration.append({"high": 8, "moderate": 6, "low": 4}.get(level, 0))

        elif cat == "stress":
            stress.append(data.get("level", "").lower())

        elif cat == "fitness":
            fitness.append(int(data.get("minutes", 0)))

        elif cat == "mood":
            mood_val = data.get("mood", "Unspecified")
            mood_count[mood_val] = mood_count.get(mood_val, 0) + 1

    msg = []

    if sleep and sum(sleep) / len(sleep) < 7:
        msg.append("Your sleep duration was below recommended levels.")
    else:
        msg.append("Your sleep routine was mostly consistent.")

    if hydration and sum(hydration) / len(hydration) < 7:
        msg.append("Hydration levels were low on several days.")
    else:
        msg.append("You maintained good hydration habits.")

    if fitness and sum(fitness) / len(fitness) < 30:
        msg.append("Physical activity needs improvement.")
    else:
        msg.append("Your fitness activity was good this week.")

    if stress.count("high") > 2:
        msg.append("Stress levels were frequently high.")

    if mood_count:
        common_mood = max(mood_count, key=mood_count.get)
        msg.append(f"Most frequent mood was {common_mood}.")

    return " ".join(msg)

def generate_monthly_summary(user_id):
    import json

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = %s
        AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return "No sufficient data available for this month."

    sleep, hydration, fitness = [], [], []

    for r in rows:
        cat = r["category"]
        val = r["input_value"]

        try:
            data = json.loads(val)
        except:
            continue

        if cat == "sleep":
            sleep.append(float(data.get("hours", 0)))

        elif cat == "hydration":
            level = data.get("level", "").lower()
            hydration.append({"high": 8, "moderate": 6, "low": 4}.get(level, 0))

        elif cat == "fitness":
            fitness.append(int(data.get("minutes", 0)))

    msg = []

    if sleep and sum(sleep) / len(sleep) >= 7:
        msg.append("Sleep consistency improved over the month.")
    else:
        msg.append("Sleep routine needs improvement.")

    if hydration and sum(hydration) / len(hydration) >= 8:
        msg.append("Hydration habits were well maintained.")
    else:
        msg.append("Hydration was inconsistent.")

    if fitness and sum(fitness) / len(fitness) >= 30:
        msg.append("Physical activity level was satisfactory.")
    else:
        msg.append("Physical activity was below recommended levels.")

    msg.append("Overall health trends show gradual progress.")

    return " ".join(msg)


@app.route("/submit-feedback", methods=["POST"])
@login_required
def submit_feedback():
    user_id = session.get("user_id")
    if not user_id:
        flash("User not logged in", "danger")
        return redirect(url_for("dashboard"))

    # Get form data (STRING VALUES)
    rating = request.form.get("rating", "").strip()              # 😍 Excellent
    usefulness = request.form.get("usefulness", "").strip()      # 💚 Very Useful
    feedback_type = request.form.get("feedback_type", "").strip()
    improve = request.form.get("improve", "").strip()
    feature = request.form.get("feature", "").strip()

    # Validation
    if not rating or not usefulness:
        flash("Rating and usefulness are required!", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for("dashboard"))

    try:
        cursor = conn.cursor()

        # Verify user exists
        cursor.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cursor.fetchone():
            flash("Invalid user session!", "danger")
            return redirect(url_for("dashboard"))

        # Insert feedback
        cursor.execute("""
            INSERT INTO feedback
            (user_id, rating, usefulness, feedback_type, improve, feature)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            rating,
            usefulness,
            feedback_type,
            improve,
            feature
        ))

        conn.commit()
        flash("✅ Feedback submitted successfully!", "success")

    except Exception as e:
        print("❌ Feedback insert error:", e)
        flash("❌ Failed to submit feedback!", "danger")

    finally:
        cursor.close()
        conn.close()

    # ✅ REDIRECT AFTER SUBMIT
    return redirect(url_for("dashboard"))

# ---------------- Admin Login ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password) and user["role"] == "admin":
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials or not an admin!", "danger")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total users
    cursor.execute("SELECT COUNT(*) AS cnt FROM users")
    total_users = cursor.fetchone()["cnt"]

    # Feedback stats
    cursor.execute("SELECT COUNT(*) AS cnt FROM feedback")
    total_feedback = cursor.fetchone()["cnt"]

    cursor.execute("SELECT AVG(rating) AS avg_rating FROM feedback")
    avg_rating = cursor.fetchone()["avg_rating"] or 0

    cursor.execute("SELECT COUNT(*) AS cnt FROM feedback WHERE created_at >= NOW() - INTERVAL 1 DAY")
    new_feedback = cursor.fetchone()["cnt"]

    # ---------- USER GROWTH (Last 7 Days) ----------
    user_labels = []
    user_counts = []

    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST

    cursor.execute("SELECT created_at FROM users")
    all_users = cursor.fetchall()
    created_list = [u["created_at"] + timedelta(hours=5, minutes=30) for u in all_users]

    for i in range(6, -1, -1):
        day_start = (now_ist - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = (now_ist - timedelta(days=i)).replace(hour=23, minute=59, second=59, microsecond=999999)
        count = sum(1 for dt in created_list if day_start <= dt <= day_end)
        user_labels.append(day_start.strftime("%d-%b"))
        user_counts.append(count)

    # ---------- FAKE FEEDBACK PIE CHART ----------
    rating_distribution = [4, 2, 0, 0, 0]  # fake data

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_feedback=total_feedback,
        avg_rating=round(avg_rating, 2),
        new_feedback=new_feedback,
        user_labels=user_labels,
        user_counts=user_counts,
        rating_distribution=rating_distribution
    )


@app.route("/admin/feedback")
def admin_feedback():
    if session.get("role") != "admin":
        flash("Access denied!", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for("dashboard"))

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                f.rating,
                f.usefulness,
                f.feedback_type,
                f.improve,
                f.feature,
                f.created_at,
                COALESCE(u.name, 'Unknown User') AS name,
                COALESCE(u.email, 'Deleted / Mismatch') AS email
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
        """)

        feedbacks = cursor.fetchall()

    except Exception as e:
        print("❌ Admin feedback fetch error:", e)
        flash("Failed to load feedback!", "danger")
        feedbacks = []

    finally:
        cursor.close()
        conn.close()

    # IST time (consistent with dashboard)
    current_date = datetime.utcnow() + timedelta(hours=5, minutes=30)

    return render_template(
        "admin_feedback.html",
        feedbacks=feedbacks,
        current_date=current_date
    )

@app.route("/admin/feedback/export_pdf")
def export_feedback_pdf():
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            u.name, u.email, f.rating, f.usefulness, f.feedback_type,
            f.improve, f.feature, f.created_at
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """)
    feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=20, leftMargin=20,
        topMargin=30, bottomMargin=20
    )

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle('normal', fontSize=10)
    wrap_style = ParagraphStyle('wrap', fontSize=10, wordWrap='CJK')

    elements = []
    elements.append(Paragraph("User Feedback Report", styles['Title']))
    elements.append(Spacer(1, 12))

    data = [["User", "Email", "Rating", "Useful", "Type", "Improve", "Feature", "Date & Time"]]

    for f in feedbacks:
        dt = f["created_at"]
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

        formatted_date = dt.strftime("%Y-%m-%d %I:%M %p")

        data.append([
            Paragraph(f["name"], wrap_style),
            Paragraph(f["email"], wrap_style),
            Paragraph(str(f["rating"]), normal_style),
            Paragraph(str(f["usefulness"]), normal_style),
            Paragraph(f["feedback_type"], wrap_style),
            Paragraph(f["improve"] or "-", wrap_style),
            Paragraph(f["feature"] or "-", wrap_style),
            Paragraph(formatted_date, normal_style)
        ])

    page_width, _ = landscape(letter)
    available_width = page_width - 40

    col_widths = [
        0.13 * available_width,
        0.23 * available_width,
        0.07 * available_width,
        0.07 * available_width,
        0.10 * available_width,
        0.14 * available_width,
        0.14 * available_width,
        0.15 * available_width,
    ]

    table = RLTable(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4e73df")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
    ]))

    for i in range(1, len(data)):
        bg = "#f8f9fc" if i % 2 == 0 else "#ffffff"
        table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.HexColor(bg))]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="user_feedback.pdf",
        mimetype="application/pdf"
    )


@app.route("/admin/users")
@app.route("/admin/users/<status>")
def admin_users(status=None):
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if status == "active":
        cursor.execute("SELECT * FROM users WHERE is_active = 1")
    elif status == "inactive":
        cursor.execute("SELECT * FROM users WHERE is_active = 0")
    else:
        cursor.execute("SELECT * FROM users")

    users = cursor.fetchall()
    cursor.close()
    conn.close()

    for u in users:
        if u["created_at"]:
            u["created_at"] = (
                u["created_at"] + timedelta(hours=5, minutes=30)
            ).strftime("%Y-%m-%d %H:%M:%S")

    return render_template("admin_users.html", users=users)


@app.route("/admin/user/delete/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("User deleted successfully!", "success")
    return redirect(url_for("admin_users"))



# ---------------- Main Period Page ----------------
@app.route("/period", methods=["GET", "POST"])
@login_required
def period():
    # Only female users
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Ensure dictionary results

    # Fetch the last period record
    cursor.execute("""
        SELECT last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))
    record = cursor.fetchone()

    conn.close()

    predicted_date = None
    female_health_summary = None
    wellness_suggestions = None
    phase = None

    if record:
        # Convert last_period_date string to date object
        try:
            last_date = datetime.strptime(record["last_period_date"], "%Y-%m-%d").date()
        except ValueError:
            last_date = None

        if last_date:
            predicted_date = last_date + timedelta(days=int(record["cycle_length"]))
            phase = get_cycle_phase(record["last_period_date"], int(record["cycle_length"]))
            female_health_summary, wellness_suggestions = generate_female_health_summary(record)
        else:
            phase = "Unknown"

    return render_template(
        "period.html",
        record=record,
        predicted_date=predicted_date,
        female_health_summary=female_health_summary,
        wellness_suggestions=wellness_suggestions,
        phase=phase  # <-- Pass phase directly
    )

# ---------------- Add Period Record ----------------
@app.route("/period/add", methods=["POST"])
@login_required
def add_period():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    last_period_date = request.form.get("last_period_date")
    cycle_length = request.form.get("cycle_length")
    period_duration = request.form.get("period_duration")
    symptoms = request.form.get("symptoms")

    if not last_period_date:
        return redirect("/period")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO period_tracking
        (user_id, last_period_date, cycle_length, period_duration, symptoms)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        session["user_id"],
        last_period_date,
        cycle_length or 28,
        period_duration or 5,
        symptoms
    ))

    conn.commit()
    conn.close()

    return redirect("/period")

# ---------------- Period History ----------------
@app.route("/period/history")
@login_required
def period_history():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = %s
        ORDER BY last_period_date DESC
    """, (session["user_id"],))
    history = cursor.fetchall()
    conn.close()

    return render_template("period_history.html", history=history)

# ---------------- Edit Period ----------------
@app.route("/period/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def edit_period(pid):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        cycle_length = request.form["cycle_length"]
        period_duration = request.form["period_duration"]
        symptoms = request.form["symptoms"]

        cursor.execute("""
            UPDATE period_tracking
            SET cycle_length=%s, period_duration=%s, symptoms=%s
            WHERE id=%s AND user_id=%s
        """, (cycle_length, period_duration, symptoms, pid, session["user_id"]))

        conn.commit()
        conn.close()
        return redirect("/period/history")

    cursor.execute("""
        SELECT cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE id=%s AND user_id=%s
    """, (pid, session["user_id"]))
    record = cursor.fetchone()
    conn.close()

    return render_template("edit_period.html", record=record)

# ---------------- Delete Period ----------------
@app.route("/period/delete/<int:record_id>", methods=["POST"])
@login_required
def delete_period_record(record_id):
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM period_tracking
        WHERE id = %s AND user_id = %s
    """, (record_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/period/history")

# ---------------- Period Charts ----------------
@app.route("/period/charts")
@login_required
def period_charts():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = %s
        ORDER BY last_period_date ASC
    """, (session["user_id"],))
    history = cursor.fetchall()
    conn.close()

    # Prepare chart data
    dates = [rec["last_period_date"] for rec in history]
    cycle_lengths = [rec["cycle_length"] for rec in history]
    period_durations = [rec["period_duration"] for rec in history]

    # Symptoms frequency
    all_symptoms = []
    for rec in history:
        if rec["symptoms"]:
            all_symptoms.extend([s.strip() for s in rec["symptoms"].split(",")])
    symptoms_count = Counter(all_symptoms)

    # Cycle phase distribution
    phase_count = Counter()
    for rec in history:
        phase = get_cycle_phase(rec["last_period_date"], rec["cycle_length"])
        phase_count[phase] += 1

    return render_template(
        "period_charts.html",
        dates=dates,
        cycle_lengths=cycle_lengths,
        period_durations=period_durations,
        symptoms_count=symptoms_count,
        phase_count=phase_count
    )

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



