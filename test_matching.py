import importlib.util
import os
import sys
import types

sys.path.insert(0, ".")

# Stub out heavy imports
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

spec = importlib.util.spec_from_file_location("fp", "forward_papers.py")
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)

test_cases = [
    ("Greater Kashmir ● 09‹09‹2026.pdf", "Greater kashmir ❄️❄️❄️", "Greater Kashmir"),
    ("TOI ● Delhi Times ● 09‹09‹2026 .pdf", "The Times Of India 🧻 🚽", "Times of India"),
    ("TOI ● Pune ● 09‹09‹2026 .pdf", "The Times Of India 🧻 🚽", None),
    ("TOI ● Bombay Times ● 09‹09‹2026.pdf", "The Times Of India 🧻 🚽", None),
    ("HT ● Delhi ● 09‹09‹2026 Tr.pdf", "The Hindustan Times 🌵", None),
    ("ET ● Delhi ● 09‹09‹2026 .pdf", "The Economic Times 🍃", None),
]

for filename, caption, expected in test_cases:
    result = fp.identify_indian_paper(filename, caption)
    assert result == expected, (
        f"{filename!r}: expected {expected!r}, got {result!r}"
    )

print("ALL MATCHING TESTS PASSED")