import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

SOURCE_CHANNEL = -1003645659794

client = TelegramClient(
    "fresh_newspaper_session",
    api_id,
    api_hash
)


def identify_paper(filename, caption):
    text = f"{filename} {caption}".lower()

    if "greater kashmir" in text:
        return "Greater Kashmir"

    if ("toi" in text or "times of india" in text) and "delhi" in text:
        return "Times of India — Delhi"

    if ("ht" in text or "hindustan times" in text) and "delhi" in text:
        if not any(x in text for x in [
            "north delhi",
            "south delhi",
            "east delhi",
            "west delhi",
            "delhi city"
        ]):
            return "Hindustan Times — Delhi"

    if ("et" in text or "economic times" in text) and "delhi" in text:
        return "Economic Times — Delhi"

    return None


async def main():
    message = await client.get_messages(
        SOURCE_CHANNEL,
        ids=33649
    )

    if not message:
        print("Message 33649 not found.")
        return

    filename = message.file.name if message.file else ""
    caption = message.text or ""

    print("Message ID:", message.id)
    print("File:", filename)
    print("Caption:", caption)

    paper = identify_paper(filename, caption)

    print()
    print("MATCH RESULT:")
    print(paper if paper else "NO MATCH")


with client:
    client.loop.run_until_complete(main())