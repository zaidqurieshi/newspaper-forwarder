import os
import re

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

SOURCE_CHANNEL = -1003645659794
DESTINATION_CHANNEL = -1004486510815


def identify_paper(filename, caption):
    text = f"{filename} {caption}".lower()

    # Greater Kashmir
    if re.search(r"greater\s+kashmir", text):
        return "Greater Kashmir"

    # Times of India — Delhi
    if re.search(r"\btoi\b|times\s+of\s+india", text):
        if re.search(r"\bdelhi\b", text):
            return "Times of India — Delhi"

    # Hindustan Times — main Delhi edition
    if re.search(r"\bht\b|hindustan\s+times", text):
        if re.search(r"\bdelhi\b", text):
            if not re.search(
                r"(north|south|east|west)\s+delhi|delhi\s+city",
                text
            ):
                return "Hindustan Times — Delhi"

    # Economic Times — Delhi
    if re.search(r"\bet\b|economic\s+times", text):
        if re.search(r"\bdelhi\b", text):
            return "Economic Times — Delhi"

    return None


async def main():
    print("Checking newspaper channel...")

    # Look at recent messages. This is intentionally bounded so
    # every GitHub Actions run remains lightweight.
    messages = []

    async for message in client.iter_messages(
        SOURCE_CHANNEL,
        limit=100
    ):
        if not message.file:
            continue

        filename = message.file.name or ""
        caption = message.text or ""

        paper = identify_paper(filename, caption)

        if paper:
            messages.append((message, paper))

    # Check recent destination messages to avoid duplicates.
    forwarded_ids = set()

    async for destination_message in client.iter_messages(
        DESTINATION_CHANNEL,
        limit=200
    ):
        forwarded = destination_message.fwd_from

        if not forwarded:
            continue

        source_message_id = getattr(
            forwarded,
            "channel_post",
            None
        )

        if source_message_id:
            forwarded_ids.add(source_message_id)

    messages.reverse()

    forwarded_count = 0

    for message, paper in messages:

        if message.id in forwarded_ids:
            continue

        filename = message.file.name or "(unnamed file)"

        print("--------------------------------------")
        print(f"Paper: {paper}")
        print(f"Message ID: {message.id}")
        print(f"File: {filename}")

        try:
            await client.forward_messages(
                DESTINATION_CHANNEL,
                message.id,
                from_peer=SOURCE_CHANNEL
            )

            print("✓ Forwarded")
            forwarded_count += 1

        except Exception as error:
            print("✗ Forwarding failed")
            print(f"Error: {error}")

    print("--------------------------------------")
    print(f"Forwarded this run: {forwarded_count}")
    print("Finished.")


with client:
    client.loop.run_until_complete(main())