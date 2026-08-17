import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("newspaper_session", api_id, api_hash)

SOURCE_CHANNEL = -1003645659794


def identify_paper(filename, caption):
    text = f"{filename} {caption}".lower()

    # Times of India — Delhi
    if re.search(r"\btoi\b|times\s+of\s+india", text):
        if re.search(r"\bdelhi\b", text):
            return "Times of India — Delhi"

    # Greater Kashmir
    if re.search(r"greater\s+kashmir", text):
        return "Greater Kashmir"

    # Hindustan Times — main Delhi edition only
    if re.search(r"\bht\b|hindustan\s+times", text):
        if re.search(r"\bdelhi\b", text):
            # Exclude city-specific Delhi editions
            if not re.search(
                r"(north|south|west|east)\s+delhi|delhi\s+city",
                text
            ):
                return "Hindustan Times — Delhi"

    # Economic Times — Delhi
    if re.search(r"\bet\b|economic\s+times", text):
        if re.search(r"\bdelhi\b", text):
            return "Economic Times — Delhi"

    return None


async def main():
    print("\nTarget editions found:\n")

    found = set()

    async for message in client.iter_messages(
        SOURCE_CHANNEL,
        limit=200
    ):
        if not message.file:
            continue

        filename = message.file.name or ""
        caption = message.text or ""

        paper = identify_paper(filename, caption)

        if paper:
            found.add(paper)

            print(f"[{message.id}] {paper}")
            print(f"    FILE: {filename}")
            print()

    print("========== SUMMARY ==========")

    for paper in sorted(found):
        print(f"✓ {paper}")


with client:
    client.loop.run_until_complete(main())