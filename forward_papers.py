import os
import re
import sys
import json
import tempfile
import shutil

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONSOLE ENCODING
#
# Telegram filenames can contain Unicode characters
# (e.g. \u25cf BLACK CIRCLE, \u2039 SINGLE LEFT-POINTING
# ANGLE QUOTATION MARK). On Windows the default stdout
# encoding is cp1252 which can't represent those, so
# we force UTF-8 before printing anything.
# ============================================================

try:

    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace"
    )

    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace"
    )

except Exception:

    pass


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

INDIAN_CHANNEL = -1003645659794

INTERNATIONAL_CHANNEL = -1001580607147

DESTINATION_CHANNEL = -1004486510815


# ============================================================
# TODAY-ONLY WINDOW
#
# Only messages posted TODAY (Asia/Kolkata) are eligible for
# forwarding. Anything posted yesterday or earlier is ignored
# so the destination channel never gets flooded with a
# backlog of old papers.
# ============================================================


# ============================================================
# FORWARDED DATABASE
# ============================================================

FORWARDED_FILE = "forwarded_messages.json"


# ============================================================
# TEST / FORCE MODE
#
# When FORCE=1 (environment variable) or "--force" is passed
# on the command line, every matched paper is forwarded again
# regardless of whether it was already sent today. The current
# forwarded-messages database is COPIED to a side file
# (FORWARDED_TEST_FILE) for the duration of the test so the
# real production state is never modified.
# ============================================================

FORWARDED_TEST_FILE = "forwarded_messages.test.json"


def _force_mode_enabled():

    if (
        "--force" in sys.argv
        or "-f" in sys.argv
    ):

        return True


    if (
        os.getenv(
            "FORCE",
            ""
        ).strip().lower()
        in (
            "1",
            "true",
            "yes",
            "on",
        )
    ):

        return True


    return False


def _enter_force_mode():

    global FORWARDED_FILE

    if os.path.exists(FORWARDED_FILE):

        try:

            with open(
                FORWARDED_FILE,
                "r",
                encoding="utf-8"
            ) as src:

                data = json.load(src)

        except Exception:

            data = {
                "indian": [],
                "international": [],
                "daily_sent": {},
            }

    else:

        data = {
            "indian": [],
            "international": [],
            "daily_sent": {},
        }


    with open(
        FORWARDED_TEST_FILE,
        "w",
        encoding="utf-8"
    ) as dst:

        json.dump(
            data,
            dst,
            indent=2
        )


    FORWARDED_FILE = FORWARDED_TEST_FILE


def load_forwarded_messages():

    if not os.path.exists(FORWARDED_FILE):

        return {
            "indian": [],
            "international": [],
            "daily_sent": {}
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
                "international": [],
                "daily_sent": {}
            }

        data.setdefault("indian", [])
        data.setdefault("international", [])
        data.setdefault("daily_sent", {})

        return data

    except Exception:

        return {
            "indian": [],
            "international": [],
            "daily_sent": {}
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
# DAILY DEDUPLICATION
#
# The source channel often posts the same newspaper more than
# once per day (different Telegram message IDs). To honour the
# "send each file only once per day" rule, we keep a
# "daily_sent" map of the form:
#
#     {
#         "Greater Kashmir":         ["2026-09-02"],
#         "Hindustan Times":         ["2026-09-02"],
#         "The New York Times":      ["2026-09-02"]
#     }
#
# A paper is skipped for the same calendar day (in IST) if a
# record already exists for that (paper, date) pair.
# ============================================================

def _today_key_ist(message=None):
    """
    Return today's date in IST as an ISO string
    (e.g. "2026-09-02"). If `message` is provided, the
    message's publication date is used instead, so the
    dedup window matches the publication date used in the
    filename.
    """

    if message is not None:

        publication_date = get_publication_date(
            message
        )

    else:

        publication_date = datetime.now(
            timezone.utc
        )


    try:

        from zoneinfo import ZoneInfo

        publication_date = publication_date.astimezone(
            ZoneInfo("Asia/Kolkata")
        )

    except Exception:

        pass


    return publication_date.strftime(
        "%Y-%m-%d"
    )


def already_sent_today(
    paper,
    daily_sent,
    message=None
):

    date_key = _today_key_ist(
        message
    )

    dates = daily_sent.get(
        paper,
        []
    )

    return date_key in dates


def mark_sent_today(
    paper,
    daily_sent,
    message=None
):

    date_key = _today_key_ist(
        message
    )

    dates = daily_sent.setdefault(
        paper,
        []
    )

    if date_key not in dates:

        dates.append(date_key)


# ============================================================
# TODAY-ONLY MESSAGE CHECK
# ============================================================

def is_recent_message(message):

    if message.date is None:
        return False

    message_date = message.date

    if message_date.tzinfo is None:

        message_date = message_date.replace(
            tzinfo=timezone.utc
        )

    try:

        from zoneinfo import ZoneInfo

        ist_timezone = ZoneInfo("Asia/Kolkata")

    except Exception:

        ist_timezone = timezone(
            timedelta(hours=5, minutes=30)
        )

    now_ist = datetime.now(ist_timezone)

    message_ist = message_date.astimezone(
        ist_timezone
    )

    return (
        message_ist.date() == now_ist.date()
    )


# ============================================================
# DATE / FILENAME
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


def _ordinal_day(day):
    """
    Return the day number with its English ordinal suffix.

    1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th, 11 -> 11th, 21 -> 21st, etc.
    """

    if 10 <= (day % 100) <= 20:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(
            day % 10,
            "th"
        )

    return f"{day}{suffix}"


def make_filename(
    paper,
    message
):

    publication_date = get_publication_date(
        message
    )

    # --------------------------------------------------------
    # Convert the message date to IST (Asia/Kolkata) so the
    # filename day matches the publication day in India,
    # not the UTC day.
    # --------------------------------------------------------

    try:

        from zoneinfo import ZoneInfo

        publication_date = publication_date.astimezone(
            ZoneInfo("Asia/Kolkata")
        )

    except Exception:

        pass


    day_with_suffix = _ordinal_day(
        publication_date.day
    )

    month_name = publication_date.strftime(
        "%B"
    )

    year = publication_date.year


    date_string = (
        f"{day_with_suffix} {month_name} {year}"
    )


    return (
        f"{paper} - {date_string}.pdf"
    )


# ============================================================
# INDIAN NEWSPAPER MATCHING
# ============================================================

# Allowed Indian edition keywords that should be forwarded.
# When multiple editions exist, Delhi is preferred.
DELHI_KEYWORDS = [
    "delhi",
    "new delhi",
    "ncr",
]

# Excluded edition keywords (non-Delhi editions) for HT.
HT_EXCLUDED_EDITIONS = [
    "mumbai",
    "thane",
    "navi mumbai",
    "bengaluru",
    "bangalore",
    "pune",
    "kolkata",
    "chennai",
    "lucknow",
    "varanasi",
    "patna",
    "ranchi",
    "rajasthan",
    "punjab",
    "haryana",
    "jalandhar",
    "amritsar",
    "ludhiana",
    "chandigarh",
    "jammu",
    "uttarakhand",
    "uttrakhand",
    "east up",
    "west up",
    "north india",
    "south india",
    "kerala",
    "kochi",
    "hyderabad",
    "goa",
    "ahmedabad",
    "surat",
    "indore",
    "bhopal",
    "nagpur",
    "jaipur",
    "guwahati",
    "patiala",
    "malwa",
    "mysuru",
    "mangaluru",
]

# Excluded edition keywords (non-Delhi editions) for TOI.
TOI_EXCLUDED_EDITIONS = [
    "mumbai",
    "bombay",
    "bengaluru",
    "bangalore",
    "pune",
    "kolkata",
    "chennai",
    "kochi",
    "hyderabad",
    "goa",
    "ahmedabad",
]

# Excluded edition keywords (non-Delhi editions) for ET.
ET_EXCLUDED_EDITIONS = [
    "mumbai",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "chennai",
    "kolkata",
]


def _has_delhi_keyword(text):
    """
    Returns True if the text contains a Delhi-region keyword.

    Recognised variants:
      - delhi
      - new delhi
      - ncr (national capital region)
    """

    for keyword in DELHI_KEYWORDS:

        if keyword in text:

            return True

    return False


def _is_excluded_edition(
    text,
    excluded_list
):
    """
    Returns True if any excluded edition keyword is present in text.
    """

    return any(
        edition in text
        for edition in excluded_list
    )


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


    # --------------------------------------------------------
    # GREATER KASHMIR
    # --------------------------------------------------------

    if re.search(
        r"greater[\s_-]+kashmir",
        text
    ):

        return "Greater Kashmir"


    # --------------------------------------------------------
    # HINDUSTAN TIMES
    #
    # Only the MAIN Delhi edition is forwarded.
    # We treat "HT ● Delhi" (or "Hindustan Times - Delhi",
    # "HT Delhi", etc.) as the main paper. Every other
    # Delhi-area variant (North/South/East/West Delhi,
    # Delhi City, School Delhi, Noida, Gurgaon, etc.) and
    # every non-Delhi city is excluded, as is anything that
    # looks like an editorial / supplement / magazine file.
    # --------------------------------------------------------

    if re.search(
        r"\bht\b"
        r"|hindustan[\s_-]+times"
        r"|the[\s_-]+hindustan[\s_-]+times",
        text
    ):

        # First, drop any obvious editorial / supplement /
        # special-section file (e.g. "HT School", "HT Op-Ed",
        # "HT Editorial", "HT Magazine", "HT Lite", "HT
        # Buzz", "HT HT City", "HT Live", etc.).
        if re.search(
            r"\beditorial\b"
            r"|\bop[\s_-]+ed\b"
            r"|\bsupplement\b"
            r"|\bmagazine\b"
            r"|\bschool\b"
            r"|\blite\b"
            r"|\bbuzz\b"
            r"|\bcity\b"
            r"|\blive\b",
            text
        ):

            return None


        # Must mention Delhi to be considered.
        if not _has_delhi_keyword(text):

            return None


        # Drop any non-Delhi city (Mumbai, Pune, Lucknow, ...).
        if _is_excluded_edition(
            text,
            HT_EXCLUDED_EDITIONS
        ):

            return None


        # Drop Delhi-area sub-editions (North/South/East/West
        # Delhi, Delhi City, etc.) so that only the main
        # "HT ● Delhi" file is forwarded.
        if re.search(
            r"(north|south|east|west|ncr|school)"
            r"[\s_-]+delhi"
            r"|delhi[\s_-]+city"
            r"|\bdelhi[\s_-]+ncr\b"
            r"|\bgreater[\s_-]+noida\b"
            r"|\bnoida\b"
            r"|\bgurgaon\b"
            r"|\bgurugram\b"
            r"|\bfaridabad\b"
            r"|\bghaziabad\b",
            text
        ):

            return None


        return "Hindustan Times"


    # --------------------------------------------------------
    # TIMES OF INDIA
    #
    # Match TOI (or "Times of India") only when the file
    # refers to a Delhi-region edition.
    # --------------------------------------------------------

    if re.search(
        r"\btoi\b"
        r"|times[\s_-]+of[\s_-]+india"
        r"|the[\s_-]+times[\s_-]+of[\s_-]+india",
        text
    ):

        if _has_delhi_keyword(text):

            if not _is_excluded_edition(
                text,
                TOI_EXCLUDED_EDITIONS
            ):

                return "Times of India"


    # --------------------------------------------------------
    # ECONOMIC TIMES
    #
    # Match ET (or "Economic Times") only when the file
    # refers to a Delhi-region edition.
    # --------------------------------------------------------

    if re.search(
        r"\beconomic[\s_-]+times\b"
        r"|\bet\b",
        text
    ):

        if _has_delhi_keyword(text):

            if not _is_excluded_edition(
                text,
                ET_EXCLUDED_EDITIONS
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
        f"{filename or ''} {caption or ''}"
    ).lower()


    # --------------------------------------------------------
    # EXCLUDE TIMES SUPPLEMENTS
    # --------------------------------------------------------

    supplement_patterns = [
        r"the[\s_-]+times[\s_-]+.*magazine",
        r"the[\s_-]+times[\s_-]+.*culture",
        r"the[\s_-]+times[\s_-]+.*style",
        r"\btimes[\s_-]+magazine\b",
        r"\btimes[\s_-]+culture\b",
        r"\btimes[\s_-]+style\b",
    ]

    for pattern in supplement_patterns:

        if re.search(
            pattern,
            text
        ):

            return None


    # --------------------------------------------------------
    # WASHINGTON POST
    # --------------------------------------------------------

    if re.search(
        r"washington[\s_-]+post",
        text
    ):

        return "The Washington Post"


    # --------------------------------------------------------
    # GUARDIAN
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+guardian"
        r"|\bguardian\b",
        text
    ):

        return "The Guardian"


    # --------------------------------------------------------
    # FINANCIAL TIMES UK
    # --------------------------------------------------------

    if re.search(
        r"\bft[\s_-]+uk\b"
        r"|financial[\s_-]+times[\s_-]+uk",
        text
    ):

        return "Financial Times UK"


    # --------------------------------------------------------
    # FINANCIAL TIMES EU
    # --------------------------------------------------------

    if re.search(
        r"\bft[\s_-]+eu\b"
        r"|financial[\s_-]+times[\s_-]+eu"
        r"|financial[\s_-]+times[\s_-]+europe",
        text
    ):

        return "Financial Times EU"


    # --------------------------------------------------------
    # FINANCIAL TIMES US
    # --------------------------------------------------------

    if re.search(
        r"\bft[\s_-]+us\b"
        r"|financial[\s_-]+times[\s_-]+us",
        text
    ):

        return "Financial Times US"


    # --------------------------------------------------------
    # NEW YORK TIMES
    # --------------------------------------------------------

    if re.search(
        r"\bnyt\b"
        r"|new[\s_-]+york[\s_-]+times",
        text
    ):

        if "international" in text:

            return "The New York Times International"

        return "The New York Times"


    # --------------------------------------------------------
    # WALL STREET JOURNAL
    # --------------------------------------------------------

    if re.search(
        r"wall[\s_-]+street[\s_-]+journal"
        r"|wall[\s_-]+street[\s_-]+jornal",
        text
    ):

        return "The Wall Street Journal"


    # --------------------------------------------------------
    # DAILY TELEGRAPH
    # --------------------------------------------------------

    if re.search(
        r"daily[\s_-]+telegraph",
        text
    ):

        return "Daily Telegraph"


    # --------------------------------------------------------
    # DAILY MAIL
    # --------------------------------------------------------

    if re.search(
        r"daily[\s_-]+mail",
        text
    ):

        return "Daily Mail"


    # --------------------------------------------------------
    # OBSERVER
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+observer"
        r"|\bobserver\b",
        text
    ):

        return "The Observer"


    # --------------------------------------------------------
    # INDEPENDENT
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+independent"
        r"|\bindependent\b",
        text
    ):

        return "The Independent"


    # --------------------------------------------------------
    # TIMES UK
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+times[\s_-]+uk",
        text
    ):

        return "The Times UK"


    # --------------------------------------------------------
    # SUN UK
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+sun[\s_-]+uk",
        text
    ):

        return "The Sun UK"


    # --------------------------------------------------------
    # DAILY EXPRESS
    # --------------------------------------------------------

    if re.search(
        r"daily[\s_-]+express",
        text
    ):

        return "Daily Express"


    # --------------------------------------------------------
    # DAILY MIRROR
    # --------------------------------------------------------

    if re.search(
        r"daily[\s_-]+mirror",
        text
    ):

        return "Daily Mirror"


    # --------------------------------------------------------
    # I NEWSPAPER (also "The i Paper")
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+i[\s_-]+newspaper"
        r"|\bi[\s_-]+newspaper\b"
        r"|the[\s_-]+i[\s_-]+paper"
        r"|\bi[\s_-]+paper\b",
        text
    ):

        return "The i Newspaper"


    # --------------------------------------------------------
    # DAILY NEWS (UK)
    # --------------------------------------------------------

    if re.search(
        r"\bdaily[\s_-]+news\b",
        text
    ):

        return "Daily News"


    # --------------------------------------------------------
    # DAILY STAR (UK)
    # --------------------------------------------------------

    if re.search(
        r"\bdaily[\s_-]+star\b",
        text
    ):

        return "Daily Star"


    # --------------------------------------------------------
    # DAILY RECORD (Scotland)
    # --------------------------------------------------------

    if re.search(
        r"\bdaily[\s_-]+record\b",
        text
    ):

        return "Daily Record"


    # --------------------------------------------------------
    # THE JOURNAL (Newcastle)
    # --------------------------------------------------------

    if re.search(
        r"the[\s_-]+journal[\s_-]+uk"
        r"|\bjournal[\s_-]+uk\b"
        r"|the[\s_-]+journal(?=[\s_-]+\d|\.pdf|$)"
        r"|\bnewcastle[\s_-]+journal\b",
        text
    ):

        return "The Journal"


    # --------------------------------------------------------
    # CALGARY HERALD
    # --------------------------------------------------------

    if re.search(
        r"calgary[\s_-]+herald",
        text
    ):

        return "Calgary Herald"


    # --------------------------------------------------------
    # NATIONAL POST
    # --------------------------------------------------------

    if re.search(
        r"national[\s_-]+post",
        text
    ):

        return "National Post"


    # --------------------------------------------------------
    # GLOBE AND MAIL
    # --------------------------------------------------------

    if re.search(
        r"globe[\s_-]+and[\s_-]+mail",
        text
    ):

        return "The Globe and Mail"


    # --------------------------------------------------------
    # CHICAGO TRIBUNE
    # --------------------------------------------------------

    if re.search(
        r"chicago[\s_-]+tribune",
        text
    ):

        return "Chicago Tribune"


    # --------------------------------------------------------
    # USA TODAY
    # --------------------------------------------------------

    if re.search(
        r"usa[\s_-]+today",
        text
    ):

        return "USA Today"


    # --------------------------------------------------------
    # BOSTON GLOBE
    # --------------------------------------------------------

    if re.search(
        r"boston[\s_-]+globe",
        text
    ):

        return "The Boston Globe"


    # --------------------------------------------------------
    # NEW YORK POST
    # --------------------------------------------------------

    if re.search(
        r"new[\s_-]+york[\s_-]+post",
        text
    ):

        return "New York Post"


    # --------------------------------------------------------
    # LOS ANGELES TIMES
    # --------------------------------------------------------

    if re.search(
        r"la[\s_-]+times"
        r"|los[\s_-]+angeles[\s_-]+times",
        text
    ):

        return "Los Angeles Times"


    return None


# ============================================================
# NEWS TG8 PROMOTIONAL PAGE
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
# INDIAN PAPERS THAT ARE SCANNED FOR PROMOTIONAL PAGES
#
# Every Indian paper is downloaded, scanned, and has detected
# promotional pages stripped before it is re-uploaded.
# ============================================================

def _should_clean_paper(paper):

    return True


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


    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

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
#
# Every Indian newspaper is downloaded and re-uploaded
# so the destination channel always shows the new ordinal
# filename (e.g. "Hindustan Times - 31st August 2026.pdf")
# rather than the original Telegram filename.
#
# The downloaded file is scanned for promotional pages and a
# cleaned PDF is produced for every Indian paper.
# ============================================================

async def prepare_indian_pdf(
    message,
    paper
):

    final_filename = make_filename(
        paper,
        message
    )


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
        "Downloading Indian PDF for re-upload...",
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


    # --------------------------------------------------------
    # Path that the re-upload will read from. We always
    # write the final_filename into the temporary directory
    # so the upload carries the right name attribute.
    # --------------------------------------------------------

    upload_path = os.path.join(
        temporary_directory,
        final_filename
    )


    if _should_clean_paper(paper):

        print(
            "Checking for NewsTG8 promotional page...",
            flush=True
        )


        removed_pages = clean_indian_pdf(
            original_path,
            upload_path
        )


        if removed_pages == 0:

            print(
                "No promotional page detected.",
                flush=True
            )

            if os.path.abspath(
                original_path
            ) != os.path.abspath(
                upload_path
            ):

                shutil.copy2(
                    original_path,
                    upload_path
                )

        else:

            print(
                f"Removed {removed_pages} "
                f"promotional page(s).",
                flush=True
            )

    else:

        # No cleaning required; just rename the file on
        # disk so the upload carries the new filename.
        shutil.copy2(
            original_path,
            upload_path
        )


    print(
        f"Final filename: {final_filename}",
        flush=True
    )


    return (
        upload_path,
        temporary_directory,
        final_filename
    )


# ============================================================
# INTERNATIONAL HANDLING
#
# International papers are not downloaded or renamed. They
# reuse the existing Telegram media reference and preserve
# the original Telegram filename.
# ============================================================


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
    # TEST / FORCE MODE
    #
    # If the user passed --force (or set FORCE=1), the real
    # production database is copied to a side file and
    # every dedup check is disabled so every matched
    # newspaper is forwarded exactly once during this run.
    # ========================================================

    force_mode = _force_mode_enabled()


    if force_mode:

        print(
            "⚠ FORCE MODE ENABLED",
            flush=True
        )

        print(
            "  - The real forwarded_messages.json is "
            "NOT being modified.",
            flush=True
        )

        print(
            f"  - All progress is written to "
            f"{FORWARDED_TEST_FILE} instead.",
            flush=True
        )

        print(
            "  - All dedup checks are bypassed "
            "(every match will be forwarded).",
            flush=True
        )

        print(
            flush=True
        )


    # ========================================================
    # LOAD DATABASE
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


    daily_sent = forwarded.get(
        "daily_sent",
        {}
    )


    matches = []


    # ========================================================
    # INDIAN CHANNEL
    # ========================================================

    print(
        "Checking Indian newspapers...",
        flush=True
    )


    indian_scanned = 0

    indian_skipped_old = 0

    indian_skipped_duplicate = 0

    indian_skipped_unmatched = 0

    indian_skipped_daily = 0


    async for message in client.iter_messages(
        INDIAN_CHANNEL,
        limit=500
    ):

        if not message.file:

            continue


        indian_scanned += 1


        if not is_recent_message(
            message
        ):

            indian_skipped_old += 1

            continue


        if (
            not force_mode
            and message.id in forwarded_indian
        ):

            indian_skipped_duplicate += 1

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

            # --------------------------------------------
            # DAILY DEDUP
            #
            # If this paper was already forwarded on the
            # same calendar day (in IST), skip it so we
            # only send the file once per day.
            # (Bypassed in FORCE mode.)
            # --------------------------------------------

            if (
                not force_mode
                and already_sent_today(
                    paper,
                    daily_sent,
                    message
                )
            ):

                indian_skipped_daily += 1

                continue


            matches.append(
                (
                    message,
                    paper,
                    "indian"
                )
            )

        else:

            indian_skipped_unmatched += 1


    print(
        f"  Indian scanned: {indian_scanned}, "
        f"skipped (old): {indian_skipped_old}, "
        f"skipped (duplicate): {indian_skipped_duplicate}, "
        f"skipped (unmatched): {indian_skipped_unmatched}, "
        f"skipped (already-sent-today): {indian_skipped_daily}",
        flush=True
    )


    # ========================================================
    # INTERNATIONAL CHANNEL
    # ========================================================

    print(
        "Checking international newspapers...",
        flush=True
    )


    international_scanned = 0

    international_skipped_old = 0

    international_skipped_duplicate = 0

    international_skipped_unmatched = 0

    international_skipped_daily = 0


    async for message in client.iter_messages(
        INTERNATIONAL_CHANNEL,
        limit=500
    ):

        if not message.file:

            continue


        international_scanned += 1


        if not is_recent_message(
            message
        ):

            international_skipped_old += 1

            continue


        if (
            not force_mode
            and message.id in forwarded_international
        ):

            international_skipped_duplicate += 1

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

            # --------------------------------------------
            # DAILY DEDUP
            # (Bypassed in FORCE mode.)
            # --------------------------------------------

            if (
                not force_mode
                and already_sent_today(
                    paper,
                    daily_sent,
                    message
                )
            ):

                international_skipped_daily += 1

                continue


            matches.append(
                (
                    message,
                    paper,
                    "international"
                )
            )

        else:

            international_skipped_unmatched += 1


    print(
        f"  International scanned: {international_scanned}, "
        f"skipped (old): {international_skipped_old}, "
        f"skipped (duplicate): {international_skipped_duplicate}, "
        f"skipped (unmatched): {international_skipped_unmatched}, "
        f"skipped (already-sent-today): {international_skipped_daily}",
        flush=True
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
            # =================================================

            if source_type == "indian":


                (
                    upload_path,
                    temporary_directory,
                    final_filename
                ) = await prepare_indian_pdf(
                    message,
                    paper
                )


                # ---------------------------------------------
                # Every Indian paper (cleaned or not) is now
                # re-uploaded from disk so the destination
                # always shows the new ordinal filename.
                # ---------------------------------------------

                print(
                    "Uploading Indian PDF...",
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
            # Reuse the existing Telegram media reference so
            # international papers keep their original names
            # and do not require a slow download.
            # =================================================

            else:


                print(
                    "Re-sending existing Telegram media "
                    "(no download, original name preserved)...",
                    flush=True
                )


                await client.send_file(
                    DESTINATION_CHANNEL,
                    message.media,
                    caption=None,
                    force_document=True
                )


                print(
                    f"✓ Sent as: "
                    f"{message.file.name or '(no name)'}",
                    flush=True
                )


                forwarded_international.add(
                    message.id
                )


                forwarded["international"] = sorted(
                    forwarded_international
                )


            # =================================================
            # DAILY DEDUP RECORD
            # =================================================

            mark_sent_today(
                paper,
                daily_sent,
                message
            )


            forwarded["daily_sent"] = daily_sent


            # =================================================
            # SAVE DATABASE AFTER SUCCESS
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

    # ----------------------------------------------------
    # When FORCE mode is on, copy the real database to a
    # side file and switch FORWARDED_FILE to the side file
    # BEFORE main() runs. The production
    # forwarded_messages.json is left untouched.
    # ----------------------------------------------------

    if _force_mode_enabled():

        _enter_force_mode()


    with client:

        client.loop.run_until_complete(
            main()
        )