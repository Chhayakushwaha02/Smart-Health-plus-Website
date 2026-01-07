from flask import Blueprint, request, jsonify, session, redirect, render_template

# Create Blueprint
auth_bp = Blueprint("auth_bp", __name__)

# In-memory user storage (for testing, replace with DB later)
users = []

# ---------------- REGISTER ----------------
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    # Check if email already exists
    for user in users:
        if user["email"] == email:
            return jsonify({"success": False, "message": "Email already registered!"})

    users.append({"name": name, "email": email, "password": password})
    return jsonify({"success": True, "message": "Registered successfully!"})

# ---------------- LOGIN ----------------
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    for user in users:
        if user["email"] == email and user["password"] == password:
            session["username"] = email.split("@")[0]
            session["email"] = email
            return jsonify({"success": True})

    return jsonify({"success": False, "message": "Invalid credentials"})

# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/auth")

# ---------------- AUTH PAGE ----------------
@auth_bp.route("/auth")
def auth_page():
    # If already logged in, redirect to dashboard
    if "username" in session:
        return redirect("/dashboard")
    return render_template("auth.html")
