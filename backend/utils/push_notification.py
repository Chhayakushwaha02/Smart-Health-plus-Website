import requests
import os

def send_push_notification(device_ids, title, message):
    url = "https://onesignal.com/api/v1/notifications"

    headers = {
        "Authorization": f"Basic {os.getenv('ONESIGNAL_REST_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "app_id": os.getenv("ONESIGNAL_APP_ID"),
        "include_player_ids": device_ids,
        "headings": {"en": title},
        "contents": {"en": message}
    }

    requests.post(url, json=payload, headers=headers)
