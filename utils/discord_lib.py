import requests
from . import constants


def send_messages(embeds: list[dict]):
    for embed in embeds:
        requests.post(
            constants.WEBHOOK,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
        )
