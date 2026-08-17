import json

data = {
    "indian": [],
    "international": []
}

with open(
    "forwarded_messages.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        data,
        file,
        indent=2
    )

print("forwarded_messages.json created.")
print("No messages were sent.")