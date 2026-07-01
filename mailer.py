
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from pathlib import Path

import config

logger = logging.getLogger("mailer")


class EmailSendError(Exception):
    """Raised when an email fails to send for any reason."""
    pass


def _build_email_html_body() -> str:
    """
    Build the predefined, professional HTML email body used for every
    application. The content is intentionally generic so it can be sent
    to any HR / recruiter email address, while still looking polished
    and personalised using the applicant's details from config.py.
    """
    contact_lines = []
    if config.APPLICANT_PHONE:
        contact_lines.append(f"<li>Phone: {config.APPLICANT_PHONE}</li>")
    if config.APPLICANT_LINKEDIN:
        contact_lines.append(
            f'<li>LinkedIn: <a href="{config.APPLICANT_LINKEDIN}">{config.APPLICANT_LINKEDIN}</a></li>'
        )
    if config.APPLICANT_PORTFOLIO:
        contact_lines.append(
            f'<li>Portfolio: <a href="{config.APPLICANT_PORTFOLIO}">{config.APPLICANT_PORTFOLIO}</a></li>'
        )
    contact_html = "\n".join(contact_lines)

    html = f"""\
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; color: #222222; line-height: 1.6;">
    <p>Dear Hiring Manager,</p>

    <p>
      I hope this email finds you well. My name is <strong>{config.APPLICANT_NAME}</strong>,
      and I am writing to express my strong interest in the
      <strong>{config.APPLICANT_ROLE}</strong> position at your organization.
    </p>

    <p>
      I have attached my resume for your review, which highlights my academic
      background, technical skills, and relevant project experience. I am
      confident that my skills and enthusiasm make me a strong candidate for
      this opportunity, and I would welcome the chance to discuss how I can
      contribute to your team.
    </p>

    <p>
      I have attached my updated resume to this email for your kind
      consideration. Please feel free to reach out to me at your convenience
      for any further information or to schedule an interview.
    </p>

    {"<p>You can also reach me through:</p><ul>" + contact_html + "</ul>" if contact_html else ""}

    <p>Thank you for your time and consideration. I look forward to hearing from you.</p>

    <p>
      Warm regards,<br>
      <strong>{config.APPLICANT_NAME}</strong><br>
      {config.APPLICANT_PHONE if config.APPLICANT_PHONE else ""}
    </p>
  </body>
</html>
"""
    return html


def _attach_resume(message: MIMEMultipart) -> None:
    """
    Attach the resume PDF (path defined in config.RESUME_PATH) to the
    given MIME message. Raises EmailSendError if the file is missing or
    unreadable so the caller can surface a clean error to the user.
    """
    resume_path = Path(config.RESUME_PATH)

    if not resume_path.exists() or not resume_path.is_file():
        raise EmailSendError(
            f"Resume attachment not found at '{resume_path}'. "
            f"Please make sure resume.pdf exists in the project root."
        )

    try:
        with open(resume_path, "rb") as f:
            resume_data = f.read()
    except OSError as exc:
        raise EmailSendError(f"Failed to read resume file: {exc}") from exc

    attachment = MIMEApplication(resume_data, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=resume_path.name,
    )
    message.attach(attachment)


def send_application_email(recipient_email: str, subject: str) -> None:
    """
    Send the job application email synchronously.

    This is a *blocking* function (uses smtplib directly). It should be
    invoked from async handlers via `asyncio.to_thread(...)` to avoid
    blocking the Telegram bot's event loop.

    Args:
        recipient_email: The HR / recruiter email address to send to.
        subject: The AI-suggested subject line the user selected.

    Raises:
        EmailSendError: If anything goes wrong while composing or
                         sending the email (auth failure, network issue,
                         missing resume, invalid recipient, etc.).
    """
    try:
        message = MIMEMultipart("mixed")
        message["From"] = formataddr((config.SENDER_NAME, config.SMTP_EMAIL))
        message["To"] = recipient_email
        message["Subject"] = subject

        # Attach the HTML body.
        html_body = _build_email_html_body()
        message.attach(MIMEText(html_body, "html"))

        # Attach the resume PDF.
        _attach_resume(message)

        # Connect to Gmail's SMTP server using STARTTLS (port 587) and send.
        context = ssl.create_default_context()

        logger.info(
            "Connecting to SMTP server %s:%s to send email to %s",
            config.SMTP_HOST,
            config.SMTP_PORT,
            recipient_email,
        )

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config.SMTP_EMAIL, config.SMTP_APP_PASSWORD)
            server.sendmail(
                from_addr=config.SMTP_EMAIL,
                to_addrs=[recipient_email],
                msg=message.as_string(),
            )

        logger.info("Email successfully sent to %s with subject '%s'", recipient_email, subject)

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP authentication failed: %s", exc)
        raise EmailSendError(
            "SMTP authentication failed. Please verify SMTP_EMAIL and "
            "SMTP_APP_PASSWORD (use a Gmail App Password, not your normal password)."
        ) from exc

    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("Recipient refused: %s", exc)
        raise EmailSendError(
            f"The recipient address '{recipient_email}' was refused by the mail server. "
            f"Please double-check the email address."
        ) from exc

    except smtplib.SMTPConnectError as exc:
        logger.error("Could not connect to SMTP server: %s", exc)
        raise EmailSendError(
            "Could not connect to the SMTP server. Please check SMTP_HOST/SMTP_PORT "
            "and your network connection."
        ) from exc

    except smtplib.SMTPException as exc:
        logger.error("SMTP error occurred: %s", exc)
        raise EmailSendError(f"An SMTP error occurred while sending the email: {exc}") from exc

    except EmailSendError:
        # Re-raise EmailSendError raised from _attach_resume without wrapping again.
        raise

    except Exception as exc:  # noqa: BLE001 - broad catch is intentional at this top boundary
        logger.exception("Unexpected error while sending email.")
        raise EmailSendError(f"An unexpected error occurred while sending the email: {exc}") from exc
