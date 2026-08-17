from dotenv import load_dotenv
from telethon import TelegramClient
import os

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("newspaper_session", api_id, api_hash)

SOURCE_CHANNEL = 1003645659794


async def main():
    print("\nRecent posts from INDIAN English:\n")

    async for message in client.iter_messages(SOURCE_CHANNEL, limit=20):
        text = (message.text or "").strip().replace("\n", " ")

        if message.file:
            filename = message.file.name or "(unnamed file)"
            print(f"[{message.id}] FILE: {filename}")
            if text:
                print(f"       TEXT: {text[:200]}")
        elif text:
            print(f"[{message.id}] TEXT: {text[:200]}")


with client:
    client.loop.run_until_complete(main())