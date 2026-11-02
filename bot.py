import os
import json
import time
import html
import random
import threading
from datetime import datetime, timezone, timedelta

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from flask import Flask

# ============ الإعدادات (من متغيرات البيئة، لا تكتب التوكن هنا) ============
TOKEN = os.environ.get("9102973043:AAHkHciWASMdh5W_wRqfizAv18E1scCIwLc")
OWNER_ID = int(os.environ.get("8652446896", "0"))
TZ_HOURS = int(os.environ.get("TZ_OFFSET", "3"))  # سوريا = 3
PORT = int(os.environ.get("PORT", "10000"))
USERS_FILE = "users.json"

if not TOKEN:
    raise SystemExit("❌ المتغير BOT_TOKEN غير موجود. أضفه في إعدادات الاستضافة.")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
START_TIME = datetime.now(timezone.utc)

# ============ تخزين المستخدمين (لأجل الإذاعة والإحصائيات) ============
_lock = threading.Lock()


def _load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


USERS = _load_users()


def _save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(USERS), f)


def remember(user_id):
    with _lock:
        if user_id not in USERS:
            USERS.add(user_id)
            _save_users()


def forget(user_id):
    with _lock:
        if user_id in USERS:
            USERS.discard(user_id)
            _save_users()


def is_owner(user_id):
    return user_id == OWNER_ID


def tracked(func):
    """يسجّل كل مستخدم يتفاعل مع البوت."""
    def wrapper(message, *args, **kwargs):
        remember(message.from_user.id)
        return func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def now_local():
    return datetime.now(timezone(timedelta(hours=TZ_HOURS)))


def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("ℹ️ معلومات", "🎲 رقم عشوائي")
    markup.add("⏰ الوقت", "🆔 إيدي حسابي")
    markup.add("❓ مساعدة")
    return markup


# ============ /start ============
@bot.message_handler(commands=["start"])
@tracked
def send_welcome(message):
    name = html.escape(message.from_user.first_name or "")
    bot.send_message(
        message.chat.id,
        f"أهلاً بك {name} 👋\nاختر من القائمة:",
        reply_markup=main_menu(),
    )


# ============ /help ============
@bot.message_handler(commands=["help"])
@tracked
def send_help(message):
    text = (
        "📌 <b>الأوامر المتاحة:</b>\n\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/myid - عرض إيديك\n"
        "/info - معلومات عنك\n"
        "/random - رقم عشوائي\n"
        "/time - الوقت الحالي\n"
    )
    if is_owner(message.from_user.id):
        text += (
            "\n👑 <b>أوامر المالك:</b>\n"
            "/stats - إحصائيات البوت\n"
            "/broadcast - إرسال رسالة جماعية\n"
        )
    bot.send_message(message.chat.id, text)


# ============ /myid ============
@bot.message_handler(commands=["myid"])
@tracked
def send_myid(message):
    user = message.from_user
    username = f"@{html.escape(user.username)}" if user.username else "لا يوجد"
    text = (
        f"🆔 <b>إيديك:</b> <code>{user.id}</code>\n"
        f"👤 <b>اسمك:</b> {html.escape(user.first_name or '')}\n"
        f"📛 <b>المعرف:</b> {username}"
    )
    bot.send_message(message.chat.id, text)


# ============ /info ============
@bot.message_handler(commands=["info"])
@tracked
def send_info(message):
    user = message.from_user
    role = "👑 مالك" if is_owner(user.id) else "👤 مستخدم"
    username = f"@{html.escape(user.username)}" if user.username else "لا يوجد"
    text = (
        f"👤 <b>الاسم:</b> {html.escape(user.first_name or '')}\n"
        f"🆔 <b>الإيدي:</b> <code>{user.id}</code>\n"
        f"📛 <b>المعرف:</b> {username}\n"
        f"🎭 <b>الصلاحية:</b> {role}"
    )
    bot.send_message(message.chat.id, text)


# ============ /random ============
@bot.message_handler(commands=["random"])
@tracked
def send_random(message):
    bot.reply_to(message, f"🎲 رقمك العشوائي: <b>{random.randint(1, 100)}</b>")


# ============ /time ============
@bot.message_handler(commands=["time"])
@tracked
def send_time(message):
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    bot.reply_to(message, f"⏰ الوقت الحالي:\n<code>{now}</code>")


# ============ /stats (للمالك فقط) ============
@bot.message_handler(commands=["stats"])
def send_stats(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ هذا الأمر للمالك فقط!")
        return
    up = datetime.now(timezone.utc) - START_TIME
    hours, rem = divmod(int(up.total_seconds()), 3600)
    minutes = rem // 60
    text = (
        "📊 <b>إحصائيات البوت:</b>\n\n"
        f"👥 <b>المستخدمون:</b> {len(USERS)}\n"
        f"⏱ <b>مدة التشغيل:</b> {hours} ساعة و{minutes} دقيقة\n"
        "✅ <b>الحالة:</b> يعمل"
    )
    bot.send_message(message.chat.id, text)


# ============ /broadcast (للمالك فقط) ============
@bot.message_handler(commands=["broadcast"])
def broadcast_start(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ هذا الأمر للمالك فقط!")
        return
    msg = bot.reply_to(message, "📢 أرسل الرسالة التي تريد إذاعتها (أو /cancel للإلغاء):")
    bot.register_next_step_handler(msg, do_broadcast)


def do_broadcast(message):
    if message.text and message.text.strip() == "/cancel":
        bot.reply_to(message, "تم الإلغاء ✅")
        return
    with _lock:
        targets = list(USERS)
    sent = failed = 0
    for uid in targets:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except ApiTelegramException as e:
            failed += 1
            if e.error_code in (400, 403):  # حظر البوت أو حذف الحساب
                forget(uid)
        except Exception:
            failed += 1
        time.sleep(0.05)  # لتفادي حدود تيليجرام
    bot.reply_to(message, f"✅ تمت الإذاعة\nوصلت: {sent}\nفشلت: {failed}")


# ============ الأزرار النصية ============
@bot.message_handler(func=lambda m: True, content_types=["text"])
@tracked
def handle_text(message):
    text = message.text
    if text == "ℹ️ معلومات":
        send_info(message)
    elif text == "🎲 رقم عشوائي":
        send_random(message)
    elif text == "⏰ الوقت":
        send_time(message)
    elif text == "🆔 إيدي حسابي":
        send_myid(message)
    elif text == "❓ مساعدة":
        send_help(message)
    else:
        bot.reply_to(message, f"📝 أرسلت: {html.escape(text)}\nجرب /help")


# ============ خادم صغير يبقي الاستضافة المجانية مستيقظة ============
web = Flask(__name__)


@web.route("/")
def home():
    return "Bot is running ✅"


@web.route("/health")
def health():
    return "ok"


def run_web():
    web.run(host="0.0.0.0", port=PORT)


# ============ التشغيل ============
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.remove_webhook()
    print("✅ البوت يعمل...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
