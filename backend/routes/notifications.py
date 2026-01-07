from flask import Blueprint, request, jsonify
from database import get_db_connection

notification_bp = Blueprint("notification_bp", __name__)

@notification_bp.route("/register-device", methods=["POST"])
def register_device():
    user_id = request.json.get("user_id")
    device_id = request.json.get("device_id")
    platform = request.json.get("platform", "web")

    if not user_id or not device_id:
        return jsonify({"error": "Missing data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO user_devices (user_id, device_id, platform)
        VALUES (?, ?, ?)
    """, (user_id, device_id, platform))

    conn.commit()
    conn.close()

    return jsonify({"message": "Device registered successfully"})
