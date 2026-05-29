from flask import Flask, request
from groq import Groq
import requests
import os
import re
import json
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
groq_client     = Groq(api_key=os.environ.get("GROQ_API_KEY"))

LANDING_PAGE_URL = "https://blender-store.netlify.app"
SHEET_URL = "https://script.google.com/macros/s/AKfycbxXNph0oxL-VQCJXDGXALGvduzJVpMeDqBqDg2bxWruqYYCyQL7uLogBMWuw6dJFz0j/exec"

conversation_history = {}   # {sender_id: [{role, content}]}
saved_orders         = set() # захиалга хадгалсан sender_id-ууд
MAX_HISTORY = 8

PHONE_RE = re.compile(r'\b[89]\d{7}\b')

# ========== KEYWORD SETS ==========

PAYMENT_KEYWORDS = [
    'авья','авъя','авах','авна','авмаар','авч','авъ',
    'захиал','захиалъя','захиалья','захиалах','захиалмаар','захиална',
    'данс','дансаа','дансны','дансруу',
    'шилжүүл','шилжүүлэх','шилжүүлнэ',
    'төлбөр','төлнө','төлье','төлөх','төл',
    'мөнгө','хаан','банк',
    'яаж авах','яаж захиалах','хэрхэн авах',
    'худалдаж','худалдан',
    'үнэ','үнийг','хэд вэ','хэдэн','хямд',
    '79900','79,900',
    'хүргэлт','хүргэнэ','хэзээ ирэх',
    'ягаан','цагаан','ямар өнгө',
    'avya','avah','avna','avmar','avch','avj',
    'zahial','zahialya','zahialah','zahialna','zahialmar',
    'dans','dansaa','dansny','dansruu',
    'shiljuul','shiljuuleh','shiljuulne',
    'tulbur','tulne','tuleh','tulye',
    'mungu','mongo','munguu',
    'haan','khan','bank','qpay','socialpay','monpay',
    'yaaj avah','yaaj zahialah','herhen avah',
    'hudaldaj','hudaldah','buy','order','purchase',
    'une','unee','hed ve','heduun','hyamd',
    'hurgelt','hurgene','hezee ireh',
    'yagaan','tsagaan','yamar ungu','yamar ongu',
]

IMAGE_KEYWORDS = [
    'зураг','зурагтай','зурагнь','фото',
    'харах','харуул','харъя','үзэх','үзүүл','үзье',
    'илгээ','видео','дэлгэрэнгүй',
    'холбоос','хаяг','сайт','мэдээлэл','танилцуул',
    'zurag','foto','photo','image',
    'harah','haruul','uzeh','uzuul',
    'ilgee','video',
    'delgerengui','delgerenguui',
    'holboos','hayag','sait','medeelel',
    'link','website',
]

PAYMENT_REPLY = """💳 Захиалгын алхам:

1️⃣ Нэр, утас, хаяг, өнгө (Ягаан🩷 / Цагаан🤍) хэлнэ үү

2️⃣ 79,900₮-г доорх дансанд шилжүүлнэ:
🏦 Хаан банк: 5057496119
(QPay / SocialPay / MonPay-р ч болно)

3️⃣ Гүйлгээний screenshot энд илгээнэ

4️⃣ 24 цагт хүргэлт зохицуулна 🚀"""

MANAGER_REPLY = "Манай менежертэй шууд холбогдоорой 📞 88920304"

# ========== SHEET FUNCTIONS ==========

def save_order_to_sheet(sender_id, user_name, history):
    """Яриаас утасны дугаар илэрвэл захиалгыг Sheets-т хадгалах"""
    if sender_id in saved_orders:
        return

    phone = ''
    color = ''
    addr_parts = []

    for msg in history:
        if msg['role'] == 'user':
            text = msg['content']
            m = PHONE_RE.search(text)
            if m and not phone:
                phone = m.group()
            tl = text.lower()
            if any(c in tl for c in ['ягаан','yagaan','pink','ягаан']):
                color = 'Ягаан'
            elif any(c in tl for c in ['цагаан','tsagaan','white']):
                color = 'Цагаан'
            if len(text) > 8:
                addr_parts.append(text)

    if not phone:
        return  # Утасны дугаар байхгүй = захиалга биш

    addr = ' | '.join(addr_parts[:2])[:120] if addr_parts else ''

    data = {
        "type":      "order",
        "name":      user_name or "",
        "phone":     phone,
        "addr":      addr,
        "color":     color,
        "sender_id": sender_id,
        "огноо":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        requests.post(SHEET_URL,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(data, ensure_ascii=False),
            timeout=10)
        saved_orders.add(sender_id)
        print(f">>> [ORDER SAVED] {user_name} - {phone}")
    except Exception as ex:
        print(f">>> [SHEET ERROR] {ex}")


def save_payment_to_sheet(user_name, sender_id, image_url):
    """Төлбөрийн зургийг Sheets-т хадгалах — sender_id-аар мөр хайна"""
    try:
        data = {
            "type":      "payment",
            "name":      user_name or "Messenger хэрэглэгч",
            "sender_id": sender_id,
            "image_url": image_url,
            "огноо":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        requests.post(SHEET_URL,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(data, ensure_ascii=False),
            timeout=10)
        print(f">>> [PAYMENT SAVED] {user_name}")
    except Exception as ex:
        print(f">>> [SHEET ERROR] {ex}")

# ========== FACEBOOK FUNCTIONS ==========

def get_user_name(sender_id):
    try:
        res = requests.get(
            f"https://graph.facebook.com/{sender_id}",
            params={"fields": "first_name", "access_token": PAGE_ACCESS_TOKEN})
        return res.json().get('first_name', '')
    except:
        return ''

def send_message(recipient_id, text):
    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params={"access_token": PAGE_ACCESS_TOKEN},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}})

def send_url_button(recipient_id, text, url, sender_id=None):
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
                        "buttons": [{"type": "web_url",
                                     "url": f"{url}?uid={sender_id}" if sender_id else url,
                                     "title": "📸 Зураг үзэх & Захиалах"}]
                    }
                }
            }
        })

# ========== WEBHOOK ==========

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge')
    return 'Error', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    for entry in data.get('entry', []):
        for msg in entry.get('messaging', []):
            if 'message' not in msg:
                continue

            sender_id = msg['sender']['id']
            user_text = msg['message'].get('text', '')

            # ── Зураг (төлбөрийн баримт) ──
            for att in msg['message'].get('attachments', []):
                if att.get('type') == 'image':
                    image_url = att.get('payload', {}).get('url', '')
                    user_name = get_user_name(sender_id)
                    print(f">>> [IMAGE] {user_name}")
                    save_payment_to_sheet(user_name, sender_id, image_url)
                    send_message(sender_id,
                        f"✅ Баримт хүлээн авлаа{(' ' + user_name + '!') if user_name else '!'}\n\n"
                        "Бид шалгаад 24 цагт хүргэлтийн мэдээлэл явуулна 🚀\n"
                        "Асуух зүйл байвал: 📞 88920304")

            if not user_text:
                continue

            user_name  = get_user_name(sender_id)
            text_lower = user_text.lower()
            print(f">>> [{user_name}]: {user_text}")

            wants_image   = any(kw in text_lower for kw in IMAGE_KEYWORDS)
            wants_payment = any(kw in text_lower for kw in PAYMENT_KEYWORDS)

            # ── Захиалга / данс ──
            if wants_payment:
                send_message(sender_id, PAYMENT_REPLY)
                send_url_button(sender_id,
                    "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:", LANDING_PAGE_URL, sender_id)
                continue

            # ── Зураг хүсэх ──
            if wants_image:
                send_url_button(sender_id,
                    "👇 Бүтээгдэхүүний зураг, дэлгэрэнгүй мэдээлэл:", LANDING_PAGE_URL, sender_id)
                continue

            # ── AI хариулт ──
            history = conversation_history.get(sender_id, [])

            system_prompt = f"""Чи "Flexdeal" дэлгүүрийн Messenger chatbot юм.
Хэрэглэгчийн нэр: {user_name if user_name else 'танхим'}

ХАТУУ ДҮРЭМ:
- Ямар хэлээр бичсэн ч ЗӨВХӨН МОНГОЛ КИРИЛЛ үсгээр хариул
- Хариулт 1-3 өгүүлбэрт багтаана, маш товч байх
- Зөвхөн анхны мессежид нэрээр нь нэг удаа мэндэл
- Өмнөх яриаг санаж уялдаатай хариул
- Мэдэхгүй бол: "Манай менежертэй холбогдоорой 📞 88920304"

БҮТЭЭГДЭХҮҮН:
Fresh Juice Mini Portable Blender
💰 79,900₮ (120,000₮-с 33% хямдарсан)
📦 350мл | 🎨 Ягаан🩷 Цагаан🤍 | ⭐ 4.9/5 | 🔥 Цөөхөн үлдлээ!

ОНЦЛОГ:
• 30 секундэд жүүс, smoothie бэлдэнэ
• USB цэнэглэлт — powerbank, утаснаас
• Жижиг, хөнгөн — ажил, дасгал, аялалд тохиромжтой

SЭТГЭГДЭЛ:
• Болормаа: "Өглөө бүр smoothie хийж байна!"
• Энхбаяр: "Жижигхэн ч гэсэн маш хүчтэй!"

UPSELL:
• Ягаан авна → "Цагаан өнгө ч бий 😊"
• Нэг авна → "Найздаа бэлэг болгоод 2 авбал?"
• Үнэ асуувал → "33% хэмнэлт 🔥" """

            history.append({"role": "user", "content": user_text})
            messages = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY:]

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=300,
            )
            reply = response.choices[0].message.content

            if any(w in reply for w in ['мэдэхгүй','менежер']):
                reply = MANAGER_REPLY

            history.append({"role": "assistant", "content": reply})
            conversation_history[sender_id] = history[-MAX_HISTORY:]

            send_message(sender_id, reply)

    return 'OK'

if __name__ == '__main__':
    app.run(port=5000)
