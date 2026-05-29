from flask import Flask, request
from groq import Groq
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 🔗 Landing page URL - Netlify дээр байрлуулсны дараа энд оруул
LANDING_PAGE_URL = "https://blender-store.netlify.app"

# Анхны мессеж хадгалах (нэрээр мэндлэхэд ашиглана)
greeted_users = set()

# ========== FACEBOOK FUNCTIONS ==========

def get_user_name(sender_id):
    """Facebook-аас хэрэглэгчийн нэр авах"""
    try:
        res = requests.get(
            f"https://graph.facebook.com/{sender_id}",
            params={"fields": "first_name", "access_token": PAGE_ACCESS_TOKEN}
        )
        return res.json().get('first_name', '')
    except:
        return ''

def send_message(recipient_id, text):
    """Энгийн мессеж илгээх"""
    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}}
    )

def send_url_button(recipient_id, text, url):
    """Товчтой мессеж илгээх — зураг, захиалах"""
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

                # Хэрэглэгчийн нэр авах
                user_name = get_user_name(sender_id)
                is_first = sender_id not in greeted_users
                if is_first:
                    greeted_users.add(sender_id)

                print(f">>> [{user_name}]: {user_text}")

                # Зураг/мэдээлэл хүссэн эсэх
                image_keywords = ['зураг', 'фото', 'харах', 'үзэх', 'харуул', 'илгээ', 'photo', 'image', 'дэлгэрэнгүй']
                wants_image = any(kw in user_text.lower() for kw in image_keywords)

                # System prompt
                system_prompt = f"""Чи Flexdeal дэлгүүрийн харилцагч үйлчилгээний AI туслах юм.
Хэрэглэгчийн нэр: {user_name if user_name else 'танхим'}

{"⚡ АНХААР: Энэ хэрэглэгч АНХНЫ удаа мессеж илгээж байна. Заавал '" + user_name + "' гэж нэрээр мэндлэж, Flexdeal-д тавтай морилно уу гэж хариул!" if is_first else ""}

🛍️ БҮТЭЭГДЭХҮҮН:
Нэр: Fresh Juice Mini Portable Blender
💰 Үнэ: 79,900₮ (анхны үнэ 120,000₮-с 33% хямдарсан!)
📦 Багтаамж: 350мл
🎨 Өнгө: Ягаан 🩷, Цагаан 🤍
🔥 ЯАРАВЧИЛ: Зөвхөн 5 ширхэг үлдсэн!
⭐ Үнэлгээ: 4.9/5

⚡ ОНЦЛОГ:
- 30 секундэд шинэхэн жүүс, smoothie бэлдэнэ
- USB цэнэглэлт — powerbank, утасны цэнэглэгчээс
- Жижиг, хөнгөн — ажил, дасгал, аялалд тохиромжтой
- Цэвэрлэхэд амархан — ус нэмж асаахад л болно

💳 ЗАХИАЛГЫН АЛХАМ:
1️⃣ Нэр, утас, хаяг, өнгө (Ягаан/Цагаан) хэлнэ
2️⃣ 79,900₮-г QPay/SocialPay/MonPay-р шилжүүлнэ
3️⃣ Гүйлгээний screenshot Messenger-т илгээнэ
4️⃣ 24 цагт хүргэлт зохицуулна

⭐ СЭТГЭГДЭЛ:
- Болормаа: "Маш хурдан ирсэн, чанар гайхалтай. Өглөө бүр smoothie хийж байна!"
- Энхбаяр: "Жижигхэн ч гэсэн маш хүчтэй!"
- Ундрах: "Загвар нь маш сайхан, бүх зүйл сайн."

💡 UPSELL (заавал дагах):
- Ягаан авна гэвэл → "Цагаан өнгө ч бий, хоёуланг харьцуулж үзэх үү? 😊"
- Нэг авна гэвэл → "Найздаа бэлэг болгоод 2 авбал хэрхэн вэ?"
- Үнэ асуувал → "120,000₮-с 79,900₮ болсон — 33% хэмнэлт! 🔥"

📌 ДҮРЭМ:
- Зөвхөн МОНГОЛ хэлээр хариул
- 3-4 өгүүлбэрээс хэтрэхгүй, товч байх
- Анхны мессежид заавал нэрээр нь мэндлэх
- Мэдэхгүй зүйлд "Манай менежер танд тусална 🙏" гэж хариул"""

                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text}
                    ],
                    max_tokens=300,
                )
                reply = response.choices[0].message.content
                print(f">>> AI хариу: {reply}")

                # Мессеж илгээх
                send_message(sender_id, reply)

                # Зураг хүссэн бол landing page URL ч илгээх
                if wants_image:
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний дэлгэрэнгүй мэдээлэл, зураг болон захиалгын хуудас:",
                        LANDING_PAGE_URL
                    )

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000)
