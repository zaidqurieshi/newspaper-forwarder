import os
import re
import json
import tempfile
import shutil

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from telethon import TelegramClient, types
from telethon.sessions import StringSession
from pypdf import PdfReader, PdfWriter


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
session_string = os.getenv("TELEGRAM_SESSION_STRING")

if not session_string:
    raise RuntimeError(
        "TELEGRAM_SESSION_STRING is not configured."
    )


# ============================================================
# TELEGRAM CLIENT
# ============================================================

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)


# ============================================================
# TELEGRAM CHANNELS
# ============================================================

# Indian newspaper source
INDIAN_CHANNEL = -1003645659794

# International newspaper source
INTERNATIONAL_CHANNEL = -1001580607147

# Destination ePapers channel
DESTINATION_CHANNEL = -1004486510815


# ============================================================
# ONLY PROCESS RECENT MESSAGES
# ============================================================

MAX_MESSAGE_AGE = timedelta(hours=48)


# ============================================================
# DUPLICATE DATABASE
# ============================================================

FORWARDED_FILE = "forwarded_messages.json"


def load_forwarded_messages():

    if not os.path.exists(FORWARDED_FILE):
        return {
            "indian": [],
            "international": []
        }

    try:

        with open(
            FORWARDED_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, dict):
            return {
                "indian": [],
                "international": []
            }

        data.setdefault("indian", [])
        data.setdefault("international", [])

        return data

    except Exception:

        return {
            "indian": [],
            "international": []
        }


def save_forwarded_messages(data):

    temporary_file = FORWARDED_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2
        )

    os.replace(
        temporary_file,
        FORWARDED_FILE
    )


# ============================================================
# RECENT MESSAGE CHECK
# ============================================================

def is_recent_message(message):

    if message.date is None:
        return False

    now = datetime.now(timezone.utc)

    message_date = message.date

    if message_date.tzinfo is None:
        message_date = message_date.replace(
            tzinfo=timezone.utc
        )

    age = now - message_date

    return age <= MAX_MESSAGE_AGE


# ============================================================
# DATE FOR TELEGRAM FILENAME
# ============================================================

def get_publication_date(message):

    if message.date is None:
        return datetime.now(
            timezone.utc
        )

    date = message.date

    if date.tzinfo is None:
        date = date.replace(
            tzinfo=timezone.utc
        )

    return date


def make_filename(
    paper,
    message
):

    date_string = get_publication_date(
        message
    ).strftime(
        "%d-%m-%Y"
    )

    return (
        f"{paper} - {date_string}.pdf"
    )


# ============================================================
# INDIAN NEWSPAPER MATCHING
# ============================================================

def identify_indian_paper(
    filename,
    caption
):

    filename_lower = (
        filename or ""
    ).lower()

    caption_lower = (
        caption or ""
    ).lower()

    text = (
        f"{filename_lower} {caption_lower}"
    )


    # ========================================================
    # GREATER KASHMIR
    # ========================================================

    if re.search(
        r"greater[\s_-]+kashmir",
        text
    ):

        return "Greater Kashmir"


    # ========================================================
    # TIMES OF INDIA — DELHI
    # ========================================================

    if re.search(
        r"\btoi\b"
        r"|times[\s_-]+of[\s_-]+india"
        r"|the[\s_-]+times[\s_-]+of[\s_-]+india",
        text
    ):

        if re.search(
            r"delhi[\s_-]+times"
            r"|delhi",
            text
        ):

            excluded = [
                "kochi",
                "hyderabad",
                "goa",
                "chennai",
                "bombay",
                "mumbai",
                "bangalore",
                "bengaluru",
                "kolkata",
                "pune",
                "ahmedabad",
            ]

            if not any(
                edition in text
                for edition in excluded
            ):

                return "Times of India"


    # ========================================================
    # HINDUSTAN TIMES — DELHI
    # ========================================================

    if re.search(
        r"\bht\b"
        r"|hindustan[\s_-]+times"
        r"|the[\s_-]+hindustan[\s_-]+times",
        text
    ):

        if re.search(
            r"ht[\s●_-]+delhi[\s●_-]"
            r"|ht[\s_-]+delhi\b"
            r"|hindustan[\s_-]+times.*\bdelhi\b",
            text
        ):

            excluded = [
                "delhi city",
                "west delhi",
                "south delhi",
                "east delhi",
                "north delhi",
                "noida",
                "gurgaon",
                "gurugram",
                "mumbai",
                "thane",
                "navi mumbai",
                "bengaluru",
                "bangalore",
            ]

            if not any(
                edition in text
                for edition in excluded
            ):

                return "Hindustan Times"


    # ========================================================
    # ECONOMIC TIMES — DELHI
    # ========================================================

    if re.search(
        r"\beconomic[\s_-]+times\b"
        r"|\bet\b",
        text
    ):

        if re.search(
            r"\bdelhi\b",
            text
        ):

            excluded = [
                "mumbai",
                "bangalore",
                "bengaluru",
                "hyderabad",
                "chennai",
                "kolkata",
            ]

            if not any(
                edition in text
                for edition in excluded
            ):

                return "Economic Times"


    return None


# ============================================================
# INTERNATIONAL NEWSPAPER MATCHING
# ============================================================

def identify_international_paper(
    filename,
    caption
):

    text = (
        f"{filename} {caption}"
    ).lower()


    # ========================================================
    # THE GUARDIAN
    # ========================================================

    if re.search(
        r"the[-\s]+guardian",
        text
    ):

        if re.search(
            r"\buk\b|uk[_\s-]",
            text
        ):

            return "The Guardian"


    # ========================================================
    # NEW YORK TIMES
    # ========================================================

    if re.search(
        r"\bnyt\b"
        r"|new[-\s]+york[-\s]+times",
        text
    ):

        return "The New York Times"


    # ========================================================
    # WASHINGTON POST
    # ========================================================

    if re.search(
        r"washington[-\s]+post",
        text
    ):

        return "The Washington Post"


    # ========================================================
    # THE SUN UK
    # ========================================================

    if re.search(
        r"the[-\s]+sun",
        text
    ):

        if re.search(
            r"\buk\b",
            text
        ):

            return "The Sun UK"


    # ========================================================
    # FINANCIAL TIMES — UK
    # ========================================================

    if re.search(
        r"\bft[\s_-]+uk\b"
        r"|financial[-\s]+times[-\s]+uk",
        text
    ):

        return "Financial Times UK"


    # ========================================================
    # FINANCIAL TIMES — US
    # ========================================================

    if re.search(
        r"\bft[\s_-]+us\b"
        r"|financial[-\s]+times[-\s]+us",
        text
    ):

        return "Financial Times US"


    # ========================================================
    # FINANCIAL TIMES — EU
    # ========================================================

    if re.search(
        r"\bft[\s_-]+eu\b"
        r"|financial[-\s]+times[-\s]+eu"
        r"|financial[-\s]+times[-\s]+europe",
        text
    ):

        return "Financial Times EU"


    # ========================================================
    # WALL STREET JOURNAL
    # ========================================================

    if re.search(
        r"wall[-\s]+street[-\s]+journal"
        r"|wall[-\s]+street[-\s]+jornal",
        text
    ):

        return "The Wall Street Journal"


    # ========================================================
    # DAILY MIRROR
    # ========================================================

    if re.search(
        r"daily[-\s]+mirror",
        text
    ):

        return "Daily Mirror"


    # ========================================================
    # DAILY TELEGRAPH
    # ========================================================

    if re.search(
        r"daily[-\s]+telegraph",
        text
    ):

        return "Daily Telegraph"


    return None


# ============================================================
# NEWS TG8 PROMOTIONAL PAGE DETECTION
# ============================================================

def is_promotional_page(text):

    if not text:
        return False

    text = text.lower()

    indicators = [

        "newstg8",

        "newstg",

        "8890005082",

        "save my contact number",

        "to get all the popular newspapers",

        "popular newspapers",

        "english newspapers",

        "hindi newspapers",

        "type in search box of telegram",

        "receive daily editions",

        "daily editions of all popular epapers",

        "t.me/newstg8",
    ]

    matches = 0

    for indicator in indicators:

        if indicator in text:
            matches += 1

    if "newstg8" in text:
        return True

    if "t.me/newstg8" in text:
        return True

    return matches >= 2


# ============================================================
# CLEAN INDIAN PDF
# ============================================================

def clean_indian_pdf(
    input_path,
    output_path
):

    reader = PdfReader(
        input_path
    )

    writer = PdfWriter()

    removed_pages = 0


    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        try:

            text = (
                page.extract_text()
                or ""
            )

        except Exception:

            text = ""


        if is_promotional_page(text):

            print(
                f"Promotional page detected "
                f"(page {page_number}) - removed",
                flush=True
            )

            removed_pages += 1

            continue


        writer.add_page(page)


    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if len(writer.pages) == 0:

        print(
            "WARNING: Cleaning would produce "
            "an empty PDF. Original retained.",
            flush=True
        )

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        removed_pages = 0


    with open(
        output_path,
        "wb"
    ) as output_file:

        writer.write(
            output_file
        )


    return removed_pages


# ============================================================
# PREPARE INDIAN PDF
# ============================================================

async def prepare_indian_pdf(
    message,
    paper
):

    temporary_directory = tempfile.mkdtemp(
        prefix="newspaper_"
    )


    original_filename = (
        message.file.name
        or f"newspaper_{message.id}.pdf"
    )


    original_path = os.path.join(
        temporary_directory,
        original_filename
    )


    print(
        "Downloading Indian PDF for cleaning...",
        flush=True
    )


    await client.download_media(
        message,
        file=original_path
    )


    print(
        "Download complete.",
        flush=True
    )


    print(
        "Checking for NewsTG8 promotional page...",
        flush=True
    )


    final_filename = make_filename(
        paper,
        message
    )


    cleaned_path = os.path.join(
        temporary_directory,
        final_filename
    )


    removed_pages = clean_indian_pdf(
        original_path,
        cleaned_path
    )


    if removed_pages == 0:

        print(
            "No promotional page detected.",
            flush=True
        )

        if os.path.abspath(
            original_path
        ) != os.path.abspath(
            cleaned_path
        ):

            shutil.copy2(
                original_path,
                cleaned_path
            )

    else:

        print(
            f"Removed {removed_pages} "
            f"promotional page(s).",
            flush=True
        )


    print(
        f"Final filename: {final_filename}",
        flush=True
    )


    return (
        cleaned_path,
        temporary_directory
    )


# ============================================================
# SEND INTERNATIONAL MEDIA WITHOUT DOWNLOADING
#
# Telegram media is reused directly.
# Only the filename attribute is changed.
# ============================================================

async def send_existing_media(
    message,
    paper
):

    final_filename = make_filename(
        paper,
        message
    )


    print(
        "Sending existing Telegram media directly...",
        flush=True
    )


    print(
        f"Final filename: {final_filename}",
        flush=True
    )


    # Telegram document filename attribute.
    #
    # This changes the filename shown in the destination
    # channel while reusing the existing Telegram media.

    filename_attribute = (
        types.DocumentAttributeFilename(
            file_name=final_filename
        )
    )


    await client.send_file(
        DESTINATION_CHANNEL,
        message.media,
        caption=None,
        force_document=True,
        attributes=[
            filename_attribute
        ]
    )


    print(
        "✓ Sent without downloading to GitHub",
        flush=True
    )


# ============================================================
# CLEAN TEMP DIRECTORY
# ============================================================

def cleanup_directory(
    directory
):

    if not directory:
        return

    try:

        shutil.rmtree(
            directory,
            ignore_errors=True
        )

    except Exception:

        pass


# ============================================================
# MAIN
# ============================================================

async def main():

    print(
        "======================================",
        flush=True
    )

    print(
        " Newspaper Forwarder",
        flush=True
    )

    print(
        "======================================",
        flush=True
    )

    print(
        flush=True
    )


    # ========================================================
    # LOAD DUPLICATE DATABASE
    # ========================================================

    forwarded = load_forwarded_messages()


    forwarded_indian = set(
        int(x)
        for x in forwarded.get(
            "indian",
            []
        )
    )


    forwarded_international = set(
        int(x)
        for x in forwarded.get(
            "international",
            []
        )
    )


    matches = []


    # ========================================================
    # INDIAN CHANNEL
    # ========================================================

    print(
        "Checking Indian newspapers...",
        flush=True
    )


    async for message in client.iter_messages(
        INDIAN_CHANNEL,
        limit=100
    ):

        if not message.file:
            continue


        if not is_recent_message(
            message
        ):
            continue


        if message.id in forwarded_indian:
            continue


        filename = (
            message.file.name
            or ""
        )


        caption = (
            message.text
            or ""
        )


        paper = identify_indian_paper(
            filename,
            caption
        )


        if paper:

            matches.append(
                (
                    message,
                    paper,
                    "indian"
                )
            )


    # ========================================================
    # INTERNATIONAL CHANNEL
    # ========================================================

    print(
        "Checking international newspapers...",
        flush=True
    )


    async for message in client.iter_messages(
        INTERNATIONAL_CHANNEL,
        limit=100
    ):

        if not message.file:
            continue


        if not is_recent_message(
            message
        ):
            continue


        if message.id in forwarded_international:
            continue


        filename = (
            message.file.name
            or ""
        )


        caption = (
            message.text
            or ""
        )


        paper = identify_international_paper(
            filename,
            caption
        )


        if paper:

            matches.append(
                (
                    message,
                    paper,
                    "international"
                )
            )


    # ========================================================
    # OLDEST FIRST
    # ========================================================

    matches.sort(
        key=lambda item: item[0].id
    )


    print(
        flush=True
    )


    print(
        f"Found {len(matches)} new "
        f"matching newspaper(s).",
        flush=True
    )


    print(
        flush=True
    )


    sent_count = 0
    failed_count = 0


    # ========================================================
    # PROCESS
    # ========================================================

    for (
        message,
        paper,
        source_type
    ) in matches:


        filename = (
            message.file.name
            or ""
        )


        print(
            "--------------------------------------",
            flush=True
        )


        print(
            f"Paper: {paper}",
            flush=True
        )


        print(
            f"Message ID: {message.id}",
            flush=True
        )


        print(
            f"File: {filename}",
            flush=True
        )


        temporary_directory = None


        try:


            # =================================================
            # INDIAN
            #
            # Download → clean → rename → upload
            # =================================================

            if source_type == "indian":


                (
                    upload_path,
                    temporary_directory
                ) = await prepare_indian_pdf(
                    message,
                    paper
                )


                print(
                    "Uploading cleaned PDF...",
                    flush=True
                )


                await client.send_file(
                    DESTINATION_CHANNEL,
                    upload_path,
                    caption=None,
                    force_document=True
                )


                print(
                    f"✓ Sent as: "
                    f"{os.path.basename(upload_path)}",
                    flush=True
                )


                forwarded_indian.add(
                    message.id
                )


                forwarded["indian"] = sorted(
                    forwarded_indian
                )


            # =================================================
            # INTERNATIONAL
            #
            # NO DOWNLOAD.
            # NO UPLOAD FROM GITHUB.
            #
            # Reuse Telegram media and rename it.
            # =================================================

            else:


                await send_existing_media(
                    message,
                    paper
                )


                forwarded_international.add(
                    message.id
                )


                forwarded["international"] = sorted(
                    forwarded_international
                )


            # =================================================
            # SAVE ONLY AFTER SUCCESS
            # =================================================

            save_forwarded_messages(
                forwarded
            )


            sent_count += 1


        except Exception as error:


            print(
                "✗ Sending failed",
                flush=True
            )


            print(
                f"Error: {error}",
                flush=True
            )


            failed_count += 1


        finally:


            cleanup_directory(
                temporary_directory
            )


    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        flush=True
    )


    print(
        "======================================",
        flush=True
    )


    print(
        f"Sent this run: {sent_count}",
        flush=True
    )


    print(
        f"Failed: {failed_count}",
        flush=True
    )


    print(
        "Finished.",
        flush=True
    )


    print(
        "======================================",
        flush=True
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    with client:

        client.loop.run_until_complete(
            main()
        )