
# import os
# import sys
# import logging
# from pathlib import Path

# from dotenv import load_dotenv

# # ---------------------------------------------------------------------------
# # Load environment variables from a local .env file (no-op in production if
# # the file does not exist -- cloud platforms inject env vars directly).
# # ---------------------------------------------------------------------------
# load_dotenv()

# logger = logging.getLogger("config")

# # ---------------------------------------------------------------------------
# # Base directory of the project (used to resolve resume.pdf, database path).
# # ---------------------------------------------------------------------------
# BASE_DIR = Path(__file__).resolve().parent


# def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
#     """
#     Small helper to fetch an environment variable with optional
#     "required" enforcement. Fails fast (at import time) with a clear
#     error message if a required variable is missing -- this is much
#     easier to debug on a fresh cloud deployment than a cryptic runtime
#     KeyError buried deep in the code.
#     """
#     value = os.getenv(name, default)
#     if required and (value is None or value.strip() == ""):
#         logger.critical("Missing required environment variable: %s", name)
#         raise RuntimeError(
#             f"Missing required environment variable '{name}'. "
#             f"Please set it in your .env file or your hosting platform's "
#             f"environment variable settings."
#         )
#     return value


# # ---------------------------------------------------------------------------
# # Telegram Bot Configuration
# # ---------------------------------------------------------------------------
# TELEGRAM_BOT_TOKEN: str = _get_env("TELEGRAM_BOT_TOKEN", required=True)

# # ---------------------------------------------------------------------------
# # SMTP (Gmail App Password) Configuration
# # ---------------------------------------------------------------------------
# SMTP_HOST: str = _get_env("SMTP_HOST", default="smtp.gmail.com")
# SMTP_PORT: int = int(_get_env("SMTP_PORT", default="587"))
# SMTP_EMAIL: str = _get_env("SMTP_EMAIL", required=True)
# SMTP_APP_PASSWORD: str = _get_env("SMTP_APP_PASSWORD", required=True)

# # Display name used in the "From" header of outgoing emails.
# SENDER_NAME: str = _get_env("SENDER_NAME", default="Job Applicant")

# # ---------------------------------------------------------------------------
# # Applicant / Email Content Configuration
# # ---------------------------------------------------------------------------
# APPLICANT_NAME: str = _get_env("APPLICANT_NAME", default="Applicant")
# APPLICANT_PHONE: str = _get_env("APPLICANT_PHONE", default="")
# APPLICANT_LINKEDIN: str = _get_env("APPLICANT_LINKEDIN", default="")
# APPLICANT_PORTFOLIO: str = _get_env("APPLICANT_PORTFOLIO", default="")
# APPLICANT_ROLE: str = _get_env("APPLICANT_ROLE", default="Software Engineer Internship")

# # ---------------------------------------------------------------------------
# # Resume attachment path (resolved relative to project root by default).
# # ---------------------------------------------------------------------------
# RESUME_PATH: str = str(BASE_DIR / _get_env("RESUME_FILENAME", default="Aman_Raghav_Updated _Resume.pdf"))

# # ---------------------------------------------------------------------------
# # SQLite database file used to store sent-email history & cooldown tracking.
# # ---------------------------------------------------------------------------
# DATABASE_PATH: str = str(BASE_DIR / _get_env("DATABASE_FILENAME", default="job_mail_bot.db"))

# # ---------------------------------------------------------------------------
# # Cooldown period (in hours) to prevent duplicate emails to the same
# # recipient within a short time window.
# # ---------------------------------------------------------------------------
# DUPLICATE_EMAIL_COOLDOWN_HOURS: float = float(
#     _get_env("DUPLICATE_EMAIL_COOLDOWN_HOURS", default="24")
# )

# # ---------------------------------------------------------------------------
# # Number of subject line suggestions to generate locally (5-10 range).
# # ---------------------------------------------------------------------------
# NUM_SUBJECT_SUGGESTIONS: int = int(_get_env("NUM_SUBJECT_SUGGESTIONS", default="7"))
# if not (5 <= NUM_SUBJECT_SUGGESTIONS <= 10):
#     NUM_SUBJECT_SUGGESTIONS = max(5, min(10, NUM_SUBJECT_SUGGESTIONS))

# # ---------------------------------------------------------------------------
# # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# # ---------------------------------------------------------------------------
# LOG_LEVEL: str = _get_env("LOG_LEVEL", default="INFO").upper()

# # ---------------------------------------------------------------------------
# # Optional: restrict bot usage to specific Telegram user IDs (comma separated)
# # Leave blank to allow anyone to use the bot.
# # ---------------------------------------------------------------------------
# _allowed_ids_raw = _get_env("ALLOWED_TELEGRAM_USER_IDS", default="")
# ALLOWED_TELEGRAM_USER_IDS: set[int] = set()
# if _allowed_ids_raw.strip():
#     try:
#         ALLOWED_TELEGRAM_USER_IDS = {
#             int(uid.strip()) for uid in _allowed_ids_raw.split(",") if uid.strip()
#         }
#     except ValueError:
#         logger.warning(
#             "ALLOWED_TELEGRAM_USER_IDS contains a non-integer value; ignoring restriction."
#         )
#         ALLOWED_TELEGRAM_USER_IDS = set()


# def validate_startup_config() -> None:
#     """
#     Perform a few extra sanity checks at startup (beyond the required-env
#     checks above) so misconfigurations are caught immediately with a
#     friendly error message instead of failing halfway through a user
#     interaction.
#     """
#     if not Path(RESUME_PATH).exists():
#         logger.critical("Resume file not found at path: %s", RESUME_PATH)
#         raise RuntimeError(
#             f"resume.pdf not found at '{RESUME_PATH}'. Please place your resume "
#             f"PDF in the project root (or set RESUME_FILENAME in .env)."
#         )

#     if SMTP_PORT not in (587, 465, 25):
#         logger.warning("Unusual SMTP_PORT '%s' configured; typical values are 587 or 465.", SMTP_PORT)

#     logger.info("Configuration validated successfully.")


# if __name__ == "__main__":
#     # Allow running `python config.py` to quickly sanity-check the .env setup.
#     logging.basicConfig(level=logging.INFO)
#     try:
#         validate_startup_config()
#         print("Configuration OK.")
#     except RuntimeError as exc:
#         print(f"Configuration ERROR: {exc}", file=sys.stderr)
#         sys.exit(1)


"""
config.py
=========
Centralised configuration loader for the Telegram Job Mail Bot.

Every secret / tunable value used across the project (bot.py, mailer.py,
ai_subject.py) is loaded here from environment variables (via a `.env`
file during local development, or directly from the platform's
environment variable settings when deployed to Render / Railway / Koyeb
/ etc.).

Keeping all configuration in a single place makes the bot easy to audit
and deploy without hunting through multiple files for hard-coded values.
"""

import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables from a local .env file (no-op in production if
# the file does not exist -- cloud platforms inject env vars directly).
# ---------------------------------------------------------------------------
load_dotenv()

logger = logging.getLogger("config")

# ---------------------------------------------------------------------------
# Base directory of the project (used to resolve resume.pdf, database path).
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    """
    Small helper to fetch an environment variable with optional
    "required" enforcement. Fails fast (at import time) with a clear
    error message if a required variable is missing -- this is much
    easier to debug on a fresh cloud deployment than a cryptic runtime
    KeyError buried deep in the code.
    """
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        logger.critical("Missing required environment variable: %s", name)
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Please set it in your .env file or your hosting platform's "
            f"environment variable settings."
        )
    return value


# ---------------------------------------------------------------------------
# Telegram Bot Configuration
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = _get_env("TELEGRAM_BOT_TOKEN", required=True)

# ---------------------------------------------------------------------------
# SMTP (Gmail App Password) Configuration
# ---------------------------------------------------------------------------
SMTP_HOST: str = _get_env("SMTP_HOST", default="smtp.gmail.com")
SMTP_PORT: int = int(_get_env("SMTP_PORT", default="587"))
SMTP_EMAIL: str = _get_env("SMTP_EMAIL", required=True)
SMTP_APP_PASSWORD: str = _get_env("SMTP_APP_PASSWORD", required=True)

# Display name used in the "From" header of outgoing emails.
SENDER_NAME: str = _get_env("SENDER_NAME", default="Job Applicant")

# ---------------------------------------------------------------------------
# Applicant / Email Content Configuration
# ---------------------------------------------------------------------------
APPLICANT_NAME: str = _get_env("APPLICANT_NAME", default="Applicant")
APPLICANT_PHONE: str = _get_env("APPLICANT_PHONE", default="")
APPLICANT_LINKEDIN: str = _get_env("APPLICANT_LINKEDIN", default="")
APPLICANT_PORTFOLIO: str = _get_env("APPLICANT_PORTFOLIO", default="")
APPLICANT_ROLE: str = _get_env("APPLICANT_ROLE", default="Software Engineer Internship")

# ---------------------------------------------------------------------------
# Resume attachment path (resolved relative to project root by default).
# ---------------------------------------------------------------------------
RESUME_PATH: str = str(BASE_DIR / _get_env("RESUME_FILENAME", default="resume.pdf"))

# ---------------------------------------------------------------------------
# SQLite database file used to store sent-email history & cooldown tracking.
# ---------------------------------------------------------------------------
DATABASE_PATH: str = str(BASE_DIR / _get_env("DATABASE_FILENAME", default="job_mail_bot.db"))

# ---------------------------------------------------------------------------
# Cooldown period (in hours) to prevent duplicate emails to the same
# recipient within a short time window.
# ---------------------------------------------------------------------------
DUPLICATE_EMAIL_COOLDOWN_HOURS: float = float(
    _get_env("DUPLICATE_EMAIL_COOLDOWN_HOURS", default="24")
)

# ---------------------------------------------------------------------------
# Number of subject line suggestions to generate locally (5-10 range).
# ---------------------------------------------------------------------------
NUM_SUBJECT_SUGGESTIONS: int = int(_get_env("NUM_SUBJECT_SUGGESTIONS", default="7"))
if not (5 <= NUM_SUBJECT_SUGGESTIONS <= 10):
    NUM_SUBJECT_SUGGESTIONS = max(5, min(10, NUM_SUBJECT_SUGGESTIONS))

# ---------------------------------------------------------------------------
# Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# ---------------------------------------------------------------------------
LOG_LEVEL: str = _get_env("LOG_LEVEL", default="INFO").upper()

# ---------------------------------------------------------------------------
# Auto-shutdown (used for 100%-free hosting on GitHub Actions).
#
# GitHub Actions does not allow a job to run forever for free -- but public
# repos get unlimited free minutes for jobs that each run for a bounded
# duration. To exploit this, the bot can be configured to automatically
# stop itself after a fixed number of minutes; a GitHub Actions workflow
# (see .github/workflows/bot.yml) then re-triggers a fresh run shortly
# after, giving a "run N minutes -> rest a few minutes -> run again" cycle.
#
# Set AUTO_SHUTDOWN_MINUTES to 0 (default) to disable this behaviour and
# run the bot forever (recommended for Render/Railway/Koyeb/VPS deployments
# that support long-lived background workers).
# ---------------------------------------------------------------------------
AUTO_SHUTDOWN_MINUTES: float = float(_get_env("AUTO_SHUTDOWN_MINUTES", default="0"))

# ---------------------------------------------------------------------------
# Optional: restrict bot usage to specific Telegram user IDs (comma separated)
# Leave blank to allow anyone to use the bot.
# ---------------------------------------------------------------------------
_allowed_ids_raw = _get_env("ALLOWED_TELEGRAM_USER_IDS", default="")
ALLOWED_TELEGRAM_USER_IDS: set[int] = set()
if _allowed_ids_raw.strip():
    try:
        ALLOWED_TELEGRAM_USER_IDS = {
            int(uid.strip()) for uid in _allowed_ids_raw.split(",") if uid.strip()
        }
    except ValueError:
        logger.warning(
            "ALLOWED_TELEGRAM_USER_IDS contains a non-integer value; ignoring restriction."
        )
        ALLOWED_TELEGRAM_USER_IDS = set()


def validate_startup_config() -> None:
    """
    Perform a few extra sanity checks at startup (beyond the required-env
    checks above) so misconfigurations are caught immediately with a
    friendly error message instead of failing halfway through a user
    interaction.
    """
    if not Path(RESUME_PATH).exists():
        logger.critical("Resume file not found at path: %s", RESUME_PATH)
        raise RuntimeError(
            f"resume.pdf not found at '{RESUME_PATH}'. Please place your resume "
            f"PDF in the project root (or set RESUME_FILENAME in .env)."
        )

    if SMTP_PORT not in (587, 465, 25):
        logger.warning("Unusual SMTP_PORT '%s' configured; typical values are 587 or 465.", SMTP_PORT)

    logger.info("Configuration validated successfully.")


if __name__ == "__main__":
    # Allow running `python config.py` to quickly sanity-check the .env setup.
    logging.basicConfig(level=logging.INFO)
    try:
        validate_startup_config()
        print("Configuration OK.")
    except RuntimeError as exc:
        print(f"Configuration ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
