import requests
import os

# The Discord webhook URL to send messages to.
WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

# The number of books to send as separate embeds. If the number
# is greater than this, a single message without thumbnails will be sent instead.
MAX_EMBEDS = os.environ.get("MAX_DISCORD_EMBEDS", 4)


def send_messages(embeds: list[dict]):
    for embed in embeds:
        requests.post(
            WEBHOOK,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
        )
