import requests

def send_telegram_alert(message):
    TOKEN = "8793108322:AAHAnLkYOyLb9XuTbUSTttxP53pPZVzooxk"
    CHAT_ID = "1387428739" 
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ تم إرسال الرسالة للموبايل بنجاح!")
        else:
            print(f"❌ حصلت مشكلة من تليجرام: {response.text}")
    except Exception as e:
        print(f"❌ مشكلة في الاتصال بالإنترنت: {e}")

test_message = """
🚨 *El-Sharnouby Executive Alert* 🚨

مرحباً بك.. تم تفعيل البوت بنجاح وهو الآن جاهز للربط بجميع أجزاء Decision Hub! ✅
"""

send_telegram_alert(test_message)