import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
session_string = os.getenv("TELEGRAM_SESSION_STRING")

if not session_string:
    raise RuntimeError(
        "TELEGRAM_SESSION_STRING is not configured."
    )

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

SOURCE_CHANNEL = -1001580607147


async def main():
    print("\nRecent posts from International Newspapers:\n")

    async for message in client.iter_messages(
        SOURCE_CHANNEL,
        limit=100
    ):
        filename = ""

        if message.file:
            filename = message.file.name or ""

        caption = message.text or ""

        if filename:
            print(f"[{message.id}] FILE: {filename}")

        if caption:
            print(f"       TEXT: {caption}")

        if filename or caption:
            print()


with client:
    client.loop.run_until_complete(main())