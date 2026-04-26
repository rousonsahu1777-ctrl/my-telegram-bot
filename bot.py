import os
import sqlite3
import logging
import re
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))
API_URL = "https://ansh-apis.is-dev.org/api/num-info2"
API_KEY = "luffy"

db = sqlite3.connect("num_bot.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, credits INTEGER DEFAULT 3, approved INTEGER DEFAULT 1, registered_date TEXT, searches INTEGER DEFAULT 0)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, type TEXT, timestamp TEXT)""")
db.commit()
logging.basicConfig(level=logging.INFO)

main_keyboard = ReplyKeyboardMarkup([["🔍 Search Number", "👤 My Profile"], ["💰 Buy Credits", "🎟️ Redeem Code"], ["📞 Contact Owner"]], resize_keyboard=True)

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return {'user_id': result[0], 'username': result[1], 'credits': result[2], 'approved': result[3], 'registered_date': result[4], 'searches': result[5]}
    return None

def add_user(user_id, username):
    if not get_user(user_id):
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (user_id, username, 3, 1, datetime.now().isoformat(), 0))
        db.commit()
        return True
    return False

def deduct_credit(user_id):
    cursor.execute("UPDATE users SET credits = credits - 1, searches = searches + 1 WHERE user_id = ?", (user_id,))
    db.commit()
    cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]

def add_credits(user_id, amount):
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    db.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username or user.first_name)
    await update.message.reply_text(f"✨ Welcome {user.first_name}! ✨\n🎁 3 free credits!\n🔍 1 search = 1 credit", reply_markup=main_keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    user_data = get_user(user.id)
    
    if not user_data:
        add_user(user.id, user.username or user.first_name)
        user_data = get_user(user.id)
    
    if text == "👤 My Profile":
        await update.message.reply_text(f"👤 PROFILE\n🆔 ID: {user.id}\n💰 Credits: {user_data['credits']}\n🔍 Searches: {user_data['searches']}")
    
    elif text == "📞 Contact Owner":
        await update.message.reply_text("📞 Contact: @tw_hacker")
    
    elif text == "🔍 Search Number":
        if user_data['credits'] <= 0:
            await update.message.reply_text("❌ No credits!")
            return
        await update.message.reply_text("📱 Send 10-digit number:")
        context.user_data["waiting_for_number"] = True
    
    elif text == "💰 Buy Credits":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("10 Credits - ₹10", callback_data="buy_10")],
            [InlineKeyboardButton("25 Credits - ₹20", callback_data="buy_25")],
            [InlineKeyboardButton("50 Credits - ₹35", callback_data="buy_50")],
            [InlineKeyboardButton("100 Credits - ₹60", callback_data="buy_100")]
        ])
        await update.message.reply_text("💎 SELECT PACKAGE:", reply_markup=keyboard)
    
    elif text == "🎟️ Redeem Code":
        await update.message.reply_text("🎟️ Send promo code:\nCodes: WELCOME10, FREETRIAL, TW_HACKER")
        context.user_data["waiting_for_promo"] = True
    
    elif context.user_data.get("waiting_for_number"):
        number = re.sub(r'\D', '', text)
        if len(number) == 10:
            new_credits = deduct_credit(user.id)
            await update.message.reply_text(f"🔍 Searching... (Credits left: {new_credits})")
            try:
                response = requests.get(API_URL, params={"key": API_KEY, "num": number}, timeout=10)
                data = response.json()
                if data.get("success") == "true":
                    info = data["data"][0]
                    await update.message.reply_text(f"📱 Number: {info.get('num')}\n👤 Name: {info.get('name')}")
                else:
                    await update.message.reply_text("❌ No info found")
            except:
                await update.message.reply_text("⚠️ API error")
            context.user_data.pop("waiting_for_number")
        else:
            await update.message.reply_text("❌ Send 10-digit number")
    
    elif context.user_data.get("waiting_for_promo"):
        promos = {"WELCOME10": 5, "FREETRIAL": 3, "TW_HACKER": 10}
        code = text.upper()
        if code in promos:
            add_credits(user.id, promos[code])
            await update.message.reply_text(f"✅ +{promos[code]} credits added!")
        else:
            await update.message.reply_text("❌ Invalid code")
        context.user_data.pop("waiting_for_promo", None)
    
    else:
        await update.message.reply_text("Use buttons:", reply_markup=main_keyboard)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("buy_"):
        await query.edit_message_text("💳 Pay to: twhacker@okhdfcbank\nSend screenshot.\nOwner will add credits.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    port = int(os.environ.get("PORT", 8080))
    app.run_webhook(listen="0.0.0.0", port=port, url_path="/webhook", webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook")

if __name__ == "__main__":
    main()
