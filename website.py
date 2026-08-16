import os
import asyncio
from collections import OrderedDict
from urllib.parse import quote

import pymupdf
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates

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

if not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_HASH is missing."
    )

if not SESSION_STRING:
    raise RuntimeError(
        "TELEGRAM_SESSION_STRING is missing."
    )

if not DESTINATION_CHANNEL:
    raise RuntimeError(
        "TELEGRAM_DESTINATION_CHANNEL is missing."
    )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Newspaper Library",
    description="Telegram-backed newspaper library"
)


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
# THUMBNAIL CONFIGURATION
# ============================================================

# Maximum time allowed for Telegram to provide
# the PDF needed for a thumbnail.

THUMBNAIL_TIMEOUT = 90


# Only allow two thumbnail PDF downloads at once.
#
# This prevents a page containing 30+ newspapers
# from trying to download 30 PDFs simultaneously.

THUMBNAIL_SEMAPHORE = asyncio.Semaphore(2)


# ============================================================
# RAM-ONLY THUMBNAIL CACHE
# ============================================================
#
# IMPORTANT:
#
# We DO NOT save PDFs.
#
# We DO NOT save thumbnails to disk.
#
# We DO NOT use a database.
#
# Thumbnails are kept temporarily in RAM.
#
# Restarting the server clears this cache.
#
# ============================================================

THUMBNAIL_CACHE = OrderedDict()

MAX_THUMBNAILS = 40


def cache_thumbnail(
    message_id,
    image_bytes
):

    THUMBNAIL_CACHE[
        message_id
    ] = image_bytes

    THUMBNAIL_CACHE.move_to_end(
        message_id
    )

    while len(
        THUMBNAIL_CACHE
    ) > MAX_THUMBNAILS:

        THUMBNAIL_CACHE.popitem(
            last=False
        )


def get_cached_thumbnail(
    message_id
):

    image = THUMBNAIL_CACHE.get(
        message_id
    )

    if image is not None:

        THUMBNAIL_CACHE.move_to_end(
            message_id
        )

    return image


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

    print(
        "Disconnecting from Telegram...",
        flush=True
    )

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
# ============================================================
#
# This function reads Telegram metadata only.
#
# It DOES NOT download PDFs.
#
# ============================================================

async def get_newspapers():

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

        message_id = message.id

        newspapers.append({

            # REAL destination-channel ID
            "id":
                message_id,

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

            # First page thumbnail
            "thumbnail_url":
                (
                    f"/thumbnail/"
                    f"{message_id}"
                    f"?v={message_id}"
                ),

            # Direct Telegram-backed download
            "download_url":
                (
                    f"/download/"
                    f"{message_id}"
                ),

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

        if paper["category"]
        == "Indian"

    ]

    international = [

        paper

        for paper in newspapers

        if paper["category"]
        == "International"

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
# DOWNLOAD PDF TO MEMORY
# ============================================================

async def download_pdf_to_memory(
    message
):

    pdf_bytes = bytearray()

    iterator = telegram.iter_download(

        message.media,

        request_size=
            1024 * 1024,

        chunk_size=
            1024 * 1024

    )

    async for chunk in iterator:

        pdf_bytes.extend(
            chunk
        )

    return bytes(
        pdf_bytes
    )


# ============================================================
# CREATE FIRST-PAGE THUMBNAIL
# ============================================================

async def create_thumbnail(
    message_id
):

    # --------------------------------------------------------
    # CHECK RAM CACHE
    # --------------------------------------------------------

    cached = get_cached_thumbnail(
        message_id
    )

    if cached is not None:

        print(
            f"Thumbnail cache hit: "
            f"{message_id}",
            flush=True
        )

        return cached


    # --------------------------------------------------------
    # LIMIT SIMULTANEOUS TELEGRAM DOWNLOADS
    # --------------------------------------------------------

    async with THUMBNAIL_SEMAPHORE:

        # Check cache again after waiting for semaphore.

        cached = get_cached_thumbnail(
            message_id
        )

        if cached is not None:

            return cached


        print(
            f"Generating thumbnail for "
            f"destination message "
            f"{message_id}",
            flush=True
        )


        # ----------------------------------------------------
        # GET MESSAGE FROM DESTINATION CHANNEL
        # ----------------------------------------------------

        message = await telegram.get_messages(

            DESTINATION_CHANNEL,

            ids=message_id

        )

        if not message:

            raise HTTPException(

                status_code=404,

                detail=(
                    "Newspaper not found "
                    "in destination channel."
                )

            )


        if not message.document:

            raise HTTPException(

                status_code=404,

                detail="Message has no document."

            )


        filename = (
            message.file.name
            or ""
        )


        if not filename.lower().endswith(
            ".pdf"
        ):

            raise HTTPException(

                status_code=400,

                detail="File is not a PDF."

            )


        print(
            f"Reading PDF for thumbnail: "
            f"{filename}",
            flush=True
        )


        # ----------------------------------------------------
        # DOWNLOAD PDF INTO RAM ONLY
        # ----------------------------------------------------

        try:

            pdf_bytes = await asyncio.wait_for(

                download_pdf_to_memory(
                    message
                ),

                timeout=THUMBNAIL_TIMEOUT

            )

        except asyncio.TimeoutError:

            print(
                f"Thumbnail timeout after "
                f"{THUMBNAIL_TIMEOUT}s: "
                f"{filename}",
                flush=True
            )

            raise HTTPException(

                status_code=504,

                detail=(
                    "PDF took too long to "
                    "download from Telegram."
                )

            )

        except Exception as error:

            print(
                f"Telegram PDF download failed "
                f"for {filename}: "
                f"{repr(error)}",
                flush=True
            )

            raise HTTPException(

                status_code=502,

                detail=(
                    "Could not download PDF "
                    "from Telegram."
                )

            )


        if not pdf_bytes:

            raise HTTPException(

                status_code=404,

                detail=(
                    "Telegram returned "
                    "an empty PDF."
                )

            )


        print(
            f"Downloaded "
            f"{len(pdf_bytes):,} bytes "
            f"for {filename}",
            flush=True
        )


        # ----------------------------------------------------
        # RENDER FIRST PAGE
        # ----------------------------------------------------

        document = None

        try:

            document = pymupdf.open(

                stream=pdf_bytes,

                filetype="pdf"

            )


            if document.page_count < 1:

                raise RuntimeError(
                    "PDF contains no pages."
                )


            page = document.load_page(
                0
            )


            # Render first page.

            matrix = pymupdf.Matrix(
                1.25,
                1.25
            )


            pixmap = page.get_pixmap(

                matrix=matrix,

                alpha=False

            )


            # Convert to JPEG.

            image_bytes = pixmap.tobytes(

                "jpeg",

                jpg_quality=82

            )


        except Exception as error:

            print(
                f"PyMuPDF rendering failed "
                f"for {filename}: "
                f"{repr(error)}",
                flush=True
            )

            raise HTTPException(

                status_code=500,

                detail=(
                    "Could not render first "
                    "page of PDF."
                )

            )

        finally:

            if document is not None:

                document.close()

            # Release the PDF from RAM.

            del pdf_bytes


        # ----------------------------------------------------
        # STORE ONLY JPEG IN RAM
        # ----------------------------------------------------

        cache_thumbnail(

            message_id,

            image_bytes

        )


        print(
            f"Thumbnail generated successfully: "
            f"{filename}",
            flush=True
        )


        return image_bytes


# ============================================================
# THUMBNAIL ENDPOINT
# ============================================================

@app.get(
    "/thumbnail/{message_id}"
)
async def thumbnail(
    message_id: int
):

    image_bytes = await create_thumbnail(
        message_id
    )

    return Response(

        content=image_bytes,

        media_type="image/jpeg",

        headers={

            "Cache-Control":
                "public, max-age=3600",

            "X-Thumbnail-Message-ID":
                str(message_id),

        }

    )


# ============================================================
# DOWNLOAD PDF
# ============================================================
#
# The PDF is streamed directly from Telegram.
#
# The website does NOT save it.
#
# ============================================================

@app.get(
    "/download/{message_id}"
)
async def download_pdf(
    message_id: int
):

    print(
        f"Download requested for "
        f"destination message "
        f"{message_id}",
        flush=True
    )


    # --------------------------------------------------------
    # GET TELEGRAM MESSAGE
    # --------------------------------------------------------

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

            detail="Message has no document."

        )


    filename = (

        message.file.name

        or
        f"newspaper-{message_id}.pdf"

    )


    if not filename.lower().endswith(
        ".pdf"
    ):

        filename += ".pdf"


    encoded_filename = quote(
        filename
    )


    # --------------------------------------------------------
    # STREAM TELEGRAM MEDIA
    # --------------------------------------------------------

    async def stream_pdf():

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


    return StreamingResponse(

        stream_pdf(),

        media_type="application/pdf",

        headers={

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

        "telegram_connected":
            telegram.is_connected(),

        "destination_channel":
            DESTINATION_CHANNEL,

        "pdf_storage":
            False,

        "thumbnail_storage":
            "RAM only",

        "thumbnail_cache_count":
            len(
                THUMBNAIL_CACHE
            ),

    }


# ============================================================
# LOCAL DEVELOPMENT
#
# Render will use its own start command.
#
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "website:app",

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                8000
            )
        ),

        reload=False

    )