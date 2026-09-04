import os
import re

from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.sessions import StringSession


# ============================================================
# SESSION ROTATOR
#
# Creates a brand-new Telegram session (interactive login:
# phone number -> code -> optional 2FA password) and writes
# the resulting StringSession directly into the local .env
# file, replacing the previous TELEGRAM_SESSION_STRING value.
#
# WHY THIS EXISTS: a Telegram session string that is used
# from two different IP addresses simultaneously is killed
# permanently by Telegram (AuthKeyDuplicatedError). Rotating
# to a fresh session fixes it — as long as each runtime
# (GitHub Actions forwarder, website, local runs) keeps its
# OWN separate session.
#
# Usage:
#   .venv/bin/python rotate_session.py
# ============================================================

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID") or 0)
api_hash = os.getenv("TELEGRAM_API_HASH")

if not api_id or not api_hash:
    raise RuntimeError(
        "TELEGRAM_API_ID / TELEGRAM_API_HASH are missing "
        "from .env — add them first."
    )

env_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".env"
)


def write_session_to_env(session_string):

    if os.path.exists(env_path):

        with open(
            env_path,
            "r",
            encoding="utf-8"
        ) as handle:

            content = handle.read()

        pattern = re.compile(
            r"^TELEGRAM_SESSION_STRING=.*$",
            re.MULTILINE
        )

        if pattern.search(content):

            content = pattern.sub(
                "TELEGRAM_SESSION_STRING="
                + session_string,
                content
            )

        else:

            content += (
                "\nTELEGRAM_SESSION_STRING="
                + session_string
                + "\n"
            )

        with open(
            env_path,
            "w",
            encoding="utf-8"
        ) as handle:

            handle.write(content)

    else:

        with open(
            env_path,
            "w",
            encoding="utf-8"
        ) as handle:

            handle.write(
                "TELEGRAM_SESSION_STRING="
                + session_string
                + "\n"
            )


print()
print("========================================")
print(" CREATE A FRESH TELEGRAM SESSION")
print("========================================")
print()
print("You will be asked for your phone number,")
print("the login code sent to your Telegram app,")
print("and your 2FA password (if enabled).")
print()

with TelegramClient(
    StringSession(),
    api_id,
    api_hash
) as client:

    session_string = client.session.save()

write_session_to_env(session_string)

print()
print("========================================")
print(" NEW SESSION SAVED TO .env")
print("========================================")
print()
print("Done. The new session string was written")
print("to .env (TELEGRAM_SESSION_STRING).")
print()
print("Next step — install it as the GitHub secret")
print("used by Actions (only the forwarder uses it):")
print()
print(
    "  gh secret set TELEGRAM_SESSION_STRING"
    " --repo zaidqurieshi/newspaper-forwarder"
    " --body \"$(grep '^TELEGRAM_SESSION_STRING='"
    " .env | cut -d= -f2-)\""
)
print()
print("IMPORTANT: the website (website.py) must use")
print("a DIFFERENT session — generate a second one")
print("and set it as TELEGRAM_SESSION_STRING_WEBSITE")
print("in the website's own .env.")
print()
