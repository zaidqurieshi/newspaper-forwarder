import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
)


# ============================================================
# STEPWISE TELEGRAM LOGIN (assistant-driven)
#
# Each stage of the Telegram login runs as a separate
# non-interactive command; the in-progress state (staging
# session + phone_code_hash) is persisted between steps in
# .login_state.json:
#
#   1) python session_login.py request +15551234567
#      -> Telegram sends a login code to the account
#   2) python session_login.py code 12345
#      -> submits the code (from the Telegram app)
#   3) python session_login.py password
#      -> only if 2FA is enabled; reads the .login_pw file
#      -> create it with:  printf 'YOUR_PASSWORD' > .login_pw
#
# On success the new session string is written into .env as
# TELEGRAM_SESSION_STRING and all staging files are removed.
# ============================================================

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID") or 0)
API_HASH = os.getenv("TELEGRAM_API_HASH")

STATE_FILE = ".login_state.json"
PW_FILE = ".login_pw"
ENV_FILE = ".env"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def write_session_to_env(session_string):

    if os.path.exists(ENV_FILE):

        with open(ENV_FILE, "r", encoding="utf-8") as handle:
            content = handle.read()

        pattern = re.compile(
            r"^TELEGRAM_SESSION_STRING=.*$",
            re.MULTILINE
        )

        if pattern.search(content):
            content = pattern.sub(
                "TELEGRAM_SESSION_STRING=" + session_string,
                content
            )
        else:
            content += (
                "\nTELEGRAM_SESSION_STRING="
                + session_string + "\n"
            )

        with open(ENV_FILE, "w", encoding="utf-8") as handle:
            handle.write(content)

    else:

        with open(ENV_FILE, "w", encoding="utf-8") as handle:
            handle.write(
                "TELEGRAM_SESSION_STRING="
                + session_string + "\n"
            )


def cleanup():
    for path in (STATE_FILE, PW_FILE):
        if os.path.exists(path):
            os.remove(path)


def finish(client):

    session_string = client.session.save()

    write_session_to_env(session_string)
    cleanup()

    print()
    print("========================================")
    print(" SUCCESS - NEW SESSION SAVED TO .env")
    print("========================================")
    print("Session string length:", len(session_string))
    print("Stored as TELEGRAM_SESSION_STRING in .env")


async def step_request(phone):

    if not API_ID or not API_HASH:
        print("ERROR: TELEGRAM_API_ID / TELEGRAM_API_HASH "
              "missing from .env")
        return

    if not phone.startswith("+"):
        phone = "+" + phone

    client = TelegramClient(
        StringSession(), API_ID, API_HASH
    )
    await client.connect()

    try:
        sent = await client.send_code_request(phone)
    except FloodWaitError as error:
        print("ERROR: Telegram flood wait - retry in "
              f"{error.seconds} seconds")
        await client.disconnect()
        return

    save_state({
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
        "staging_session": client.session.save(),
    })

    print("CODE REQUESTED for", phone)
    print("-> Check the Telegram APP on your phone")
    print("   (message from Telegram, not SMS).")
    print("-> Next: python session_login.py code <CODE>")
    await client.disconnect()


async def step_code(code):

    state = load_state()

    if not state.get("phone_code_hash"):
        print("ERROR: no pending login - run "
              "'session_login.py request <phone>' first")
        return

    client = TelegramClient(
        StringSession(state["staging_session"]),
        API_ID, API_HASH
    )
    await client.connect()

    try:
        await client.sign_in(
            phone=state["phone"],
            code=code.strip(),
            phone_code_hash=state["phone_code_hash"],
        )
    except PhoneCodeInvalidError:
        print("ERROR: code is INVALID - double-check and "
              "re-run: python session_login.py code <CODE>")
        await client.disconnect()
        return
    except PhoneCodeExpiredError:
        print("ERROR: code EXPIRED - re-run: "
              "python session_login.py request "
              + state["phone"])
        await client.disconnect()
        return
    except SessionPasswordNeededError:

        # Persist the staged session: it now holds the
        # pending-2FA authorization needed for the
        # password step.
        state["staging_session"] = client.session.save()
        state["needs_password"] = True
        save_state(state)

        print("2FA IS ENABLED on this account.")
        print("-> Create the password file, then run:")
        print("     printf 'YOUR_2FA_PASSWORD' > .login_pw")
        print("     python session_login.py password")
        await client.disconnect()
        return

    finish(client)
    await client.disconnect()


async def step_password():

    state = load_state()

    if not state.get("needs_password"):
        print("ERROR: no pending 2FA step")
        return

    if os.path.exists(PW_FILE):
        with open(PW_FILE, "r", encoding="utf-8") as handle:
            password = handle.read().strip()
    elif len(sys.argv) > 2:
        password = sys.argv[2]
    else:
        print("ERROR: no password found.")
        print("-> Create it with: "
              "printf 'YOUR_2FA_PASSWORD' > .login_pw")
        return

    client = TelegramClient(
        StringSession(state["staging_session"]),
        API_ID, API_HASH
    )
    await client.connect()

    try:
        await client.sign_in(password=password)
    except Exception as error:
        print("ERROR: password rejected -", error)
        print("(delete .login_pw, fix the password and "
              "retry: python session_login.py password)")
        await client.disconnect()
        return

    finish(client)
    await client.disconnect()


async def main():

    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command == "request":
        await step_request(sys.argv[2])
    elif command == "code":
        await step_code(sys.argv[2])
    elif command == "password":
        await step_password()
    else:
        print("Usage:")
        print("  python session_login.py request +15551234567")
        print("  python session_login.py code 12345")
        print("  python session_login.py password")


asyncio.run(main())
