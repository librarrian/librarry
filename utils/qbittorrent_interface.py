import requests
import logging
from . import jackett

logger = logging.getLogger(__name__)


class QbittorrentError(Exception):
    pass


class QBittorrentInterface:

    def __init__(self, address: str):
        self.address = address

    def get_torrent_info(self, hash: str) -> dict[str, str | int]:
        response = requests.get(f"{self.address}/api/v2/torrents/info?hashes={hash}")
        if response.status_code != 200:
            raise QbittorrentError(
                f"Failed to get torrent info for {hash}: {response.status_code} - {response.text}"
            )
        try:
            torrent_info = response.json()
            if not torrent_info:
                raise QbittorrentError(
                    f"Failed to get torrent info for {hash}: empty response"
                )

        except requests.JSONDecodeError as e:
            raise QbittorrentError(
                f"Failed to get torrent info for {hash}: failed to parse JSON response: {e}"
            )
        if len(torrent_info) != 1:
            logger.error(
                f"Expected exactly one torrent info for hash {hash}, but got {len(torrent_info)}: {torrent_info}"
            )

        return torrent_info[0]

    def add_torrent(self, link: str):
        magnet_link = jackett.get_magnet(link)
        payload = {"urls": magnet_link, "category": "audiobook"}
        response = requests.post(f"{self.address}/api/v2/torrents/add", data=payload)
        logging.info(f"Add torrent response: {response.status_code} - {response.text}")
        if response.status_code != 200:
            raise QbittorrentError(
                f"Failed to add torrent {magnet_link}: {response.status_code} - {response.text}"
            )
