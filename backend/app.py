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
from utils.chatbot_recommendation import ( get_user_health_summary)
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from utils.femalecycle import get_cycle_phase, generate_female_health_summary
import sqlite3
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_dance.contrib.google import make_google_blueprint, google
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import urlencode

# ---------------- Load .env ----------------
load_dotenv()  # This loads your .env file into environment variables

# ---------------- Load environment variables ----------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ---------------- SQLite Connection ----------------
DB_PATH = os.path.join(os.path.dirname(__file__), "smarthealthplus.db")

def get_db_connection():
    """Connect to local SQLite DB"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- Scheduler ----------------
scheduler = BackgroundScheduler()
scheduler.start()


# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)


# ---------------- SECURITY CONFIG ----------------
app.secret_key = os.environ.get("SMART_HEALTH_PLUS_SECRET_KEY")


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smarthealthplus.db"
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
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email=?", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify(success=False, message="Email already exists")

        # Insert user
        cursor.execute("""
            INSERT INTO users (name, age, gender, mobile, email, password, role)
            VALUES (?,?,?,?,?,?,?)
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

    # --- Normal user login from DB ---
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
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
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


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

    # Check / insert user in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, gender FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (name, email, role, auth_provider) VALUES (?, ?, ?, ?)",
            (name, email, "user", "google")
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "user"
        gender = None
    else:
        user_id, role, gender = user

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


# ---------------- Google LOGIN ----------------
@app.route("/auth/google-session", methods=["POST"])
def google_session():
    data = request.get_json(force=True)

    email = data.get("email")
    name = data.get("name", "Google User")  # default if name not present

    if not email:
        return jsonify({"success": False, "error": "Invalid user"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user including gender
    cursor.execute("SELECT id, role, name, gender FROM users WHERE email=?", (email,))
    user = cursor.fetchone()

    if not user:
        # If new Google user, insert into DB without gender (can ask later)
        cursor.execute(
            "INSERT INTO users (name, email, role, auth_provider) VALUES (?, ?, ?, ?)",
            (name, email, "user", "google")
        )
        conn.commit()
        user_id = cursor.lastrowid
        role = "user"
        gender = None
    else:
        user_id, role, existing_name, gender = user
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
    elif gender == "female":
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

    # Fetch latest data again (light query)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id=?
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
    """
    Send SMS using Twilio.
    Reads env variables inside function to avoid Invalid URL.
    """
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
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.name, r.reminder_phone, r.reminder_email
        FROM reminders r
        JOIN users u ON u.id = r.user_id
        WHERE r.reminder_type = 'daily'
    """)

    reminders = cursor.fetchall()
    conn.close()

    for name, phone, email in reminders:
        message = f"Hello {name}! This is your daily health reminder 🌸"

        if phone:
            send_sms(phone, message)

        if email:
            send_email(email, "SmartHealthPlus Reminder", message)


# ---------------- Scheduler ----------------
scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_reminder, "interval", hours=24)  # use minutes=1 for testing
scheduler.start()

print("🟢 Scheduler started. Press Ctrl+C to quit.")


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
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reminders (
            user_id,
            reminder_type,
            reminder_time,
            reminder_email,
            reminder_phone
        )
        VALUES (?, ?, ?, ?, ?)
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
        cursor = conn.cursor()

        cursor.execute("""
            SELECT r.reminder_email, r.reminder_phone, u.name
            FROM reminders r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
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

        # ---------------- Email (ALWAYS WORKS) ----------------
        if email:
            send_email(email, "SmartHealthPlus Reminder", message)

        # ---------------- SMS (OPTIONAL / TRIAL LIMIT) ----------------
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
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, reminder_type, reminder_time, created_at
        FROM reminders
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    reminders = []
    for r in rows:
        # Format time to 12-hour AM/PM
        time_str = r["reminder_time"]
        try:
            dt_obj = datetime.strptime(time_str, "%H:%M")
            formatted_time = dt_obj.strftime("%I:%M %p")  # 12-hour format
        except:
            formatted_time = time_str

        # ---------------- Correct timezone for created_at ----------------
        try:
            dt_created = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
            
            # Assuming your server stores UTC, convert to India Standard Time (UTC+5:30)
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
    cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("reminder_history"))



@app.route("/recommendation")
@login_required
def recommendation():
    user_id = session["user_id"]

    summary = get_user_health_summary(user_id)

    return render_template(
        "recommendation.html",
        health_summary=summary
    )



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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ----------------- USER INFO -----------------
    cursor.execute(
        "SELECT name, email, mobile, age, gender FROM users WHERE id=?",
        (user_id,)
    )
    user = cursor.fetchone()

    # ----------------- TIMELINE DATA -----------------
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT category, input_value, recommendation, created_at
        FROM health_data
        WHERE user_id=? AND created_at >= ?
        ORDER BY created_at DESC
    """, (user_id, seven_days_ago))

    rows = cursor.fetchall()

    timeline_data = defaultdict(list)

    for row in rows:
        day = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%d %b %Y")

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
        WHERE user_id=? AND DATE(created_at) >= DATE('now','-7 day')
    """, (user_id,))
    weekly_rows = cursor.fetchall()

    for r in weekly_rows:
        day = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%d %b")
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
        WHERE user_id=? AND DATE(created_at) >= DATE('now','-30 day')
    """, (user_id,))
    monthly_rows = cursor.fetchall()

    for r in monthly_rows:
        day = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%d %b")
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
        mobile=user["mobile"],  # ✅ now mobile is passed to template
        age=user["age"],
        gender=user["gender"],
        timeline_data=timeline_data,  # now a dict grouped by date
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

    # 🔥 NORMALIZE gender
    gender_normalized = gender.lower() if gender else None

    password_hashed = None
    if password or confirm_password:
        if password != confirm_password:
            return jsonify({"status": "error", "message": "Passwords do not match"}), 400
        from werkzeug.security import generate_password_hash
        password_hashed = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "UPDATE users SET name=?, email=?, mobile=?, gender=?, age=?"
    params = [name, email, mobile, gender_normalized, age]

    if password_hashed:
        query += ", password=?"
        params.append(password_hashed)

    query += " WHERE id=?"
    params.append(user_id)

    cursor.execute(query, params)
    conn.commit()
    conn.close()

    # 🔥 UPDATE SESSION IMMEDIATELY
    session["name"] = name
    session["gender"] = gender_normalized

    # 🔥 DECIDE DASHBOARD HERE (backend decides, not frontend)
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


# ---------------- PDF DOWNLOAD WITH DATE RANGE & DETAILED SUMMARY ----------------

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
    except:
        return "Invalid date format. Use YYYY-MM-DD", 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name, email, mobile FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return "User not found", 404

    cursor.execute("""
        SELECT category, input_value, recommendation, created_at
        FROM health_data
        WHERE user_id = ?
          AND DATE(created_at) BETWEEN ? AND ?
        ORDER BY created_at ASC
    """, (user_id, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return "No health data found for selected date range", 404

    timeline = defaultdict(list)

    sleep_vals, hydration_vals = [], []
    stress_vals, mood_vals = [], []
    fitness_minutes, fitness_steps = 0, 0

    # ---------- PROCESS DATA ----------
    for r in rows:
        date_str = r["created_at"][:10]
        value = r["input_value"]
        display_value = ""

        if r["category"] == "sleep":
            try:
                d = json.loads(value)
                sleep_vals.append(float(d.get("hours", 0)))
                display_value = f"Sleep Duration: {d.get('hours', 0)} hours | Quality: {d.get('quality', 'N/A')} | Reason: {d.get('reason', 'N/A')}"
            except:
                display_value = value

        elif r["category"] == "hydration":
            try:
                d = json.loads(value)
                display_value = f"Hydration Level: {d.get('level', 'N/A')} | Reason: {d.get('reason', 'N/A')}"
            except:
                display_value = value

        elif r["category"] == "stress":
            try:
                d = json.loads(value)
                stress_vals.append(float(d.get("level_value", 0)))
                display_value = f"Stress Level: {d.get('level', 'N/A')} | Reason: {d.get('reason', 'N/A')}"
            except:
                display_value = value

        elif r["category"] == "mood":
            try:
                d = json.loads(value)
                mood_vals.append(float(d.get("score", 0)))
                display_value = f"Mood: {d.get('mood', 'N/A')} | Reason: {d.get('reason', 'N/A')}"
            except:
                display_value = value

        elif r["category"] == "nutrition":
            try:
                d = json.loads(value)
                display_value = f"Nutrition Quality: {d.get('quality', value)} | Reason: {d.get('reason', 'N/A')}"
            except:
                display_value = f"Nutrition Quality: {value}"

        elif r["category"] == "fitness":
            try:
                d = json.loads(value)
                fitness_minutes += int(d.get("minutes", 0))
                fitness_steps += int(d.get("steps", 0))
                display_value = f"Workout Minutes: {d.get('minutes',0)} mins | Workout Type: {d.get('type','Unspecified')} | Daily Steps: {d.get('steps',0)} steps"
            except:
                display_value = value

        timeline[date_str].append({
            "category": r["category"].capitalize(),
            "value": display_value,
            "recommendation": r["recommendation"] or ""
        })

    # ---------- SUMMARY ----------
    avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else 0
    total_hydration = sum(hydration_vals)
    avg_stress = round(sum(stress_vals) / len(stress_vals), 1) if stress_vals else 0
    avg_mood = round(sum(mood_vals) / len(mood_vals), 1) if mood_vals else 0
    health_score = round((avg_sleep + avg_mood - avg_stress) / 3, 1) if avg_sleep else 0

    summary_text = (
        f"During the selected period, your average sleep was {avg_sleep} hours per day. "
        f"You logged a total hydration intake of {total_hydration} units. "
        f"Your physical activity included {fitness_minutes} minutes of exercise "
        f"and {fitness_steps} total steps. "
        f"Your average stress level was {avg_stress}/10, while your average mood score was {avg_mood}/10. "
        f"Overall, your calculated health score for this period is {health_score}/10."
    )

    # ---------- CREATE PDF ----------
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=20)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Smart Health Plus – Health Report</b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Name:</b> {user['name']}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Email:</b> {user['email']}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Contact Number:</b> {user['mobile']}", styles["Normal"]))

    elements.append(Spacer(1, 14))
    elements.append(Paragraph("<b>Health Summary</b>", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(summary_text, styles["Normal"]))
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("<b>Health Data</b>", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    for date, entries in timeline.items():
        elements.append(Paragraph(f"<b>{date}</b>", styles["Heading3"]))
        elements.append(Spacer(1, 4))
        for e in entries:
            elements.append(Paragraph(
                f"- <b>{e['category']}</b>: {e['value']}<br/><b>Recommendation:</b> {e['recommendation']}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 6))
        elements.append(Spacer(1, 10))

    doc.build(elements)
    pdf_buffer.seek(0)

    return send_file(pdf_buffer, as_attachment=True, download_name="health_report.pdf", mimetype="application/pdf")


# --------------- FORGOT PASSWORD -----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"})

    # Hash the password before storing
    hashed_password = generate_password_hash(password)

    # Update password in DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
    conn.commit()
    updated_rows = cursor.rowcount
    conn.close()

    if updated_rows == 0:
        return jsonify({"success": False, "message": "User not found!"})

    return jsonify({"success": True, "message": "Password reset successfully"})



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

    # ---------------- SAFE CONVERSIONS ----------------
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

    # ----------- FITNESS -----------
    if category_lower == "fitness":
        # Map all possible frontend keys to backend standard keys
        value["minutes"] = safe_int(value.get("minutes") or value.get("workoutMinutes") or 0)
        value["steps"] = safe_int(value.get("steps") or value.get("dailySteps") or 0)
        value["type"] = value.get("type") or value.get("workoutType") or "Unspecified"

    # ----------- SLEEP -----------
    elif category_lower == "sleep":
        value["hours"] = safe_float(value.get("hours") or 0)
        value["quality"] = value.get("quality") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # ----------- HYDRATION -----------
    elif category_lower == "hydration":
        value["level"] = value.get("level") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # ----------- NUTRITION -----------
    elif category_lower == "nutrition":
        value["quality"] = value.get("quality") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # ----------- STRESS -----------
    elif category_lower == "stress":
        value["level"] = value.get("level") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # ----------- MOOD -----------
    elif category_lower == "mood":
        value["mood"] = value.get("mood") or "Unspecified"
        value["reason"] = value.get("reason") or "Not specified"

    # Generate suggestion without chatbot line
    suggestion = generate_suggestion(category, value, include_chatbot_line=False)

    # ---------------- SAVE TO DB ----------------
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "User not logged in"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO health_data 
            (user_id, category, input_value, recommendation, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            category,
            json.dumps(value),  # store normalized JSON
            suggestion,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # Return suggestion for UI
    suggestion_ui = generate_suggestion(category, value, include_chatbot_line=True)
    return jsonify({"success": True, "suggestion": suggestion_ui})


@app.route("/generate-recommendation")
@login_required
def generate_recommendation():
    import json

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = ?
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

    # Latest data per category
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
            return 0

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
                rec_messages.append(f"Sleep is very low ({hours}h). Focus on stress management and better sleep hygiene.")
            elif hours < 7:
                rec_messages.append(f"Sleep duration slightly low ({hours}h). Try reaching 7–8 hours.")
            else:
                rec_messages.append("Sleep duration is healthy.")

        elif cat == "hydration":
            level = data.get("level") or "Unspecified"
            reason = data.get("reason") or "Not specified"
            summary_lines.append(f"Hydration Level: {level}, Reason: {reason}")
            if level.lower() in ["low", "moderate"]:
                rec_messages.append(f"Hydration is {level}. Increase water intake to 7–8 glasses daily.")
            elif level.lower() == "unspecified":
                rec_messages.append("Hydration level not specified.")
            else:
                rec_messages.append("Hydration level is good.")

        elif cat == "nutrition":
            quality = data.get("quality") or "Unspecified"
            reason = data.get("reason") or "Not specified"
            summary_lines.append(f"Nutrition Quality: {quality}, Reason: {reason}")
            if quality.lower() in ["poor", "average"]:
                rec_messages.append("Nutrition needs improvement. Reduce junk food and eat balanced meals.")
            elif quality.lower() == "unspecified":
                rec_messages.append("Nutrition quality not specified.")
            else:
                rec_messages.append("Nutrition habits are healthy.")

        elif cat == "stress":
            level = data.get("level") or "Unspecified"
            reason = data.get("reason") or "Not specified"
            summary_lines.append(f"Stress Level: {level}, Reason: {reason}")
            if level.lower() == "high":
                rec_messages.append("High stress detected. Try meditation, breaks, or talking to someone.")
            elif level.lower() == "medium":
                rec_messages.append("Moderate stress. Take regular breaks.")
            elif level.lower() == "unspecified":
                rec_messages.append("Stress level not specified.")
            else:
                rec_messages.append("Stress levels are low.")

        elif cat == "mood":
            mood_val = data.get("mood") or "Unspecified"
            reason = data.get("reason") or "Not specified"
            summary_lines.append(f"Mood: {mood_val}, Reason: {reason}")
            if mood_val.lower() in ["sad", "angry"]:
                rec_messages.append("Mood seems low. Consider mindfulness or chatting with AI assistant.")
            elif mood_val.lower() == "unspecified":
                rec_messages.append("Mood not specified.")
            else:
                rec_messages.append("Mood is positive.")

    final_recommendation = (
        " ".join(rec_messages) +
        " You can get personalized health guidance instantly. Click the button below to receive recommendations from our chatbot!"
    )
    health_summary = "Here is a summary of your recent health data:\n" + "\n".join(summary_lines)

    return jsonify({
        "recommendation": final_recommendation,
        "health_summary": health_summary
    })



# ----------------health_score----------------
def calculate_health_score(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, input_value
        FROM health_data
        WHERE user_id = ?
        AND DATE(created_at) = DATE('now')
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
    if len(latest_data) < 6:
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

    if score < 70:
        return (
            "You are on the right track! "
            "Maintain consistency in sleep and hydration. "
            "Consider breathing exercises or yoga to improve overall wellness."
        )

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
        return data["responses"][0]["message"]["content"]

    except Exception as e:
        print("Chatbot Error:", e)
        return "Unable to generate chatbot recommendation at the moment."



def generate_weekly_summary(rows):
    if not rows:
        return "No sufficient data available for this week."

    sleep, hydration, stress, fitness = [], [], [], []
    mood_count = {}

    for r in rows:
        cat = r["category"]
        val = r["input_value"]

        if cat == "sleep":
            sleep.append(int(val))
        elif cat == "hydration":
            hydration.append(int(val))
        elif cat == "stress":
            stress.append(val)
        elif cat == "fitness":
            try:
                data = json.loads(val)
                fitness.append(data.get("minutes", 0))
            except:
                pass
        elif cat == "mood":
            mood_count[val] = mood_count.get(val, 0) + 1

    msg = []

    if sleep and sum(sleep)/len(sleep) < 7:
        msg.append("Your sleep duration was below recommended levels.")
    else:
        msg.append("Your sleep routine was mostly consistent.")

    if hydration and sum(hydration)/len(hydration) < 7:
        msg.append("Hydration levels were low on several days.")
    else:
        msg.append("You maintained good hydration habits.")

    if fitness and sum(fitness)/len(fitness) < 30:
        msg.append("Physical activity needs improvement.")
    else:
        msg.append("Your fitness activity was good this week.")

    if stress.count("high") > 2:
        msg.append("Stress levels were frequently high.")

    if mood_count:
        common_mood = max(mood_count, key=mood_count.get)
        msg.append(f"Most frequent mood was {common_mood}.")

    return " ".join(msg)


def generate_monthly_summary(rows):
    if not rows:
        return "No sufficient data available for this month."

    sleep, hydration, fitness = [], [], []

    for r in rows:
        if r["category"] == "sleep":
            sleep.append(int(r["input_value"]))
        elif r["category"] == "hydration":
            hydration.append(int(r["input_value"]))
        elif r["category"] == "fitness":
            try:
                data = json.loads(r["input_value"])
                fitness.append(data.get("minutes", 0))
            except:
                pass

    msg = []

    if sleep and sum(sleep)/len(sleep) >= 7:
        msg.append("Sleep consistency improved over the month.")
    else:
        msg.append("Sleep routine needs improvement.")

    if hydration and sum(hydration)/len(hydration) >= 8:
        msg.append("Hydration habits were well maintained.")
    else:
        msg.append("Hydration was inconsistent.")

    if fitness and sum(fitness)/len(fitness) >= 30:
        msg.append("Physical activity level was satisfactory.")
    else:
        msg.append("Physical activity was below recommended levels.")

    msg.append("Overall health trends show gradual progress.")

    return " ".join(msg)


# ----------------submit-feedback----------------
@app.route("/submit-feedback", methods=["POST"])
@login_required
def submit_feedback():
    user_id = session.get("user_id")

    if not user_id:
        return "User not logged in", 403

    rating = request.form.get("rating")
    usefulness = request.form.get("usefulness")
    feedback_type = request.form.get("feedback_type")
    improve = request.form.get("improve")
    feature = request.form.get("feature")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO feedback (
            user_id,
            rating,
            usefulness,
            feedback_type,
            improve,
            feature,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        user_id,
        rating,
        usefulness,
        feedback_type,
        improve,
        feature
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ---------------- Admin Login ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
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
    cursor = conn.cursor()

    # Total users
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # Feedback counts (fake data or dynamic)
    total_feedback = cursor.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    avg_rating = cursor.execute("SELECT AVG(rating) FROM feedback").fetchone()[0] or 0
    new_feedback = cursor.execute(
        "SELECT COUNT(*) FROM feedback WHERE created_at >= datetime('now','-1 day')"
    ).fetchone()[0]

    # ---------- USER GROWTH (Last 7 Days) ----------
    user_labels = []
    user_counts = []

    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)  # convert to IST

    # Get all user created_at
    all_users = cursor.execute("SELECT created_at FROM users").fetchall()
    created_list = [datetime.strptime(u["created_at"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=5, minutes=30) for u in all_users]

    for i in range(6, -1, -1):  # last 7 days
        day_start = (now_ist - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = (now_ist - timedelta(days=i)).replace(hour=23, minute=59, second=59, microsecond=999999)
        count = sum(1 for dt in created_list if day_start <= dt <= day_end)
        user_labels.append(day_start.strftime("%d-%b"))
        user_counts.append(count)

    # ---------- FAKE FEEDBACK PIE CHART ----------
    rating_distribution = [4, 2, 0, 0, 0]  # you can keep it fake

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

# ---------------- Admin Feedback Page ----------------

@app.route("/admin/feedback")
def admin_feedback():
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()

    feedbacks = cursor.execute("""
        SELECT 
            f.rating,
            f.usefulness,
            f.feedback_type,
            f.improve,
            f.feature,
            f.created_at,
            u.name,
            u.email
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()

    feedback_list = []
    for f in feedbacks:
        feedback_date = f[5]
        # Convert string to datetime if needed
        if isinstance(feedback_date, str):
            feedback_date = datetime.strptime(feedback_date, "%Y-%m-%d %H:%M:%S")
        # Replace the tuple item with datetime object
        feedback_list.append(f[:5] + (feedback_date,) + f[6:])

    current_date = datetime.now()
    return render_template("admin_feedback.html", feedbacks=feedback_list, current_date=current_date)


@app.route("/admin/feedback/export_pdf")
def export_feedback_pdf():
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    # Fetch feedback data
    conn = get_db_connection()
    cursor = conn.cursor()
    feedbacks = cursor.execute("""
        SELECT 
            u.name, u.email, f.rating, f.usefulness, f.feedback_type,
            f.improve, f.feature, f.created_at
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=20, leftMargin=20,
        topMargin=30, bottomMargin=20
    )

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle('normal', fontName='Helvetica', fontSize=10, leading=12)
    wrap_style = ParagraphStyle('wrap', fontName='Helvetica', fontSize=10, leading=12, wordWrap='CJK')

    elements = []

    # Heading
    elements.append(Paragraph("User Feedback Report", styles['Title']))
    elements.append(Spacer(1, 12))

    # Table Data
    data = [["User", "Email", "Rating", "Useful", "Type", "Improve", "Feature", "Date & Time"]]
    for f in feedbacks:
        # Convert created_at string to datetime if needed
        feedback_date = f[7]
        if isinstance(feedback_date, str):
            feedback_date = datetime.strptime(feedback_date, "%Y-%m-%d %H:%M:%S")
        # Format in AM/PM
        formatted_date = feedback_date.strftime("%Y-%m-%d %I:%M %p")

        row = [
            Paragraph(str(f[0]), wrap_style),  # User
            Paragraph(str(f[1]), wrap_style),  # Email
            Paragraph(str(f[2]), normal_style),
            Paragraph(str(f[3]), normal_style),
            Paragraph(str(f[4]), wrap_style),
            Paragraph(str(f[5]) if f[5] else "-", wrap_style),
            Paragraph(str(f[6]) if f[6] else "-", wrap_style),
            Paragraph(formatted_date, normal_style)  # Formatted date & time
        ]
        data.append(row)

    # Page width
    page_width, page_height = landscape(letter)
    left_margin = right_margin = 20
    available_width = page_width - left_margin - right_margin

    # Column widths (adjusted for better spacing)
    col_widths = [
        0.13 * available_width,  # User
        0.22 * available_width,  # Email
        0.07 * available_width,  # Rating
        0.07 * available_width,  # Useful
        0.11 * available_width,  # Type
        0.14 * available_width,  # Improve
        0.14 * available_width,  # Feature
        0.15 * available_width,  # Date & Time
    ]

    table = RLTable(data, colWidths=col_widths, repeatRows=1, hAlign='CENTER')
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4e73df")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        # Body style
        ('GRID', (0,0), (-1,-1), 0.3, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('LEFTPADDING', (0,1), (-1,-1), 5),
        ('RIGHTPADDING', (0,1), (-1,-1), 5),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]))

    # Alternating row colors for readability
    for i in range(1, len(data)):
        if i % 2 == 0:
            table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.HexColor("#f8f9fc"))]))
        else:
            table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.white)]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="user_feedback.pdf", mimetype='application/pdf')


# ---------------- Admin User Management ----------------
@app.route("/admin/users")
@app.route("/admin/users/<status>")
def admin_users(status=None):
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if status == "active":
        users = cursor.execute("SELECT * FROM users WHERE is_active = 1").fetchall()
    elif status == "inactive":
        users = cursor.execute("SELECT * FROM users WHERE is_active = 0").fetchall()
    else:
        users = cursor.execute("SELECT * FROM users").fetchall()

    conn.close()

    # Convert UTC to IST (+5:30)
    ist_users = []
    for u in users:
        created_utc = u["created_at"]
        if created_utc:
            # Convert string to datetime
            dt = datetime.strptime(created_utc, "%Y-%m-%d %H:%M:%S")
            # Add IST offset
            dt += timedelta(hours=5, minutes=30)
            u = dict(u)
            u["created_at"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        ist_users.append(u)

    return render_template("admin_users.html", users=ist_users)

@app.route("/admin/user/delete/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for("admin_users"))



# ---------------- Cycle Phase Calculation ----------------

def get_cycle_phase(last_period_date, cycle_length=28):
    today = datetime.today()
    last_date = datetime.strptime(last_period_date, "%Y-%m-%d")
    day_diff = (today - last_date).days % cycle_length
    if day_diff < 0:
        return "Unknown"
    elif day_diff <= 5:
        return "Menstrual Phase"
    elif day_diff <= 13:
        return "Follicular Phase"
    elif day_diff <= 16:
        return "Ovulation Phase"
    else:
        return "Luteal Phase"

# Wellness Summary
def generate_female_health_summary(record):
    phase = get_cycle_phase(record["last_period_date"], int(record["cycle_length"]))

    female_health_summary = f"""- Cycle Length: {record['cycle_length']} days
- Period Duration: {record['period_duration']} days
- Symptoms: {record['symptoms'] or "None"}"""

    # Wellness Suggestions
    if phase == "Menstrual Phase":
        wellness_suggestions = "- Focus on rest, hydration, iron-rich foods, and light stretching."
    elif phase == "Follicular Phase":
        wellness_suggestions = "- Energy levels improve. Good time for planning, workouts, and learning."
    elif phase == "Ovulation Phase":
        wellness_suggestions = "- Peak confidence and strength. Maintain hydration and balanced nutrition."
    else:  # Luteal Phase
        wellness_suggestions = "- Mood may fluctuate. Prioritize sleep, stress control, and self-care."

    # Add the common line
    wellness_suggestions += "\n\nFor more suggestions and good advice, click the button below to talk to the chatbot."

    return female_health_summary, wellness_suggestions


# ---------------- Main Period Page ----------------

@app.route("/period", methods=["GET", "POST"])
@login_required
def period():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    """, (session["user_id"],))
    record = cursor.fetchone()

    conn.close()

    predicted_date = None
    female_health_summary = None
    wellness_suggestions = None

    if record:
        last_date = datetime.strptime(record["last_period_date"], "%Y-%m-%d")
        predicted_date = last_date + timedelta(days=int(record["cycle_length"]))
        female_health_summary, wellness_suggestions = generate_female_health_summary(record)

    return render_template(
        "period.html",
        record=record,
        predicted_date=predicted_date,
        female_health_summary=female_health_summary,
        wellness_suggestions=wellness_suggestions,
        get_cycle_phase=get_cycle_phase  # <-- Important
    )

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
        VALUES (?, ?, ?, ?, ?)
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

@app.route("/period/history")
@login_required
def period_history():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = ?
        ORDER BY last_period_date DESC
    """, (session["user_id"],))
    history = cursor.fetchall()
    conn.close()

    return render_template("period_history.html", history=history)

@app.route("/period/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def edit_period(pid):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        cycle_length = request.form["cycle_length"]
        period_duration = request.form["period_duration"]
        symptoms = request.form["symptoms"]

        cursor.execute("""
            UPDATE period_tracking
            SET cycle_length=?, period_duration=?, symptoms=?
            WHERE id=? AND user_id=?
        """, (cycle_length, period_duration, symptoms, pid, session["user_id"]))

        conn.commit()
        conn.close()
        return redirect("/period/history")

    cursor.execute("""
        SELECT cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE id=? AND user_id=?
    """, (pid, session["user_id"]))
    record = cursor.fetchone()
    conn.close()

    return render_template("edit_period.html", record=record)


@app.route("/period/delete/<int:record_id>", methods=["POST"])
@login_required
def delete_period_record(record_id):
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM period_tracking
        WHERE id = ? AND user_id = ?
    """, (record_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/period/history")

# Period Charts Page
@app.route("/period/charts")
@login_required
def period_charts():
    if session.get("gender") != "female":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_period_date, cycle_length, period_duration, symptoms
        FROM period_tracking
        WHERE user_id = ?
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


