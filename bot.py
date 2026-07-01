
# import logging
# import re
# import sqlite3
# import threading
# from datetime import datetime, timedelta, timezone

# from telegram import (
#     Update,
#     InlineKeyboardButton,
#     InlineKeyboardMarkup,
# )
# from telegram.constants import ParseMode
# from telegram.ext import (
#     Application,
#     ApplicationBuilder,
#     CommandHandler,
#     CallbackQueryHandler,
#     MessageHandler,
#     ContextTypes,
#     filters,
# )

# import config
# from mailer import send_application_email, EmailSendError
# from ai_subject import generate_subject_suggestions

# # ---------------------------------------------------------------------------
# # Logging configuration
# # ---------------------------------------------------------------------------
# logging.basicConfig(
#     format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
#     level=getattr(logging, config.LOG_LEVEL, logging.INFO),
# )
# # Silence overly chatty third-party loggers while keeping our own logs verbose.
# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("httpcore").setLevel(logging.WARNING)
# logging.getLogger("telegram").setLevel(logging.INFO)

# logger = logging.getLogger("bot")


# # ===========================================================================
# # EMAIL VALIDATION
# # ===========================================================================

# # A pragmatic (not 100% RFC 5322 compliant, but very robust in practice)
# # email validation regex. It rejects obviously malformed addresses while
# # accepting the vast majority of real-world email formats including
# # subdomains, plus-addressing, and common TLD lengths.
# _EMAIL_REGEX = re.compile(
#     r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
#     r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
#     r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
# )

# # A small blocklist of obviously fake / placeholder domains to protect
# # against wasted sends to non-existent addresses. Not exhaustive, and
# # intentionally not too aggressive, since this is a lightweight sanity
# # check rather than a full deliverability/MX lookup.
# _DISPOSABLE_OR_PLACEHOLDER_DOMAINS = {
#     "example.com",
#     "example.org",
#     "example.net",
#     "test.com",
#     "domain.com",
#     "email.com",
#     "mailinator.com",
# }


# def is_valid_email(email: str) -> tuple[bool, str]:
#     """
#     Validate an email address string.

#     Returns:
#         (is_valid, error_message). error_message is empty when valid.
#     """
#     email = email.strip()

#     if not email:
#         return False, "Email address cannot be empty."

#     if len(email) > 254:
#         return False, "Email address is too long to be valid."

#     if " " in email:
#         return False, "Email address must not contain spaces."

#     if email.count("@") != 1:
#         return False, "Email address must contain exactly one '@' symbol."

#     if not _EMAIL_REGEX.match(email):
#         return False, (
#             "That doesn't look like a valid email address. "
#             "Please send a properly formatted address, e.g. hr@company.com"
#         )

#     domain = email.split("@", 1)[1].lower()
#     if domain in _DISPOSABLE_OR_PLACEHOLDER_DOMAINS:
#         return False, (
#             f"'{domain}' looks like a placeholder/test domain. "
#             f"Please provide a real HR/company email address."
#         )

#     return True, ""


# # ===========================================================================
# # SQLITE DATABASE LAYER
# # ===========================================================================
# # A single shared connection is used with `check_same_thread=False` because
# # blocking DB calls are dispatched to worker threads via `asyncio.to_thread`.
# # A module-level lock guards write access to avoid race conditions between
# # concurrent handler invocations.

# _db_lock = threading.Lock()
# _db_connection: sqlite3.Connection | None = None


# def _get_connection() -> sqlite3.Connection:
#     """Lazily create (once) and return the shared SQLite connection."""
#     global _db_connection
#     if _db_connection is None:
#         _db_connection = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
#         _db_connection.row_factory = sqlite3.Row
#     return _db_connection


# def init_db() -> None:
#     """
#     Initialize the SQLite database schema if it does not already exist.
#     Called once at bot startup.
#     """
#     with _db_lock:
#         conn = _get_connection()
#         conn.execute(
#             """
#             CREATE TABLE IF NOT EXISTS sent_emails (
#                 id                INTEGER PRIMARY KEY AUTOINCREMENT,
#                 telegram_user_id  INTEGER NOT NULL,
#                 telegram_username TEXT,
#                 recipient_email   TEXT NOT NULL,
#                 subject           TEXT NOT NULL,
#                 sent_at_utc       TEXT NOT NULL
#             )
#             """
#         )
#         conn.execute(
#             "CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient "
#             "ON sent_emails (recipient_email)"
#         )
#         conn.execute(
#             "CREATE INDEX IF NOT EXISTS idx_sent_emails_user "
#             "ON sent_emails (telegram_user_id)"
#         )
#         conn.commit()
#     logger.info("SQLite database initialized at %s", config.DATABASE_PATH)


# def record_sent_email(telegram_user_id: int, telegram_username: str | None,
#                        recipient_email: str, subject: str) -> None:
#     """Persist a record of a successfully sent email."""
#     sent_at_utc = datetime.now(timezone.utc).isoformat()
#     with _db_lock:
#         conn = _get_connection()
#         conn.execute(
#             """
#             INSERT INTO sent_emails
#                 (telegram_user_id, telegram_username, recipient_email, subject, sent_at_utc)
#             VALUES (?, ?, ?, ?, ?)
#             """,
#             (telegram_user_id, telegram_username, recipient_email, subject, sent_at_utc),
#         )
#         conn.commit()


# def get_last_sent_record(recipient_email: str) -> sqlite3.Row | None:
#     """
#     Return the most recent sent-email record for a given recipient
#     (regardless of which Telegram user sent it), or None if never sent.
#     """
#     with _db_lock:
#         conn = _get_connection()
#         cursor = conn.execute(
#             """
#             SELECT * FROM sent_emails
#             WHERE recipient_email = ?
#             ORDER BY sent_at_utc DESC
#             LIMIT 1
#             """,
#             (recipient_email,),
#         )
#         return cursor.fetchone()


# def get_user_history(telegram_user_id: int, limit: int = 10) -> list[sqlite3.Row]:
#     """Return the most recent sent-email records for a given Telegram user."""
#     with _db_lock:
#         conn = _get_connection()
#         cursor = conn.execute(
#             """
#             SELECT * FROM sent_emails
#             WHERE telegram_user_id = ?
#             ORDER BY sent_at_utc DESC
#             LIMIT ?
#             """,
#             (telegram_user_id, limit),
#         )
#         return cursor.fetchall()


# def check_cooldown(recipient_email: str) -> tuple[bool, timedelta | None]:
#     """
#     Check whether `recipient_email` was emailed within the configured
#     cooldown window.

#     Returns:
#         (is_within_cooldown, time_remaining). If not within cooldown,
#         returns (False, None).
#     """
#     record = get_last_sent_record(recipient_email)
#     if record is None:
#         return False, None

#     last_sent_at = datetime.fromisoformat(record["sent_at_utc"])
#     if last_sent_at.tzinfo is None:
#         last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)

#     cooldown_delta = timedelta(hours=config.DUPLICATE_EMAIL_COOLDOWN_HOURS)
#     elapsed = datetime.now(timezone.utc) - last_sent_at

#     if elapsed < cooldown_delta:
#         return True, (cooldown_delta - elapsed)
#     return False, None


# # ===========================================================================
# # ACCESS CONTROL (optional allow-list)
# # ===========================================================================

# def _is_user_allowed(user_id: int) -> bool:
#     """
#     If config.ALLOWED_TELEGRAM_USER_IDS is non-empty, restrict bot usage
#     to only those Telegram user IDs. Otherwise, allow everyone.
#     """
#     if not config.ALLOWED_TELEGRAM_USER_IDS:
#         return True
#     return user_id in config.ALLOWED_TELEGRAM_USER_IDS


# # ===========================================================================
# # HELPERS: subject suggestion state management (per-user, in-memory via
# # context.user_data, which python-telegram-bot persists per chat/user for
# # the lifetime of the running process).
# # ===========================================================================

# # Keys used inside `context.user_data`
# _UD_PENDING_EMAIL = "pending_recipient_email"
# _UD_PENDING_SUBJECTS = "pending_subject_suggestions"


# def _build_subject_keyboard(subjects: list[str], force: bool = False) -> InlineKeyboardMarkup:
#     """
#     Build the inline keyboard of subject line suggestions.

#     Each button's callback_data encodes the subject's index (not the full
#     text, to stay well within Telegram's 64-byte callback_data limit) and
#     whether this is a "forced" send (bypassing the duplicate cooldown
#     warning).
#     """
#     prefix = "force_subj" if force else "subj"
#     buttons = [
#         [InlineKeyboardButton(text=_truncate_button_text(subject), callback_data=f"{prefix}:{idx}")]
#         for idx, subject in enumerate(subjects)
#     ]
#     if not force:
#         buttons.append([InlineKeyboardButton(text="Cancel", callback_data="cancel_subjects")])
#     return InlineKeyboardMarkup(buttons)


# def _truncate_button_text(text: str, max_len: int = 60) -> str:
#     """Telegram inline buttons render best with reasonably short text."""
#     return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


# # ===========================================================================
# # COMMAND HANDLERS
# # ===========================================================================

# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle the /start command -- greet the user and explain usage."""
#     user = update.effective_user

#     if not _is_user_allowed(user.id):
#         await update.message.reply_text(
#             "🚫 Sorry, you are not authorized to use this bot."
#         )
#         logger.warning("Unauthorized access attempt from user_id=%s (%s)", user.id, user.username)
#         return

#     welcome_text = (
#         f"👋 Hello <b>{user.first_name or 'there'}</b>!\n\n"
#         "I'm your <b>Job Application Mail Bot</b>. Here's how I can help:\n\n"
#         "1️⃣ Send me the <b>HR / recruiter email address</b> you want to apply to "
#         "(e.g. <code>hr@company.com</code>).\n"
#         "2️⃣ I'll generate several professional <b>subject line</b> suggestions for you.\n"
#         "3️⃣ Tap the subject you like best.\n"
#         "4️⃣ I'll instantly send your application email with your resume attached! 📎\n\n"
#         "Commands:\n"
#         "/start - Show this welcome message\n"
#         "/help - Show usage instructions\n"
#         "/history - View your recently sent applications\n"
#         "/cancel - Cancel the current operation\n\n"
#         "Ready? Just send me an HR email address to get started. 🚀"
#     )
#     await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle the /help command."""
#     help_text = (
#         "<b>📖 How to use this bot</b>\n\n"
#         "• Send a valid HR/recruiter email address as a plain text message.\n"
#         "• I will suggest several professional email subject lines.\n"
#         "• Tap one of the buttons to instantly send your application "
#         "(resume attached automatically).\n"
#         "• To avoid spamming the same recruiter, I won't resend to the same "
#         f"address within {config.DUPLICATE_EMAIL_COOLDOWN_HOURS:g} hours unless you confirm it explicitly.\n\n"
#         "<b>Commands</b>\n"
#         "/start - Welcome message\n"
#         "/help - This help message\n"
#         "/history - Your last 10 sent applications\n"
#         "/cancel - Cancel the current pending operation"
#     )
#     await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


# async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle the /cancel command -- clear any pending state for the user."""
#     context.user_data.pop(_UD_PENDING_EMAIL, None)
#     context.user_data.pop(_UD_PENDING_SUBJECTS, None)
#     await update.message.reply_text("✅ Cancelled. Send me a new HR email address whenever you're ready.")


# async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle the /history command -- show the user's recently sent applications."""
#     user = update.effective_user

#     if not _is_user_allowed(user.id):
#         await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
#         return

#     try:
#         # NOTE: get_user_history is a fast local SQLite read (indexed lookup
#         # limited to 10 rows), so it's called directly rather than via
#         # asyncio.to_thread -- the operation is near-instant and won't
#         # meaningfully block the event loop.
#         records = get_user_history(user.id)
#     except Exception:
#         logger.exception("Failed to fetch history for user_id=%s", user.id)
#         await update.message.reply_text("⚠️ Could not fetch your history right now. Please try again later.")
#         return

#     if not records:
#         await update.message.reply_text("📭 You haven't sent any applications yet.")
#         return

#     lines = ["<b>📜 Your recent applications:</b>\n"]
#     for row in records:
#         sent_at = datetime.fromisoformat(row["sent_at_utc"]).strftime("%Y-%m-%d %H:%M UTC")
#         lines.append(
#             f"• <b>{row['recipient_email']}</b>\n"
#             f"   Subject: {row['subject']}\n"
#             f"   Sent: {sent_at}\n"
#         )
#     await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# # ===========================================================================
# # MESSAGE HANDLER: receive & validate the HR email address
# # ===========================================================================

# async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """
#     Handle plain text messages. In this bot's simple linear workflow, any
#     non-command text message the user sends is treated as an attempted
#     HR email address submission.
#     """
#     user = update.effective_user

#     if not _is_user_allowed(user.id):
#         await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
#         return

#     raw_text = (update.message.text or "").strip()

#     # --- Step 1: Validate the email address ---------------------------------
#     is_valid, error_message = is_valid_email(raw_text)
#     if not is_valid:
#         await update.message.reply_text(
#             f"❌ {error_message}\n\nPlease send a valid HR email address, e.g. hr@company.com"
#         )
#         return

#     recipient_email = raw_text.lower()
#     logger.info("User %s (%s) submitted recipient email: %s", user.id, user.username, recipient_email)

#     # --- Step 2: Let the user know we're working on it -----------------------
#     status_message = await update.message.reply_text(
#         "🤖 Generating professional subject line suggestions for you... please wait a moment."
#     )

#     # --- Step 3: Generate subject line suggestions (local, no external API) --
#     try:
#         subjects = await _run_blocking(generate_subject_suggestions, recipient_email)
#     except Exception:
#         logger.exception("Unexpected failure generating subjects for %s", recipient_email)
#         await status_message.edit_text(
#             "⚠️ Something went wrong while generating subject suggestions. Please try again in a moment."
#         )
#         return

#     if not subjects:
#         await status_message.edit_text(
#             "⚠️ I couldn't generate any subject suggestions right now. Please try again shortly."
#         )
#         return

#     # --- Step 4: Store pending state & show inline keyboard -----------------
#     context.user_data[_UD_PENDING_EMAIL] = recipient_email
#     context.user_data[_UD_PENDING_SUBJECTS] = subjects

#     keyboard = _build_subject_keyboard(subjects, force=False)

#     await status_message.edit_text(
#         f"✅ Here are some professional subject line suggestions for "
#         f"<b>{recipient_email}</b>.\n\nTap one to send your application email instantly:",
#         parse_mode=ParseMode.HTML,
#         reply_markup=keyboard,
#     )


# # ===========================================================================
# # CALLBACK QUERY HANDLER: user taps a subject line suggestion
# # ===========================================================================

# async def handle_subject_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """
#     Handle the inline keyboard button tap when a user selects a subject
#     line suggestion (or confirms a "send anyway" override after a
#     duplicate-cooldown warning), and trigger the email sending workflow.
#     """
#     query = update.callback_query
#     user = update.effective_user

#     # Telegram requires callback queries to be acknowledged; do this early
#     # so the client doesn't show a perpetual "loading" spinner on the button.
#     await query.answer()

#     if not _is_user_allowed(user.id):
#         await query.edit_message_text("🚫 Sorry, you are not authorized to use this bot.")
#         return

#     data = query.data or ""

#     # --- Handle "Cancel" -----------------------------------------------------
#     if data == "cancel_subjects":
#         context.user_data.pop(_UD_PENDING_EMAIL, None)
#         context.user_data.pop(_UD_PENDING_SUBJECTS, None)
#         await query.edit_message_text("❌ Cancelled. Send me a new HR email address whenever you're ready.")
#         return

#     # --- Parse callback_data: "subj:<index>" or "force_subj:<index>" --------
#     try:
#         prefix, index_str = data.split(":", 1)
#         index = int(index_str)
#         force_send = prefix == "force_subj"
#     except (ValueError, IndexError):
#         logger.warning("Received malformed callback_data: %s", data)
#         await query.edit_message_text("⚠️ Something went wrong with that button. Please start over with /start.")
#         return

#     recipient_email = context.user_data.get(_UD_PENDING_EMAIL)
#     subjects = context.user_data.get(_UD_PENDING_SUBJECTS)

#     if not recipient_email or not subjects or index < 0 or index >= len(subjects):
#         await query.edit_message_text(
#             "⚠️ This subject selection has expired or is no longer valid. "
#             "Please send the HR email address again to start over."
#         )
#         return

#     selected_subject = subjects[index]

#     # --- Duplicate / cooldown check (skip if this is an explicit override) --
#     if not force_send:
#         is_cooling_down, time_remaining = check_cooldown(recipient_email)
#         if is_cooling_down:
#             hours_left = time_remaining.total_seconds() / 3600
#             warning_keyboard = InlineKeyboardMarkup(
#                 [
#                     [InlineKeyboardButton("✅ Send Anyway", callback_data=f"force_subj:{index}")],
#                     [InlineKeyboardButton("❌ Cancel", callback_data="cancel_subjects")],
#                 ]
#             )
#             await query.edit_message_text(
#                 f"⏳ You already sent an application to <b>{recipient_email}</b> recently "
#                 f"(within the last {config.DUPLICATE_EMAIL_COOLDOWN_HOURS:g}-hour cooldown window).\n\n"
#                 f"Approximately <b>{hours_left:.1f} hour(s)</b> remain before the cooldown expires.\n\n"
#                 f"Do you still want to send this email anyway?",
#                 parse_mode=ParseMode.HTML,
#                 reply_markup=warning_keyboard,
#             )
#             return

#     # --- Attempt to send the email -------------------------------------------
#     await query.edit_message_text(
#         f"📤 Sending your application to <b>{recipient_email}</b>...\nSubject: <i>{selected_subject}</i>",
#         parse_mode=ParseMode.HTML,
#     )

#     try:
#         await _run_blocking(send_application_email, recipient_email, selected_subject)
#     except EmailSendError as exc:
#         logger.error("Failed to send email to %s: %s", recipient_email, exc)
#         await query.edit_message_text(
#             f"❌ <b>Failed to send email.</b>\n\nReason: {_escape_html(str(exc))}\n\n"
#             f"Please check your configuration or try again later.",
#             parse_mode=ParseMode.HTML,
#         )
#         return
#     except Exception:
#         logger.exception("Unexpected error while sending email to %s", recipient_email)
#         await query.edit_message_text(
#             "❌ An unexpected error occurred while sending your email. Please try again later."
#         )
#         return

#     # --- Record success in the database --------------------------------------
#     try:
#         record_sent_email(
#             telegram_user_id=user.id,
#             telegram_username=user.username,
#             recipient_email=recipient_email,
#             subject=selected_subject,
#         )
#     except Exception:
#         # The email was already sent successfully; a DB logging failure
#         # should not be reported to the user as a send failure. We just
#         # log it for operator visibility.
#         logger.exception("Email sent successfully but failed to record history in DB.")

#     # --- Clear pending state for this user -----------------------------------
#     context.user_data.pop(_UD_PENDING_EMAIL, None)
#     context.user_data.pop(_UD_PENDING_SUBJECTS, None)

#     # --- Notify the user of success -------------------------------------------
#     timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
#     await query.edit_message_text(
#         "🎉 <b>Application Sent Successfully!</b>\n\n"
#         f"📧 <b>Recipient:</b> {recipient_email}\n"
#         f"✏️ <b>Subject:</b> {selected_subject}\n"
#         f"🕒 <b>Sent At:</b> {timestamp_str}\n\n"
#         f"Good luck! 🍀 Send another HR email address anytime to apply again.",
#         parse_mode=ParseMode.HTML,
#     )
#     logger.info(
#         "Application email sent successfully by user_id=%s to %s (subject: '%s')",
#         user.id, recipient_email, selected_subject,
#     )


# # ===========================================================================
# # GLOBAL ERROR HANDLER
# # ===========================================================================

# async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """
#     Catch-all error handler registered with the Application. Logs the
#     full exception and, when possible, informs the user something went
#     wrong without leaking internal details.
#     """
#     logger.error("Unhandled exception while processing update: %s", update, exc_info=context.error)

#     if isinstance(update, Update) and update.effective_message:
#         try:
#             await update.effective_message.reply_text(
#                 "⚠️ An unexpected error occurred. Please try again, or use /start to restart."
#             )
#         except Exception:
#             logger.exception("Failed to notify user about the unhandled exception.")


# # ===========================================================================
# # SMALL UTILITIES
# # ===========================================================================

# async def _run_blocking(func, *args):
#     """
#     Run a blocking (synchronous) function in a worker thread so it does
#     not block the asyncio event loop that powers the Telegram bot.
#     """
#     import asyncio
#     return await asyncio.to_thread(func, *args)


# def _escape_html(text: str) -> str:
#     """Minimal HTML escaping for safely embedding dynamic text in HTML-parsed messages."""
#     return (
#         text.replace("&", "&amp;")
#         .replace("<", "&lt;")
#         .replace(">", "&gt;")
#     )


# # ===========================================================================
# # APPLICATION ENTRY POINT
# # ===========================================================================

# def build_application() -> Application:
#     """Construct and configure the python-telegram-bot Application instance."""
#     application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

#     # --- Command handlers -----------------------------------------------------
#     application.add_handler(CommandHandler("start", start_command))
#     application.add_handler(CommandHandler("help", help_command))
#     application.add_handler(CommandHandler("cancel", cancel_command))
#     application.add_handler(CommandHandler("history", history_command))

#     # --- Callback query handler (inline keyboard button taps) -----------------
#     application.add_handler(CallbackQueryHandler(handle_subject_selection))

#     # --- Plain text message handler (HR email submission) ---------------------
#     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

#     # --- Global error handler --------------------------------------------------
#     application.add_error_handler(error_handler)

#     return application


# def main() -> None:
#     """Application entry point: validate config, init DB, and start polling."""
#     logger.info("Starting Telegram Job Mail Bot...")

#     # Fail fast on misconfiguration (missing resume.pdf, bad env vars, etc.)
#     config.validate_startup_config()

#     # Initialize the SQLite database (creates tables if not present).
#     init_db()

#     application = build_application()

#     logger.info("Bot is now polling for updates...")
#     application.run_polling(
#         allowed_updates=Update.ALL_TYPES,
#         drop_pending_updates=True,
#     )


# if __name__ == "__main__":
#     main()



"""
bot.py
======
Production-ready Telegram Job Mail Bot.

This single file contains (by design, to keep the project minimal):
    - Telegram bot setup & handler registration (python-telegram-bot v22+)
    - Inline keyboard construction & callback handling
    - SQLite database operations (sent-email history + duplicate/cooldown
      prevention)
    - Input validation (email address validation)
    - The full end-to-end workflow described below
    - Logging & comprehensive exception handling

Workflow
--------
1. User sends /start.
2. User sends an HR email address (plain text message, e.g. hr@company.com).
3. The bot validates the email address format.
4. If valid, the bot generates (locally, no external API/key needed --
   see ai_subject.py) 5-10 professional subject line suggestions for a
   job/internship application email.
5. The bot displays the suggestions as Telegram inline keyboard buttons.
6. When the user taps a suggestion, the bot:
     a. Checks the SQLite history to prevent sending a duplicate email to
        the same recipient within a configurable cooldown window.
     b. Sends the email via Gmail SMTP (mailer.py), with the resume PDF
        attached and a predefined HTML body.
     c. Records the sent email in the SQLite database.
     d. Replies with a success message containing the recipient, the
        subject used, and a timestamp.
7. All failure conditions (invalid email, SMTP failure, duplicate
   email, missing resume, etc.) are handled gracefully with clear,
   user-friendly error messages.

Run locally:
    python bot.py

Deploy:
    Works out of the box on Render / Railway / Koyeb / any host that can
    run a long-lived Python process, using long-polling (no webhook / no
    public URL required). All secrets are read from environment
    variables via config.py / python-dotenv.
"""

import logging
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
from mailer import send_application_email, EmailSendError
from ai_subject import generate_subject_suggestions

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
# Silence overly chatty third-party loggers while keeping our own logs verbose.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

logger = logging.getLogger("bot")


# ===========================================================================
# EMAIL VALIDATION
# ===========================================================================

# A pragmatic (not 100% RFC 5322 compliant, but very robust in practice)
# email validation regex. It rejects obviously malformed addresses while
# accepting the vast majority of real-world email formats including
# subdomains, plus-addressing, and common TLD lengths.
_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

# A small blocklist of obviously fake / placeholder domains to protect
# against wasted sends to non-existent addresses. Not exhaustive, and
# intentionally not too aggressive, since this is a lightweight sanity
# check rather than a full deliverability/MX lookup.
_DISPOSABLE_OR_PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "test.com",
    "domain.com",
    "email.com",
    "mailinator.com",
}


def is_valid_email(email: str) -> tuple[bool, str]:
    """
    Validate an email address string.

    Returns:
        (is_valid, error_message). error_message is empty when valid.
    """
    email = email.strip()

    if not email:
        return False, "Email address cannot be empty."

    if len(email) > 254:
        return False, "Email address is too long to be valid."

    if " " in email:
        return False, "Email address must not contain spaces."

    if email.count("@") != 1:
        return False, "Email address must contain exactly one '@' symbol."

    if not _EMAIL_REGEX.match(email):
        return False, (
            "That doesn't look like a valid email address. "
            "Please send a properly formatted address, e.g. hr@company.com"
        )

    domain = email.split("@", 1)[1].lower()
    if domain in _DISPOSABLE_OR_PLACEHOLDER_DOMAINS:
        return False, (
            f"'{domain}' looks like a placeholder/test domain. "
            f"Please provide a real HR/company email address."
        )

    return True, ""


# ===========================================================================
# SQLITE DATABASE LAYER
# ===========================================================================
# A single shared connection is used with `check_same_thread=False` because
# blocking DB calls are dispatched to worker threads via `asyncio.to_thread`.
# A module-level lock guards write access to avoid race conditions between
# concurrent handler invocations.

_db_lock = threading.Lock()
_db_connection: sqlite3.Connection | None = None


def _get_connection() -> sqlite3.Connection:
    """Lazily create (once) and return the shared SQLite connection."""
    global _db_connection
    if _db_connection is None:
        _db_connection = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row
    return _db_connection


def init_db() -> None:
    """
    Initialize the SQLite database schema if it does not already exist.
    Called once at bot startup.
    """
    with _db_lock:
        conn = _get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_emails (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id  INTEGER NOT NULL,
                telegram_username TEXT,
                recipient_email   TEXT NOT NULL,
                subject           TEXT NOT NULL,
                sent_at_utc       TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient "
            "ON sent_emails (recipient_email)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sent_emails_user "
            "ON sent_emails (telegram_user_id)"
        )
        conn.commit()
    logger.info("SQLite database initialized at %s", config.DATABASE_PATH)


def record_sent_email(telegram_user_id: int, telegram_username: str | None,
                       recipient_email: str, subject: str) -> None:
    """Persist a record of a successfully sent email."""
    sent_at_utc = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        conn = _get_connection()
        conn.execute(
            """
            INSERT INTO sent_emails
                (telegram_user_id, telegram_username, recipient_email, subject, sent_at_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_user_id, telegram_username, recipient_email, subject, sent_at_utc),
        )
        conn.commit()


def get_last_sent_record(recipient_email: str) -> sqlite3.Row | None:
    """
    Return the most recent sent-email record for a given recipient
    (regardless of which Telegram user sent it), or None if never sent.
    """
    with _db_lock:
        conn = _get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM sent_emails
            WHERE recipient_email = ?
            ORDER BY sent_at_utc DESC
            LIMIT 1
            """,
            (recipient_email,),
        )
        return cursor.fetchone()


def get_user_history(telegram_user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    """Return the most recent sent-email records for a given Telegram user."""
    with _db_lock:
        conn = _get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM sent_emails
            WHERE telegram_user_id = ?
            ORDER BY sent_at_utc DESC
            LIMIT ?
            """,
            (telegram_user_id, limit),
        )
        return cursor.fetchall()


def check_cooldown(recipient_email: str) -> tuple[bool, timedelta | None]:
    """
    Check whether `recipient_email` was emailed within the configured
    cooldown window.

    Returns:
        (is_within_cooldown, time_remaining). If not within cooldown,
        returns (False, None).
    """
    record = get_last_sent_record(recipient_email)
    if record is None:
        return False, None

    last_sent_at = datetime.fromisoformat(record["sent_at_utc"])
    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)

    cooldown_delta = timedelta(hours=config.DUPLICATE_EMAIL_COOLDOWN_HOURS)
    elapsed = datetime.now(timezone.utc) - last_sent_at

    if elapsed < cooldown_delta:
        return True, (cooldown_delta - elapsed)
    return False, None


# ===========================================================================
# ACCESS CONTROL (optional allow-list)
# ===========================================================================

def _is_user_allowed(user_id: int) -> bool:
    """
    If config.ALLOWED_TELEGRAM_USER_IDS is non-empty, restrict bot usage
    to only those Telegram user IDs. Otherwise, allow everyone.
    """
    if not config.ALLOWED_TELEGRAM_USER_IDS:
        return True
    return user_id in config.ALLOWED_TELEGRAM_USER_IDS


# ===========================================================================
# HELPERS: subject suggestion state management (per-user, in-memory via
# context.user_data, which python-telegram-bot persists per chat/user for
# the lifetime of the running process).
# ===========================================================================

# Keys used inside `context.user_data`
_UD_PENDING_EMAIL = "pending_recipient_email"
_UD_PENDING_SUBJECTS = "pending_subject_suggestions"


def _build_subject_keyboard(subjects: list[str], force: bool = False) -> InlineKeyboardMarkup:
    """
    Build the inline keyboard of subject line suggestions.

    Each button's callback_data encodes the subject's index (not the full
    text, to stay well within Telegram's 64-byte callback_data limit) and
    whether this is a "forced" send (bypassing the duplicate cooldown
    warning).
    """
    prefix = "force_subj" if force else "subj"
    buttons = [
        [InlineKeyboardButton(text=_truncate_button_text(subject), callback_data=f"{prefix}:{idx}")]
        for idx, subject in enumerate(subjects)
    ]
    if not force:
        buttons.append([InlineKeyboardButton(text="Cancel", callback_data="cancel_subjects")])
    return InlineKeyboardMarkup(buttons)


def _truncate_button_text(text: str, max_len: int = 60) -> str:
    """Telegram inline buttons render best with reasonably short text."""
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


# ===========================================================================
# COMMAND HANDLERS
# ===========================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command -- greet the user and explain usage."""
    user = update.effective_user

    if not _is_user_allowed(user.id):
        await update.message.reply_text(
            "🚫 Sorry, you are not authorized to use this bot."
        )
        logger.warning("Unauthorized access attempt from user_id=%s (%s)", user.id, user.username)
        return

    welcome_text = (
        f"👋 Hello <b>{user.first_name or 'there'}</b>!\n\n"
        "I'm your <b>Job Application Mail Bot</b>. Here's how I can help:\n\n"
        "1️⃣ Send me the <b>HR / recruiter email address</b> you want to apply to "
        "(e.g. <code>hr@company.com</code>).\n"
        "2️⃣ I'll generate several professional <b>subject line</b> suggestions for you.\n"
        "3️⃣ Tap the subject you like best.\n"
        "4️⃣ I'll instantly send your application email with your resume attached! 📎\n\n"
        "Commands:\n"
        "/start - Show this welcome message\n"
        "/help - Show usage instructions\n"
        "/history - View your recently sent applications\n"
        "/cancel - Cancel the current operation\n\n"
        "Ready? Just send me an HR email address to get started. 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    help_text = (
        "<b>📖 How to use this bot</b>\n\n"
        "• Send a valid HR/recruiter email address as a plain text message.\n"
        "• I will suggest several professional email subject lines.\n"
        "• Tap one of the buttons to instantly send your application "
        "(resume attached automatically).\n"
        "• To avoid spamming the same recruiter, I won't resend to the same "
        f"address within {config.DUPLICATE_EMAIL_COOLDOWN_HOURS:g} hours unless you confirm it explicitly.\n\n"
        "<b>Commands</b>\n"
        "/start - Welcome message\n"
        "/help - This help message\n"
        "/history - Your last 10 sent applications\n"
        "/cancel - Cancel the current pending operation"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cancel command -- clear any pending state for the user."""
    context.user_data.pop(_UD_PENDING_EMAIL, None)
    context.user_data.pop(_UD_PENDING_SUBJECTS, None)
    await update.message.reply_text("✅ Cancelled. Send me a new HR email address whenever you're ready.")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /history command -- show the user's recently sent applications."""
    user = update.effective_user

    if not _is_user_allowed(user.id):
        await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
        return

    try:
        # NOTE: get_user_history is a fast local SQLite read (indexed lookup
        # limited to 10 rows), so it's called directly rather than via
        # asyncio.to_thread -- the operation is near-instant and won't
        # meaningfully block the event loop.
        records = get_user_history(user.id)
    except Exception:
        logger.exception("Failed to fetch history for user_id=%s", user.id)
        await update.message.reply_text("⚠️ Could not fetch your history right now. Please try again later.")
        return

    if not records:
        await update.message.reply_text("📭 You haven't sent any applications yet.")
        return

    lines = ["<b>📜 Your recent applications:</b>\n"]
    for row in records:
        sent_at = datetime.fromisoformat(row["sent_at_utc"]).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"• <b>{row['recipient_email']}</b>\n"
            f"   Subject: {row['subject']}\n"
            f"   Sent: {sent_at}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ===========================================================================
# MESSAGE HANDLER: receive & validate the HR email address
# ===========================================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle plain text messages. In this bot's simple linear workflow, any
    non-command text message the user sends is treated as an attempted
    HR email address submission.
    """
    user = update.effective_user

    if not _is_user_allowed(user.id):
        await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
        return

    raw_text = (update.message.text or "").strip()

    # --- Step 1: Validate the email address ---------------------------------
    is_valid, error_message = is_valid_email(raw_text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_message}\n\nPlease send a valid HR email address, e.g. hr@company.com"
        )
        return

    recipient_email = raw_text.lower()
    logger.info("User %s (%s) submitted recipient email: %s", user.id, user.username, recipient_email)

    # --- Step 2: Let the user know we're working on it -----------------------
    status_message = await update.message.reply_text(
        "🤖 Generating professional subject line suggestions for you... please wait a moment."
    )

    # --- Step 3: Generate subject line suggestions (local, no external API) --
    try:
        subjects = await _run_blocking(generate_subject_suggestions, recipient_email)
    except Exception:
        logger.exception("Unexpected failure generating subjects for %s", recipient_email)
        await status_message.edit_text(
            "⚠️ Something went wrong while generating subject suggestions. Please try again in a moment."
        )
        return

    if not subjects:
        await status_message.edit_text(
            "⚠️ I couldn't generate any subject suggestions right now. Please try again shortly."
        )
        return

    # --- Step 4: Store pending state & show inline keyboard -----------------
    context.user_data[_UD_PENDING_EMAIL] = recipient_email
    context.user_data[_UD_PENDING_SUBJECTS] = subjects

    keyboard = _build_subject_keyboard(subjects, force=False)

    await status_message.edit_text(
        f"✅ Here are some professional subject line suggestions for "
        f"<b>{recipient_email}</b>.\n\nTap one to send your application email instantly:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


# ===========================================================================
# CALLBACK QUERY HANDLER: user taps a subject line suggestion
# ===========================================================================

async def handle_subject_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the inline keyboard button tap when a user selects a subject
    line suggestion (or confirms a "send anyway" override after a
    duplicate-cooldown warning), and trigger the email sending workflow.
    """
    query = update.callback_query
    user = update.effective_user

    # Telegram requires callback queries to be acknowledged; do this early
    # so the client doesn't show a perpetual "loading" spinner on the button.
    await query.answer()

    if not _is_user_allowed(user.id):
        await query.edit_message_text("🚫 Sorry, you are not authorized to use this bot.")
        return

    data = query.data or ""

    # --- Handle "Cancel" -----------------------------------------------------
    if data == "cancel_subjects":
        context.user_data.pop(_UD_PENDING_EMAIL, None)
        context.user_data.pop(_UD_PENDING_SUBJECTS, None)
        await query.edit_message_text("❌ Cancelled. Send me a new HR email address whenever you're ready.")
        return

    # --- Parse callback_data: "subj:<index>" or "force_subj:<index>" --------
    try:
        prefix, index_str = data.split(":", 1)
        index = int(index_str)
        force_send = prefix == "force_subj"
    except (ValueError, IndexError):
        logger.warning("Received malformed callback_data: %s", data)
        await query.edit_message_text("⚠️ Something went wrong with that button. Please start over with /start.")
        return

    recipient_email = context.user_data.get(_UD_PENDING_EMAIL)
    subjects = context.user_data.get(_UD_PENDING_SUBJECTS)

    if not recipient_email or not subjects or index < 0 or index >= len(subjects):
        await query.edit_message_text(
            "⚠️ This subject selection has expired or is no longer valid. "
            "Please send the HR email address again to start over."
        )
        return

    selected_subject = subjects[index]

    # --- Duplicate / cooldown check (skip if this is an explicit override) --
    if not force_send:
        is_cooling_down, time_remaining = check_cooldown(recipient_email)
        if is_cooling_down:
            hours_left = time_remaining.total_seconds() / 3600
            warning_keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Send Anyway", callback_data=f"force_subj:{index}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_subjects")],
                ]
            )
            await query.edit_message_text(
                f"⏳ You already sent an application to <b>{recipient_email}</b> recently "
                f"(within the last {config.DUPLICATE_EMAIL_COOLDOWN_HOURS:g}-hour cooldown window).\n\n"
                f"Approximately <b>{hours_left:.1f} hour(s)</b> remain before the cooldown expires.\n\n"
                f"Do you still want to send this email anyway?",
                parse_mode=ParseMode.HTML,
                reply_markup=warning_keyboard,
            )
            return

    # --- Attempt to send the email -------------------------------------------
    await query.edit_message_text(
        f"📤 Sending your application to <b>{recipient_email}</b>...\nSubject: <i>{selected_subject}</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        await _run_blocking(send_application_email, recipient_email, selected_subject)
    except EmailSendError as exc:
        logger.error("Failed to send email to %s: %s", recipient_email, exc)
        await query.edit_message_text(
            f"❌ <b>Failed to send email.</b>\n\nReason: {_escape_html(str(exc))}\n\n"
            f"Please check your configuration or try again later.",
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception:
        logger.exception("Unexpected error while sending email to %s", recipient_email)
        await query.edit_message_text(
            "❌ An unexpected error occurred while sending your email. Please try again later."
        )
        return

    # --- Record success in the database --------------------------------------
    try:
        record_sent_email(
            telegram_user_id=user.id,
            telegram_username=user.username,
            recipient_email=recipient_email,
            subject=selected_subject,
        )
    except Exception:
        # The email was already sent successfully; a DB logging failure
        # should not be reported to the user as a send failure. We just
        # log it for operator visibility.
        logger.exception("Email sent successfully but failed to record history in DB.")

    # --- Clear pending state for this user -----------------------------------
    context.user_data.pop(_UD_PENDING_EMAIL, None)
    context.user_data.pop(_UD_PENDING_SUBJECTS, None)

    # --- Notify the user of success -------------------------------------------
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    await query.edit_message_text(
        "🎉 <b>Application Sent Successfully!</b>\n\n"
        f"📧 <b>Recipient:</b> {recipient_email}\n"
        f"✏️ <b>Subject:</b> {selected_subject}\n"
        f"🕒 <b>Sent At:</b> {timestamp_str}\n\n"
        f"Good luck! 🍀 Send another HR email address anytime to apply again.",
        parse_mode=ParseMode.HTML,
    )
    logger.info(
        "Application email sent successfully by user_id=%s to %s (subject: '%s')",
        user.id, recipient_email, selected_subject,
    )


# ===========================================================================
# GLOBAL ERROR HANDLER
# ===========================================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catch-all error handler registered with the Application. Logs the
    full exception and, when possible, informs the user something went
    wrong without leaking internal details.
    """
    logger.error("Unhandled exception while processing update: %s", update, exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again, or use /start to restart."
            )
        except Exception:
            logger.exception("Failed to notify user about the unhandled exception.")


# ===========================================================================
# SMALL UTILITIES
# ===========================================================================

async def _run_blocking(func, *args):
    """
    Run a blocking (synchronous) function in a worker thread so it does
    not block the asyncio event loop that powers the Telegram bot.
    """
    import asyncio
    return await asyncio.to_thread(func, *args)


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for safely embedding dynamic text in HTML-parsed messages."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ===========================================================================
# APPLICATION ENTRY POINT
# ===========================================================================

async def _auto_shutdown_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    JobQueue callback that gracefully stops the bot after
    `config.AUTO_SHUTDOWN_MINUTES` minutes have elapsed.

    This is used exclusively to support 100%-free hosting on GitHub
    Actions: a public GitHub repo gets unlimited free Actions minutes,
    but each individual job run cannot run forever. By having the bot
    stop itself cleanly after a bounded duration, an external cron-based
    workflow (see .github/workflows/bot.yml) can repeatedly re-trigger
    fresh runs, giving a "run for N minutes -> rest a few minutes -> run
    again" cycle at zero cost.

    On platforms with proper long-lived workers (Render/Railway/Koyeb/
    VPS), leave AUTO_SHUTDOWN_MINUTES=0 (the default) so the bot simply
    runs forever, as normal.
    """
    logger.info(
        "Auto-shutdown timer reached (%.1f minutes). Stopping the bot gracefully "
        "so an external scheduler can restart a fresh run.",
        config.AUTO_SHUTDOWN_MINUTES,
    )
    context.application.stop_running()


def build_application() -> Application:
    """Construct and configure the python-telegram-bot Application instance."""
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # --- Command handlers -----------------------------------------------------
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("history", history_command))

    # --- Callback query handler (inline keyboard button taps) -----------------
    application.add_handler(CallbackQueryHandler(handle_subject_selection))

    # --- Plain text message handler (HR email submission) ---------------------
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # --- Global error handler --------------------------------------------------
    application.add_error_handler(error_handler)

    # --- Optional auto-shutdown (for free GitHub Actions hosting) -------------
    if config.AUTO_SHUTDOWN_MINUTES > 0:
        if application.job_queue is None:
            logger.warning(
                "AUTO_SHUTDOWN_MINUTES is set but JobQueue is unavailable. "
                "Install with `pip install \"python-telegram-bot[job-queue]\"` "
                "for auto-shutdown to work. Bot will run indefinitely instead."
            )
        else:
            application.job_queue.run_once(
                _auto_shutdown_job,
                when=timedelta(minutes=config.AUTO_SHUTDOWN_MINUTES),
                name="auto_shutdown",
            )
            logger.info(
                "Auto-shutdown enabled: bot will stop itself after %.1f minutes.",
                config.AUTO_SHUTDOWN_MINUTES,
            )

    return application


def main() -> None:
    """Application entry point: validate config, init DB, and start polling."""
    logger.info("Starting Telegram Job Mail Bot...")

    # Fail fast on misconfiguration (missing resume.pdf, bad env vars, etc.)
    config.validate_startup_config()

    # Initialize the SQLite database (creates tables if not present).
    init_db()

    application = build_application()

    logger.info("Bot is now polling for updates...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
