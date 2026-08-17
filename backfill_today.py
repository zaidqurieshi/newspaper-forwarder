import json
import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("newspaper_session", api_id, api_hash)

SOURCE_CHANNEL = -1003645659794
DESTINATION_CHANNEL = -1004486510815

STATE_FILE = "forwarded_messages.json"

# Today's target messages start around here.
START_MESSAGE_ID = 33620

# Already forwarded manually / by our test.
ALREADY_FORWARDED = {
    33644,  # Greater Kashmir
    33649,  # Hindustan Times — Delhi
}


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


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last_processed_message_id": 0,
            "forwarded_message_ids": []
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {
            "last_processed_message_id": 0,
            "forwarded_message_ids": []
        }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


async def main():
    state = load_state()

    forwarded_ids = set(
        state.get("forwarded_message_ids", [])
    )

    # Add the two files we already know were forwarded.
    forwarded_ids.update(ALREADY_FORWARDED)

    print("\nChecking today's target newspapers...\n")

    matches = []

    async for message in client.iter_messages(
        SOURCE_CHANNEL,
        min_id=START_MESSAGE_ID,
        reverse=True
    ):
        if not message.file:
            continue

        if message.id in forwarded_ids:
            continue

        filename = message.file.name or ""
        caption = message.text or ""

        paper = identify_paper(filename, caption)

        if paper:
            matches.append((message, paper))

    if not matches:
        print("No missing newspapers found.")
        return

    for message, paper in matches:
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

            forwarded_ids.add(message.id)

            print("✓ Forwarded\n")

        except Exception as error:
            print(f"✗ Failed: {error}\n")

    state["forwarded_message_ids"] = list(forwarded_ids)

    latest = await client.get_messages(
        SOURCE_CHANNEL,
        limit=1
    )

    if latest:
        state["last_processed_message_id"] = latest[0].id

    save_state(state)

    print("======================================")
    print("Catch-up complete.")
    print("======================================")


with client:
    client.loop.run_until_complete(main())