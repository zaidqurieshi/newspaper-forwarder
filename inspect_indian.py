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
        "TELEGRAM_SESSION_STRING is missing from .env"
    )


client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)


async def main():

    channel_id = -1003645659794

    print()
    print("======================================")
    print(" INDIAN CHANNEL")
    print("======================================")

    entity = await client.get_entity(
        channel_id
    )

    print(
        "Channel:",
        getattr(entity, "title", "Unknown")
    )

    print()

    async for message in client.iter_messages(
        entity,
        limit=30
    ):

        filename = ""

        if message.file:
            filename = message.file.name or ""

        caption = message.text or ""

        print(
            f"[{message.id}] "
            f"FILE: {filename}"
        )

        if caption:
            print(
                f"      CAPTION: {caption}"
            )

        print()


with client:
    client.loop.run_until_complete(
        main()
    )