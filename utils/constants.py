import os
import logging
import sys

logger = logging.getLogger(__name__)

# -------------------------------[ Audiobooks ]-------------------------------
AUDIOBOOKS_DIR = os.environ.get("AUDIOBOOKS_DIR", "/audiobooks")


# -------------------------------[ Discord ]-------------------------------
# The Discord webhook URL to send messages to.
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

# The number of books to send as separate embeds. If the number
# is greater than this, a single message without thumbnails will be sent instead.
try:
    MAX_EMBEDS = int(os.environ.get("MAX_DISCORD_EMBEDS", 4))
except ValueError:
    logger.error(
        f"Invalid int MAX_EMBEDS value: {os.environ.get('MAX_EMBEDS')}. Using default of 4."
    )
    MAX_EMBEDS = 4


# ---------------------------------[ GPT ]--------------------------------
# Chat GPT model to use in lookups.
GPT_MODEL = os.environ.get("GPT_MODEL", "gpt-4.1-mini")

# The number of times chat GPT can query audbile. Prevents infinite loops
# if GPT is unable to find a book.
try:
    NUM_LOOKUPS = int(os.environ.get("NUM_GPT_LOOKUPS", 10))
except ValueError:
    logger.error(
        f"Invalid int NUM_GPT_LOOKUPS value: {os.environ.get('NUM_GPT_LOOKUPS')}. Using default of 10."
    )
    NUM_LOOKUPS = 10

# Also requires an OPENAI_API_KEY environment variable to be set.
# See https://developers.openai.com/api/docs/quickstart#create-and-export-an-api-key
# for more details.


# ------------------------------[ QBittorrent ]-------------------------------
QBITTORRENT_ADDRESS = os.environ.get("QBITTORRENT_ADDRESS", "http://localhost:8080")


# ---------------------------------[ FLASK ]--------------------------------
FLASK_PORT = os.environ.get("FLASK_PORT", 8080)


# ---------------------------------[ LOGS ]---------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.environ.get("LOG_DIR", "/tmp/logs")


# ----------------------------[ ENV VALIDATION ]----------------------------
def validate_env():
    if not DISCORD_WEBHOOK:
        logger.warning(
            "DISCORD_WEBHOOK environment variable not set. Discord messages will not be sent."
        )

    if not os.environ.get("OPENAI_API_KEY"):
        logger.critical(
            "OPENAI_API_KEY environment variable not set."
            " GPT lookups will not work. Exiting program."
        )
        sys.exit(1)
    
    try:
        int(FLASK_PORT)
    except ValueError:
        logger.critical(f"FLASK_PORT value '{FLASK_PORT}' not convertible to int. Exiting program")
        sys.exit(1)

