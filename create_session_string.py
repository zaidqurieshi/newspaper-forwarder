import os
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.sessions import StringSession


load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")


print()
print("========================================")
print(" CREATE FRESH TELEGRAM SESSION")
print("========================================")
print()
print("This creates a NEW session for the website.")
print("Do not use the existing session string.")
print()


with TelegramClient(
    StringSession(),
    API_ID,
    API_HASH
) as client:

    print("Connecting to Telegram...")
    print()

    client.start()

    print()
    print("========================================")
    print(" NEW SESSION CREATED")
    print("========================================")
    print()

    print(
        client.session.save()
    )

    print()
    print("========================================")
    print(" COPY THE SESSION STRING ABOVE")
    print("========================================")
    print()