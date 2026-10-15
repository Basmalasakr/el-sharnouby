import requests

TELEGRAM_TOKEN = "8793108322:AAHAnLkYOyLb9XuTbUSTttxP53pPZVzooxk"
TELEGRAM_CHAT_ID = "1387428739"

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Approve Action", "callback_data": "approve_action"},
                {"text": "Reject", "callback_data": "reject_action"}
            ]
        ]
    }
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return True
        return False
    except Exception:
        return False