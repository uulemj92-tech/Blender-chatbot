from flask import Flask, request
from groq import Groq
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

LANDING_PAGE_URL = "https://blender-store.netlify.app"
SHEET_URL = "https://script.google.com/macros/s/AKfycbz1mun7kRdj7PWLYtwqFaJv8BIp6tCYFn_l04yBRF7tDc179oTy-0cp_8kZ5P3iwYZN/exec"

conversation_history = {}
MAX_HISTORY = 8

# ========== KEYWORD SETS ==========
# Кирилл болон галиг (latin үсгээр бичсэн монгол) хоёуланг хамаарна

PAYMENT_KEYWORDS = [
    # --- Кирилл ---
    'авья', 'авъя', 'авах', 'авна', 'авмаар', 'авч', 'авъ',
    'захиал', 'захиалъя', 'захиалья', 'захиалах', 'захиалмаар', 'захиална',
    'данс', 'дансаа', 'дансны', 'дансруу',
    'шилжүүл', 'шилжүүлэх', 'шилжүүлнэ',
    'төлбөр', 'төлнө', 'төлье', 'төлөх', 'төл',
    'мөнгө', 'хаан', 'банк',
    'яаж авах', 'яаж захиалах', 'хэрхэн авах',
    'худалдаж', 'худалдан',
    'үнэ', 'үнийг', 'хэд вэ', 'хэдэн', 'хямд',
    '79900', '79,900',
    'хүргэлт', 'хүргэнэ', 'хэзээ ирэх',
    'ягаан', 'цагаан', 'ямар өнгө',

    # --- Галиг (latin үсгээр бичсэн монгол) ---
    'avya', 'avah', 'avna', 'avmar', 'avch', 'avj', 'aviy',
    'zahial', 'zahialya', 'zahialah', 'zahialna', 'zahialmar',
    'dans', 'dansaa', 'dansny', 'dansruu',
    'shiljuul', 'shiljuuleh', 'shiljuulne',
    'tulbur', 'tulne', 'tuleh', 'tulye',
    'mungu', 'mongo', 'munguu',
    'haan', 'khan', 'bank', 'qpay', 'socialpay', 'monpay',
    'yaaj avah', 'yaaj zahialah', 'herhen avah', 'herhen zahialah',
    'hudaldaj', 'hudaldah', 'buy', 'order', 'purchase',
    'une', 'unee', 'hed ve', 'heduun', 'hyamd',
    '79900', '79,900',
    'hurgelt', 'hurgene', 'hezee ireh',
    'yagaan', 'tsagaan', 'yamar ungu', 'yamar ongu',
]

IMAGE_KEYWORDS = [
    # --- Кирилл ---
    'зураг', 'зурагтай', 'зурагнь', 'фото',
    'харах', 'харуул', 'харъя', 'үзэх', 'үзүүл', 'үзье',
    'илгээ', 'видео', 'дэлгэрэнгүй',
    'холбоос', 'хаяг', 'сайт', 'мэдээлэл', 'танилцуул',

    # --- Галиг ---
    'zurag', 'foto', 'photo', 'image',
    'harah', 'haruul', 'uzeh', 'uzuul',
    'ilgee', 'video',
    'delgerengui', 'delgerenguui',
    'holboos', 'hayag', 'sait', 'medeelel', 'tanilatsuul',
    'link', 'website',
]

PAYMENT_REPLY = """💳 Захиалгын алхам:

1️⃣ Нэр, утас, хаяг, өнгө (Ягаан🩷 / Цагаан🤍) хэлнэ үү

2️⃣ 79,900₮-г доорх дансанд шилжүүлнэ:
🏦 Хаан банк: 5057496119
(QPay / SocialPay / MonPay-р ч болно)

3️⃣ Гүйлгээний screenshot энд илгээнэ

4️⃣ 24 цагт хүргэлт зохицуулна 🚀"""

MANAGER_REPLY = "Манай менежертэй шууд холбогдоорой 📞 88920304"

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

def save_payment_to_sheet(user_name, sender_id, image_url):
    """Төлбөрийн баримтыг Google Sheets-т хадгалах"""
    try:
        import json
        from datetime import datetime
        # Landing page-тэй ЯВАН ТААРАХ key нэрс: name, phone, addr, color, огноо
        data = {
            "name":  user_name or "Messenger хэрэглэгч",
            "phone": "📸 ТӨЛБӨРИЙН БАРИМТ",
            "addr":  image_url,          # зургийн URL → addr баганад
            "color": "Зураг илгээсэн",
            "огноо": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        requests.post(
            SHEET_URL,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(data, ensure_ascii=False),
            timeout=10
        )
        print(f">>> [SHEET] Төлбөрийн баримт хадгаллаа: {user_name}")
    except Exception as e:
        print(f">>> [SHEET ERROR] {e}")

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

                # ── Зураг (төлбөрийн баримт) ирвэл → Sheets-т хадгалах ──
                attachments = msg['message'].get('attachments', [])
                for att in attachments:
                    if att.get('type') == 'image':
                        image_url = att.get('payload', {}).get('url', '')
                        user_name = get_user_name(sender_id)
                        print(f">>> [IMAGE] {user_name} зураг илгээлээ")
                        save_payment_to_sheet(user_name, sender_id, image_url)
                        send_message(sender_id,
                            f"✅ Баримт хүлээн авлаа{(' ' + user_name + '!') if user_name else '!'}\n\n"
                            "Бид шалгаад 24 цагт хүргэлтийн мэдээлэл явуулна 🚀\n"
                            "Асуух зүйл байвал: 📞 88920304"
                        )

                if not user_text:
                    continue

                user_name = get_user_name(sender_id)
                text_lower = user_text.lower()
                print(f">>> [{user_name}]: {user_text}")

                wants_image   = any(kw in text_lower for kw in IMAGE_KEYWORDS)
                wants_payment = any(kw in text_lower for kw in PAYMENT_KEYWORDS)

                # ── Захиалга / данс → тогтмол хариулт + landing page ──
                if wants_payment:
                    print(">>> [PAYMENT] Захиалгын мэдээлэл илгээж байна")
                    send_message(sender_id, PAYMENT_REPLY)
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:",
                        LANDING_PAGE_URL
                    )
                    continue

                # ── Зураг / link хүсвэл → шууд landing page ──
                if wants_image:
                    send_url_button(
                        sender_id,
                        "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:",
                        LANDING_PAGE_URL
                    )
                    continue

                # ── Бусад асуултад AI хариулна ──
                history = conversation_history.get(sender_id, [])

                system_prompt = f"""Чи "Flexdeal" дэлгүүрийн Messenger chatbot юм.
Хэрэглэгчийн нэр: {user_name if user_name else 'танхим'}

ХАТУУ ДҮРЭМ:
- Ямар хэлээр бичсэн ч (кирилл, галиг, англи) ЗӨВХӨН МОНГОЛ КИРИЛЛ үсгээр хариул
- Хариулт 1-3 өгүүлбэрт багтаана, маш товч байх
- Зөвхөн анхны мессежид нэрээр нь нэг удаа мэндэл, дараа нь давтахгүй
- Өмнөх яриаг санаж уялдаатай хариул
- Мэдэхгүй бол заавал: "Манай менежертэй холбогдоорой 📞 88920304" гэж хариул

БҮТЭЭГДЭХҮҮН:
Fresh Juice Mini Portable Blender
💰 79,900₮ (120,000₮-с 33% хямдарсан)
📦 350мл | 🎨 Ягаан🩷 Цагаан🤍 | ⭐ 4.9/5 | 🔥 Цөөхөн үлдлээ!

ОНЦЛОГ:
• 30 секундэд жүүс, smoothie бэлдэнэ
• USB цэнэглэлт — powerbank, утаснаас
• Жижиг, хөнгөн — ажил, дасгал, аялалд тохиромжтой
• Цэвэрлэхэд амархан — ус нэмж асаахад л болно

СЭТГЭГДЭЛ:
• Болормаа: "Өглөө бүр smoothie хийж байна, маш хурдан ирлээ!"
• Энхбаяр: "Жижигхэн ч гэсэн маш хүчтэй, гайхалтай!"

UPSELL:
• Ягаан авна → "Цагаан өнгө ч бий, аль нь таалагдах бол? 😊"
• Нэг авна → "Найздаа бэлэг болгоод 2 авбал хэрхэн вэ?"
• Үнэ асуувал → "120,000₮-с 79,900₮ — 33% хэмнэлт 🔥" """

                history.append({"role": "user", "content": user_text})
                messages = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY:]

                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=300,
                )
                reply = response.choices[0].message.content

                # AI "мэдэхгүй" гэвэл менежерийн дугаар илгээх
                if any(w in reply for w in ['мэдэхгүй', 'мэдэхгүй байна', 'менежер']):
                    reply = MANAGER_REPLY

                print(f">>> AI хариу: {reply}")

                history.append({"role": "assistant", "content": reply})
                conversation_history[sender_id] = history[-MAX_HISTORY:]

                send_message(sender_id, reply)

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000)
