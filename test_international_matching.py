from forward_papers import identify_international_paper


test_files = [
    "The Guardian UK_1308.pdf",
    "NYT 1308.pdf",
    "NYT International ¹³⁰⁸²⁰²⁶.pdf",
    "The-Washington-Post-13-08-2026.pdf",
    "The Sun UK - 13 August 2026.pdf",
    "FT UK.pdf",
    "FT US.pdf",
    "FT EU.pdf",
    "The Wall Street Journal - August 13, 2026.pdf",
    "The-Wall-Street-Jornal-13-ago-2026.pdf",
    "Daily Mirror - 13 August 2026.pdf",
    "The Daily Telegraph - 13 August 2026.pdf",
]


for filename in test_files:

    result = identify_international_paper(
        filename,
        ""
    )

    print(f"{filename}")
    print(f"  → {result}")
    print()