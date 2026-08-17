import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

client = TelegramClient(
    StringSession(os.getenv("TELEGRAM_SESSION_STRING")),
    int(os.getenv("TELEGRAM_API_ID")),
    os.getenv("TELEGRAM_API_HASH")
)

async def main():
    print("======================================")
    print(" INTERNATIONAL SOURCE")
    print("======================================")

    async for m in client.iter_messages(
        -1001580607147,
        limit=30
    ):
        if m.file:
            print(
                m.id,
                "|",
                m.file.name,
                "|",
                m.text or ""
            )

with client:
    client.loop.run_until_complete(main())
