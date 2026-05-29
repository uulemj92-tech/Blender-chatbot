from flask import Flask, request
from groq import Groq
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

LANDING_PAGE_URL = "https://blender-store.netlify.app"

# Яриа түүх хадгалах (сервер унтахаас өмнөх хугацаанд)
conversation_history = {}  # {sender_id: [{"role": ..., "content": ...}, ...]}
MAX_HISTORY = 8  # Хамгийн сүүлийн 8 мессеж хадгална

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
                print(f">>> [{user_name}]: {user_text}")

                # Яриа түүх авах
                history = conversation_history.get(sender_id, [])

                # Зураг/мэдээлэл хүссэн эсэх
                image_keywords = ['зураг', 'фото', 'харах', 'үзэх', 'харуул', 'илгээ', 'photo', 'image', 'дэлгэрэнгүй']
                wants_image = any(kw in user_text.lower() for kw in image_keywords)

                system_prompt = f"""Чи Flexdeal дэлгүүрийн харилцагч үйлчилгээний AI туслах юм.
Хэрэглэгчийн нэр: {user_name if user_name else 'танхим'}

ЧУХАЛ ДҮРЭМ:
- Зөвхөн МОНГОЛ хэлээр хариул
- 2-3 өгүүлбэрээс хэтрэхгүй, ТОВЧ байх
- Дахин дахин мэндлэхгүй — зөвхөн хэрэглэгч АНХНЫ мессеж илгээхэд нэг л удаа "{user_name}-д сайн байна уу 👋" гэж мэндэл, дараагийн мессежүүдэд огт мэндлэхгүй
- Яриа түүхийг анхаарч, өмнө ямар зүйл ярьснаа санаж байх
- Мэдэхгүй зүйлд "Манай менежер танд тусална 🙏" гэж хариул

🛍️ БҮТЭЭГДЭХҮҮН:
Нэр: Fresh Juice Mini Portable Blender
💰 Үнэ: 79,900₮ (анхны үнэ 120,000₮-с 33% хямдарсан!)
📦 Багтаамж: 350мл | 🎨 Өнгө: Ягаан 🩷, Цагаан 🤍
🔥 Зөвхөн 5 ширхэг үлдсэн! ⭐ 4.9/5 үнэлгээ

⚡ ОНЦЛОГ:
- 30 секундэд шинэхэн жүүс, smoothie
- USB цэнэглэлт — powerbank, утаснаас
- Жижиг, хөнгөн — ажил, дасгал, аялалд

💳 ЗАХИАЛГЫН АЛХАМ — данс асуувал ЗААВАЛ энийг хэл:
1️⃣ Нэр, утас, хаяг, өнгө хэлнэ үү
2️⃣ 79,900₮-г ХААН БАНК руу шилжүүлнэ:
   👉 Дансны дугаар: 5057496119
   (QPay / SocialPay / MonPay-р ч болно)
3️⃣ Гүйлгээний screenshot Messenger-т илгээнэ
4️⃣ 24 цагт хүргэлт зохицуулна

⭐ СЭТГЭГДЭЛ:
- Болормаа: "Маш хурдан ирсэн, өглөө бүр smoothie хийж байна!"
- Энхбаяр: "Жижигхэн ч гэсэн маш хүчтэй!"

💡 UPSELL:
- Ягаан авна → "Цагаан өнгө ч бий 😊"
- Нэг авна → "Найздаа бэлэг болгоод 2 авбал?"
- Үнэ асуувал → "120,000₮-с 79,900₮ — 33% хэмнэлт! 🔥" """

                # Яриа түүхэд хэрэглэгчийн мессеж нэмэх
                history.append({"role": "user", "content": user_text})

                # AI-д илгээх мессежийн жагсаалт
                messages = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY:]

                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=300,
                )
                reply = response.choices[0].message.content
                print(f">>> AI хариу: {reply}")

                # Яриа түүхэд AI хариу нэмэх
                history.append({"role": "assistant", "content": reply})

                # Хамгийн сүүлийн MAX_HISTORY мессежийг л хадгална
                conversation_history[sender_id] = history[-MAX_HISTORY:]

                send_message(sender_id, reply)

                if wants_image:
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний дэлгэрэнгүй мэдээлэл, зураг болон захиалгын хуудас:",
                        LANDING_PAGE_URL
                    )

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000)
