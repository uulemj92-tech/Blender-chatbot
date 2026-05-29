from flask import Flask, request
from groq import Groq
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

LANDING_PAGE_URL = "https://blender-store.netlify.app"

conversation_history = {}
MAX_HISTORY = 8

# ========== KEYWORD SETS ==========

PAYMENT_KEYWORDS = [
    'данс', 'дансны', 'дансруу', 'шилжүүлэх', 'шилжүүл', 'төлбөр', 'төлөх', 'төл',
    'мөнгө', 'хаан', 'qpay', 'socialpay', 'monpay', 'захиалах', 'захиалъя',
    'захиалъ', 'яаж авах', 'хэрхэн авах', 'авахад', 'авч болох', 'авмаар',
    'худалдаж', 'payment', 'bank', 'pay', 'order', 'захиал'
]

IMAGE_KEYWORDS = [
    'зураг', 'фото', 'харах', 'үзэх', 'харуул', 'илгээ', 'photo', 'image', 'дэлгэрэнгүй'
]

PAYMENT_REPLY = """💳 Захиалгын алхам:

1️⃣ Нэр, утас, хаяг, өнгө (Ягаан🩷 / Цагаан🤍) хэлнэ үү

2️⃣ 79,900₮-г доорх дансанд шилжүүлнэ:
🏦 Хаан банк: 5057496119
(QPay / SocialPay / MonPay-р ч болно)

3️⃣ Гүйлгээний screenshot энд илгээнэ

4️⃣ 24 цагт хүргэлт зохицуулна 🚀"""

# ========== FACEBOOK FUNCTIONS ==========

def get_user_name(sender_id):
    try:
        res = requests.get(
            f"https://graph.facebook.com/{sender_id}",
            params={"fields": "first_name", "access_token": PAGE_ACCESS_TOKEN}
        )
        return res.json().get('first_name', '')
    except:
        return ''

def send_message(recipient_id, text):
    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}}
    )

def send_url_button(recipient_id, text, url):
    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": text,
                        "buttons": [{
                            "type": "web_url",
                            "url": url,
                            "title": "📸 Зураг үзэх & Захиалах"
                        }]
                    }
                }
            }
        }
    )

# ========== WEBHOOK ==========

@app.route('/webhook', methods=['GET'])
def verify():
    received = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if received == VERIFY_TOKEN:
        return challenge
    return 'Error', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    for entry in data.get('entry', []):
        for msg in entry.get('messaging', []):
            if 'message' in msg:
                sender_id = msg['sender']['id']
                user_text = msg['message'].get('text', '')

                if not user_text:
                    continue

                user_name = get_user_name(sender_id)
                text_lower = user_text.lower()
                print(f">>> [{user_name}]: {user_text}")

                wants_image = any(kw in text_lower for kw in IMAGE_KEYWORDS)
                wants_payment = any(kw in text_lower for kw in PAYMENT_KEYWORDS)

                # Захиалга / данс асуувал — шууд тогтмол хариулт илгээх
                if wants_payment:
                    print(">>> [PAYMENT TRIGGER] Захиалгын мэдээлэл илгээж байна")
                    send_message(sender_id, PAYMENT_REPLY)
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:",
                        LANDING_PAGE_URL
                    )
                    continue

                # Бусад асуултад AI хариулна
                history = conversation_history.get(sender_id, [])

                system_prompt = f"""Чи Flexdeal дэлгүүрийн харилцагч үйлчилгээний AI туслах юм.
Хэрэглэгчийн нэр: {user_name if user_name else 'танхим'}

ДҮРЭМ:
- Зөвхөн МОНГОЛ хэлээр хариул
- 2-3 өгүүлбэрт багтааж ТОВЧ хариул
- Зөвхөн анхны мессежид нэр дурдаж мэндэл, дараа нь давтахгүй
- Өмнөх яриаг санаж, уялдаатай хариул

🛍️ БҮТЭЭГДЭХҮҮН:
Fresh Juice Mini Portable Blender
💰 79,900₮ (120,000₮-с 33% хямдарсан) | 📦 350мл
🎨 Ягаан🩷, Цагаан🤍 | ⭐ 4.9/5 | 🔥 5 ширхэг үлдсэн

⚡ ОНЦЛОГ:
- 30 секундэд жүүс, smoothie
- USB цэнэглэлт (powerbank-аас ч болно)
- Жижиг, хөнгөн — ажил, дасгал, аялалд тохиромжтой

⭐ СЭТГЭГДЭЛ:
- Болормаа: "Өглөө бүр smoothie хийж байна, маш хурдан ирсэн!"
- Энхбаяр: "Жижигхэн ч гэсэн маш хүчтэй!"

💡 UPSELL:
- Ягаан авна → "Цагаан өнгө ч бий 😊"
- Нэг авна → "Найздаа бэлэг болгоод 2 авбал?"
- Үнэ асуувал → "33% хэмнэлт — 120,000₮-с 79,900₮ 🔥" """

                history.append({"role": "user", "content": user_text})
                messages = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY:]

                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=300,
                )
                reply = response.choices[0].message.content
                print(f">>> AI хариу: {reply}")

                history.append({"role": "assistant", "content": reply})
                conversation_history[sender_id] = history[-MAX_HISTORY:]

                send_message(sender_id, reply)

                if wants_image:
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:",
                        LANDING_PAGE_URL
                    )

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000)
