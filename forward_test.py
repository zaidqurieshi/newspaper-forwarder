import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("newspaper_session", api_id, api_hash)

SOURCE_CHANNEL = -1003645659794
DESTINATION_CHANNEL = -1004486510815

# This is the Greater Kashmir post we found earlier.
TEST_MESSAGE_ID = 33644


async def main():
    print("Forwarding test newspaper...")

    await client.forward_messages(
        DESTINATION_CHANNEL,
        TEST_MESSAGE_ID,
        from_peer=SOURCE_CHANNEL
    )

    print("Forward successful!")


with client:
    client.loop.run_until_complete(main())