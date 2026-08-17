import os
import json

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
session_string = os.getenv("TELEGRAM_SESSION_STRING")

INDIAN_CHANNEL = -1003645659794
INTERNATIONAL_CHANNEL = -1001580607147
DESTINATION_CHANNEL = -1004486510815

OUTPUT_FILE = "forwarded_messages.json"

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)


async def main():

    print("Building duplicate database...")
    print("No messages will be sent.\n")

    indian_ids = set()
    international_ids = set()

    # --------------------------------------------------------
    # Get recent source messages
    # --------------------------------------------------------

    indian_messages = {}

    async for message in client.iter_messages(
        INDIAN_CHANNEL,
        limit=300
    ):
        if message.file:
            indian_messages[message.file.name] = message.id

    international_messages = {}

    async for message in client.iter_messages(
        INTERNATIONAL_CHANNEL,
        limit=300
    ):
        if message.file:
            international_messages[message.file.name] = message.id

    # --------------------------------------------------------
    # Examine destination messages
    #
    # Because destination files are uploaded copies, Telegram
    # doesn't retain the original source message ID.
    #
    # We therefore match destination filenames against the
    # source filenames.
    # --------------------------------------------------------

    destination_filenames = set()

    async for message in client.iter_messages(
        DESTINATION_CHANNEL,
        limit=500
    ):

        if not message.file:
            continue

        filename = message.file.name

        if filename:
            destination_filenames.add(
                filename.lower().strip()
            )

    # --------------------------------------------------------
    # Match destination filenames to recent source messages
    # --------------------------------------------------------

    for filename, message_id in indian_messages.items():

        if not filename:
            continue

        if filename.lower().strip() in destination_filenames:
            indian_ids.add(message_id)

    for filename, message_id in international_messages.items():

        if not filename:
            continue

        if filename.lower().strip() in destination_filenames:
            international_ids.add(message_id)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    data = {
        "indian": sorted(indian_ids),
        "international": sorted(international_ids)
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2
        )

    print("======================================")
    print("Database seeded successfully.")
    print("======================================")
    print(f"Indian messages: {len(indian_ids)}")
    print(f"International messages: {len(international_ids)}")
    print()
    print("No messages were sent.")


with client:
    client.loop.run_until_complete(main())