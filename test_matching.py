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


test_cases = [
    ("Hindustan Times Delhi 04 September 2026.pdf", "", "Hindustan Times — Delhi"),
    ("Economic Times Delhi 04 September 2026.pdf", "", "Economic Times — Delhi"),
    ("Times of India Delhi 04 September 2026.pdf", "", "Times of India — Delhi"),
    ("Hindustan Times Mumbai 04 September 2026.pdf", "", None),
]


for filename, caption, expected in test_cases:
    result = identify_paper(filename, caption)
    assert result == expected, (
        f"{filename!r}: expected {expected!r}, got {result!r}"
    )


print("ALL MATCHING TESTS PASSED")