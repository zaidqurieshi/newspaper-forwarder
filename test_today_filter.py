import importlib.util
import os
import sys
import types
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

# Stub out heavy imports so we can import only the date filter
sys.modules["telethon"] = types.ModuleType("telethon")
sys.modules["telethon"].TelegramClient = lambda *a, **k: object()
sys.modules["telethon.sessions"] = types.ModuleType("telethon.sessions")
sys.modules["telethon.sessions"].StringSession = lambda *a, **k: object()
sys.modules["pypdf"] = types.ModuleType("pypdf")
sys.modules["pypdf"].PdfReader = object
sys.modules["pypdf"].PdfWriter = object

os.environ["TELEGRAM_API_ID"] = "1"
os.environ["TELEGRAM_API_HASH"] = "x"
os.environ["TELEGRAM_SESSION_STRING"] = "x"

spec = importlib.util.spec_from_file_location(
    "fp", "forward_papers.py"
)
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)

IST = timezone(timedelta(hours=5, minutes=30))


class M:
    def __init__(self, d):
        self.date = d


now_ist = datetime.now(IST)

# today 09:00 IST -> True
assert fp.is_recent_message(
    M(now_ist.replace(hour=9, minute=0))
) is True, "today morning should pass"

# today 23:30 IST -> True
assert fp.is_recent_message(
    M(now_ist.replace(hour=23, minute=30))
) is True, "tonight should pass"

# yesterday 23:59 IST -> False
assert fp.is_recent_message(
    M((now_ist - timedelta(days=1)).replace(hour=23, minute=59))
) is False, "yesterday must fail"

# 2 days ago -> False (previously passed with 3-day window!)
assert fp.is_recent_message(
    M(now_ist - timedelta(days=2))
) is False, "2 days ago must fail"

# 3 days ago -> False (the old clutter source)
assert fp.is_recent_message(
    M(now_ist - timedelta(days=3))
) is False, "3 days ago must fail"

print("ALL FILTER TESTS PASSED - today-only (IST) works")
