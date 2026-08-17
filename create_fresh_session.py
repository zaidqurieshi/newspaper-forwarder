import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient(
    "fresh_newspaper_session",
    api_id,
    api_hash
)


async def main():
    await client.start()

    if not await client.is_user_authorized():
        print("Telegram authorization failed.")
        return

    session_string = StringSession.save(client.session)

    print("\nSESSION_STRING_START")
    print(session_string)
    print("SESSION_STRING_END\n")

    await client.disconnect()


with client:
    client.loop.run_until_complete(main())