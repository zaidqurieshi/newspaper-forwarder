import os

if os.getenv("RUN_LIVE_TELEGRAM_TESTS") != "1":
    print("SKIPPED live Telegram test; set RUN_LIVE_TELEGRAM_TESTS=1 to run it")
    raise SystemExit(0)

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("newspaper_session", api_id, api_hash)


async def main():
    me = await client.get_me()

    print("\nTelegram connection successful!")
    print(f"Logged in as: {me.first_name}")
    print(f"Username: @{me.username}" if me.username else "No username set")


with client:
    client.loop.run_until_complete(main())