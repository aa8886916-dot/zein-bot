import os
import sqlite3
import logging
import requests

from flask import Flask
from threading import Thread

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =========================
# 🔐 CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

# =========================
# 🌐 KEEP ALIVE
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "🏫 ZEIN SCHOOL AI IS LIVE"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run, daemon=True).start()

# =========================
# 💾 DATABASE
# =========================

def init_db():

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (

            uid TEXT PRIMARY KEY,
            name TEXT,
            level INTEGER DEFAULT 1,
            points INTEGER DEFAULT 0

        )
    """)

    conn.commit()
    conn.close()

def add_user(uid, name="طالب"):

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    c.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, 1, 0)",
        (uid, name)
    )

    conn.commit()
    conn.close()

def update_user(uid, points=1):

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    # تحديث النقاط
    c.execute(
        "UPDATE users SET points = points + ? WHERE uid = ?",
        (points, uid)
    )

    conn.commit()

    # جلب النقاط
    c.execute(
        "SELECT points FROM users WHERE uid = ?",
        (uid,)
    )

    total_points = c.fetchone()[0]

    # حساب المستوى
    new_level = (total_points // 10) + 1

    c.execute(
        "UPDATE users SET level = ? WHERE uid = ?",
        (new_level, uid)
    )

    conn.commit()
    conn.close()

def get_user(uid):

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    c.execute(
        "SELECT name, level, points FROM users WHERE uid = ?",
        (uid,)
    )

    data = c.fetchone()

    conn.close()

    return data or ("طالب", 1, 0)

# =========================
# 🧠 MEMORY
# =========================

memory = {}

# =========================
# 🤖 AI ENGINE
# =========================

def ask_ai(messages):

    try:

        r = requests.post(

            "https://openrouter.ai/api/v1/chat/completions",

            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://replit.com",
                "X-Title": "ZeinSchoolBot"
            },

            json={

                "model": "openai/gpt-4o-mini",

                "messages": messages

            },

            timeout=60

        )

        data = r.json()

        print("AI RESPONSE:", data)

        # حماية إذا الرد فاضي
        if "choices" not in data:

            print("FULL ERROR:", data)

            return "⚠️ الذكاء الاصطناعي مشغول حالياً"

        return data["choices"][0]["message"]["content"]

    except Exception as e:

        print("AI ERROR:", e)

        return "🤕 صار خطأ بالاتصال"

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = str(update.effective_user.id)

    name = update.effective_user.first_name or "طالب"

    add_user(uid, name)

    keyboard = [

        ["📚 شرح", "📷 صورة"],

        ["📝 تلخيص", "🌍 ترجمة"],

        ["📊 مستواي"]

    ]

    await update.message.reply_text(

        f"🏫 أهلاً {name} في ZEIN SCHOOL AI 🤖\n\n"
        "📚 اكتب سؤالك أو اختر من الأزرار",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

    )

# =========================
# 🧠 TEXT HANDLER
# =========================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = str(update.effective_user.id)

    text = update.message.text

    name, level, points = get_user(uid)

    # =========================
    # 📊 المستوى
    # =========================

    if text == "📊 مستواي":

        await update.message.reply_text(

            f"👤 {name}\n"
            f"⭐ المستوى: {level}\n"
            f"🏆 النقاط: {points}"

        )

        return

    # =========================
    # 📚 الأزرار
    # =========================

    if text == "📚 شرح":

        await update.message.reply_text(
            "📚 اكتب السؤال أو اسم الدرس"
        )

        return

    if text == "📝 تلخيص":

        await update.message.reply_text(
            "📝 أرسل النص للتلخيص"
        )

        return

    if text == "🌍 ترجمة":

        await update.message.reply_text(
            "🌍 أرسل النص للترجمة"
        )

        return

    # =========================
    # 🧠 MEMORY SYSTEM
    # =========================

    if uid not in memory:

        memory[uid] = []

    memory[uid].append({

        "role": "user",

        "content": text

    })

    # حفظ آخر 6 رسائل فقط
    memory[uid] = memory[uid][-6:]

    # =========================
    # 🤖 SYSTEM PROMPT
    # =========================

    messages = [

        {

            "role": "system",

            "content": (

                "أنت أستاذ زين.\n"
                "مدرس عراقي ذكي ومحترف.\n"
                "اشرح خطوة خطوة بشكل بسيط وواضح.\n"
                "شجع الطالب دائماً.\n"
                "إذا السؤال رياضيات أو علمي فاشرح بالتفصيل.\n"
                f"اسم الطالب: {name}\n"
                f"المستوى: {level}"

            )

        }

    ] + memory[uid]

    # =========================
    # 🤖 AI RESPONSE
    # =========================

    update_user(uid, 1)

    reply = ask_ai(messages)

    # حفظ الرد
    memory[uid].append({

        "role": "assistant",

        "content": reply

    })

    memory[uid] = memory[uid][-6:]

    # تقسيم الرد الطويل
    for i in range(0, len(reply), 4000):

        await update.message.reply_text(
            reply[i:i+4000]
        )

# =========================
# 📷 PHOTO HANDLER
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        uid = str(update.effective_user.id)

        name, level, _ = get_user(uid)

        file = await context.bot.get_file(
            update.message.photo[-1].file_id
        )

        image_url = (

            f"https://api.telegram.org/file/bot"
            f"{TELEGRAM_TOKEN}/{file.file_path}"

        )

        prompt = (

            update.message.caption
            or
            "حل السؤال الموجود بالصورة خطوة خطوة"

        )

        messages = [

            {

                "role": "system",

                "content": (

                    "أنت أستاذ زين.\n"
                    "حل الصور والأسئلة الدراسية بدقة.\n"
                    "اشرح خطوة خطوة بطريقة بسيطة.\n"
                    f"اسم الطالب: {name}\n"
                    f"المستوى: {level}"

                )

            },

            {

                "role": "user",

                "content": [

                    {

                        "type": "text",

                        "text": prompt

                    },

                    {

                        "type": "image_url",

                        "image_url": {

                            "url": image_url

                        }

                    }

                ]

            }

        ]

        reply = ask_ai(messages)

        update_user(uid, 3)

        # تقسيم الرد
        for i in range(0, len(reply), 4000):

            await update.message.reply_text(
                reply[i:i+4000]
            )

    except Exception as e:

        print("PHOTO ERROR:", e)

        await update.message.reply_text(
            "⚠️ صار خطأ أثناء تحليل الصورة"
        )

# =========================
# 👑 ADMIN PANEL
# =========================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "🚫 مو مسموح"
        )

        return

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")

    total = c.fetchone()[0]

    c.execute("SELECT AVG(points) FROM users")

    avg = c.fetchone()[0] or 0

    c.execute("""

        SELECT name, points
        FROM users
        ORDER BY points DESC
        LIMIT 5

    """)

    top = c.fetchall()

    conn.close()

    top_text = "\n".join(

        [f"🏆 {r[0]} — {r[1]} نقطة" for r in top]

    ) or "لا يوجد"

    await update.message.reply_text(

        f"👑 لوحة الأدمن\n\n"
        f"👥 عدد الطلاب: {total}\n"
        f"📊 معدل النقاط: {avg:.1f}\n\n"
        f"{top_text}"

    )

# =========================
# 📢 BROADCAST
# =========================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    msg = " ".join(context.args)

    if not msg:

        await update.message.reply_text(

            "📢 مثال:\n"
            "/broadcast امتحان غداً"

        )

        return

    conn = sqlite3.connect("zein_school.db")

    c = conn.cursor()

    c.execute("SELECT uid FROM users")

    users = c.fetchall()

    conn.close()

    sent = 0

    for u in users:

        try:

            await context.bot.send_message(

                chat_id=int(u[0]),

                text=f"📢 {msg}"

            )

            sent += 1

        except Exception as e:

            print("Broadcast error:", e)

    await update.message.reply_text(

        f"✅ تم الإرسال إلى {sent} طالب"

    )

# =========================
# 🔧 MAIN
# =========================

def main():

    print("🏫 ZEIN SCHOOL AI RUNNING...")

    # فحص التوكنات
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN MISSING")

    if not OPENROUTER_KEY:
        print("❌ OPENROUTER_API_KEY MISSING")

    keep_alive()

    init_db()

    bot = ApplicationBuilder().token(
        TELEGRAM_TOKEN
    ).build()

    # Commands
    bot.add_handler(
        CommandHandler("start", start)
    )

    bot.add_handler(
        CommandHandler("admin", admin_panel)
    )

    bot.add_handler(
        CommandHandler("broadcast", broadcast)
    )

    # Messages
    bot.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    bot.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # تشغيل
    bot.run_polling(

        drop_pending_updates=True,

        allowed_updates=Update.ALL_TYPES

    )

# =========================
# 🚀 RUN
# =========================

if __name__ == "__main__":

    main()