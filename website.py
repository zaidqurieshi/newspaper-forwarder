import os
from urllib.parse import quote

from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from telethon import TelegramClient
from telethon.sessions import StringSession


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

API_ID = int(
    os.getenv("TELEGRAM_API_ID")
)

API_HASH = os.getenv(
    "TELEGRAM_API_HASH"
)

SESSION_STRING = os.getenv(
    "TELEGRAM_SESSION_STRING"
)

DESTINATION_CHANNEL = int(
    os.getenv(
        "TELEGRAM_DESTINATION_CHANNEL"
    )
)


# ============================================================
# CONFIGURATION CHECK
# ============================================================

if not SESSION_STRING:
    raise RuntimeError(
        "TELEGRAM_SESSION_STRING is missing."
    )

if not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_HASH is missing."
    )

if not DESTINATION_CHANNEL:
    raise RuntimeError(
        "TELEGRAM_DESTINATION_CHANNEL is missing."
    )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Paperdrop",
    description="Open Source News Archive"
)


# ============================================================
# STATIC FILES
#
# This serves:
#
# /static/favicon.png
#
# from:
#
# static/favicon.png
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory="templates"
)


# ============================================================
# TELEGRAM CLIENT
# ============================================================

telegram = TelegramClient(
    StringSession(
        SESSION_STRING
    ),
    API_ID,
    API_HASH
)


# ============================================================
# TELEGRAM CONNECTION
# ============================================================

async def ensure_telegram_connected():

    if telegram.is_connected():
        return

    print(
        "Telegram disconnected. Reconnecting...",
        flush=True
    )

    try:

        await telegram.connect()

    except Exception as error:

        print(
            f"Telegram reconnect failed: {error}",
            flush=True
        )

        raise

    if not await telegram.is_user_authorized():

        raise RuntimeError(
            "Telegram session is not authorized."
        )

    print(
        "Telegram reconnected successfully.",
        flush=True
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    print(
        "Connecting to Telegram...",
        flush=True
    )

    await telegram.connect()

    if not await telegram.is_user_authorized():

        raise RuntimeError(
            "Telegram session is not authorized."
        )

    print(
        "Telegram connected successfully.",
        flush=True
    )

    print(
        f"Destination channel: "
        f"{DESTINATION_CHANNEL}",
        flush=True
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    if telegram.is_connected():

        await telegram.disconnect()

        print(
            "Telegram disconnected.",
            flush=True
        )


# ============================================================
# DISPLAY NAME
# ============================================================

def clean_display_name(
    filename
):

    if not filename:
        return "Newspaper"

    name = filename.strip()

    if name.lower().endswith(
        ".pdf"
    ):
        name = name[:-4]

    return name


# ============================================================
# CATEGORY
# ============================================================

def identify_category(
    filename
):

    text = (
        filename or ""
    ).lower()

    indian_patterns = [
        "times of india",
        "toi",
        "greater kashmir",
        "hindustan times",
        "economic times",
        "asian age",
        "the goan",
        "dt next",
        "morning standard",
        "mid day",
        "mid-day",
    ]

    for pattern in indian_patterns:

        if pattern in text:
            return "Indian"

    return "International"


# ============================================================
# DATE
# ============================================================

def format_date(
    message
):

    if not message.date:
        return ""

    return message.date.strftime(
        "%d-%m-%Y"
    )


# ============================================================
# GET NEWSPAPERS
#
# Only Telegram metadata is read.
#
# NO thumbnails.
# NO PDF downloads here.
# ============================================================

async def get_newspapers():

    await ensure_telegram_connected()

    newspapers = []

    try:

        async for message in telegram.iter_messages(
            DESTINATION_CHANNEL,
            limit=500
        ):

            if not message.file:
                continue

            filename = (
                message.file.name
                or ""
            )

            if not filename.lower().endswith(
                ".pdf"
            ):
                continue

            newspapers.append({

                "id":
                    message.id,

                "filename":
                    filename,

                "name":
                    clean_display_name(
                        filename
                    ),

                "date":
                    format_date(
                        message
                    ),

                "category":
                    identify_category(
                        filename
                    ),

                "size":
                    message.file.size,

            })

    except Exception as error:

        print(
            f"Telegram newspaper read failed: "
            f"{error}",
            flush=True
        )

        # ----------------------------------------------------
        # RECONNECT AND RETRY ONCE
        # ----------------------------------------------------

        try:

            await telegram.disconnect()

        except Exception:
            pass

        await telegram.connect()

        if not await telegram.is_user_authorized():

            raise RuntimeError(
                "Telegram session is not authorized."
            )

        print(
            "Telegram reconnected. "
            "Retrying newspaper list...",
            flush=True
        )

        newspapers = []

        async for message in telegram.iter_messages(
            DESTINATION_CHANNEL,
            limit=500
        ):

            if not message.file:
                continue

            filename = (
                message.file.name
                or ""
            )

            if not filename.lower().endswith(
                ".pdf"
            ):
                continue

            newspapers.append({

                "id":
                    message.id,

                "filename":
                    filename,

                "name":
                    clean_display_name(
                        filename
                    ),

                "date":
                    format_date(
                        message
                    ),

                "category":
                    identify_category(
                        filename
                    ),

                "size":
                    message.file.size,

            })

    return newspapers


# ============================================================
# HOME PAGE
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home(
    request: Request
):

    newspapers = await get_newspapers()

    indian = [
        paper
        for paper in newspapers
        if paper["category"] == "Indian"
    ]

    international = [
        paper
        for paper in newspapers
        if paper["category"] == "International"
    ]

    return templates.TemplateResponse(

        request=request,

        name="index.html",

        context={

            "request":
                request,

            "newspapers":
                newspapers,

            "indian":
                indian,

            "international":
                international,

            "total":
                len(newspapers),

        }
    )


# ============================================================
# DOWNLOAD PDF
#
# The PDF is streamed directly from Telegram.
#
# Nothing is saved to disk.
# No thumbnails are generated.
# ============================================================

@app.get(
    "/download/{message_id}"
)
async def download_pdf(
    message_id: int
):

    await ensure_telegram_connected()

    # --------------------------------------------------------
    # FIND TELEGRAM MESSAGE
    # --------------------------------------------------------

    try:

        message = await telegram.get_messages(

            DESTINATION_CHANNEL,

            ids=message_id

        )

    except Exception as error:

        print(
            f"Telegram message lookup failed: "
            f"{error}",
            flush=True
        )

        # ----------------------------------------------------
        # RECONNECT AND RETRY
        # ----------------------------------------------------

        try:
            await telegram.disconnect()
        except Exception:
            pass

        await telegram.connect()

        if not await telegram.is_user_authorized():

            raise HTTPException(
                status_code=500,
                detail="Telegram session is not authorized."
            )

        message = await telegram.get_messages(

            DESTINATION_CHANNEL,

            ids=message_id

        )

    if not message:

        raise HTTPException(
            status_code=404,
            detail="Newspaper not found."
        )

    if not message.document:

        raise HTTPException(
            status_code=404,
            detail="No document found."
        )

    filename = (
        message.file.name
        or f"newspaper-{message_id}.pdf"
    )

    if not filename.lower().endswith(
        ".pdf"
    ):

        filename += ".pdf"

    print(
        f"Streaming PDF: "
        f"{filename}",
        flush=True
    )


    # ========================================================
    # TELEGRAM PDF STREAM
    # ========================================================

    async def stream_pdf():

        await ensure_telegram_connected()

        iterator = telegram.iter_download(

            message.media,

            request_size=
                1024 * 1024,

            chunk_size=
                1024 * 1024

        )

        try:

            async for chunk in iterator:

                yield bytes(
                    chunk
                )

        finally:

            close_method = getattr(
                iterator,
                "close",
                None
            )

            if close_method:

                result = close_method()

                if hasattr(
                    result,
                    "__await__"
                ):

                    await result


    # ========================================================
    # RESPONSE HEADERS
    # ========================================================

    encoded_filename = quote(
        filename
    )

    headers = {

        "Content-Disposition":
            (
                "attachment; "
                "filename*=UTF-8''"
                f"{encoded_filename}"
            ),

        "Cache-Control":
            "no-store",

        "X-Content-Type-Options":
            "nosniff",

    }


    # ========================================================
    # STREAM RESPONSE
    # ========================================================

    return StreamingResponse(

        stream_pdf(),

        media_type="application/pdf",

        headers=headers

    )


# ============================================================
# SEARCH API
# ============================================================

@app.get(
    "/api/search"
)
async def search(
    q: str = ""
):

    newspapers = await get_newspapers()

    q = q.strip().lower()

    if not q:
        return newspapers

    results = []

    for paper in newspapers:

        searchable = (

            f"{paper['name']} "

            f"{paper['filename']} "

            f"{paper['category']} "

            f"{paper['date']}"

        ).lower()

        if q in searchable:

            results.append(
                paper
            )

    return results


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get(
    "/health"
)
async def health():

    return {

        "status":
            "ok",

        "telegram":
            telegram.is_connected(),

        "pdf_storage":
            False,

        "thumbnails":
            False,

    }