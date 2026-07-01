"""
ai_subject.py
=============
Generates professional, ready-to-use email subject line suggestions for
job/internship applications.

NOTE: This module does NOT call any external AI API and requires NO API
key. All subject lines are generated locally using a curated set of
professional templates combined with the applicant's details from
config.py (name, target role) and the recipient's company/domain
(extracted from the HR email address). This keeps the bot fully
self-contained, free of external dependencies/costs, and impossible to
break due to API downtime, quota limits, or invalid keys.

The bot calls `generate_subject_suggestions()` after a user submits a
valid HR email address. The resulting list of subject lines is then
rendered as Telegram inline keyboard buttons in bot.py -- the user simply
taps whichever subject they like best.
"""

import logging
import random
import re

import config

logger = logging.getLogger("ai_subject")


def _extract_company_name(recipient_email: str) -> str:
    """
    Derive a human-friendly company name from the recipient's email
    domain, e.g. "hr@bright-solutions.co.in" -> "Bright Solutions".

    This is a best-effort heuristic (no external lookups involved):
      - Take the domain part of the email.
      - Drop common TLD segments (com, in, co, org, net, io, etc.).
      - Replace hyphens/underscores/dots with spaces.
      - Title-case the result.

    Falls back to an empty string if nothing meaningful can be derived,
    in which case templates simply omit the company name.
    """
    try:
        domain = recipient_email.split("@", 1)[1].lower()
    except IndexError:
        return ""

    # Common TLD / multi-part suffixes to strip off the domain.
    known_suffixes = {
        "com", "in", "co", "org", "net", "io", "biz", "info", "us",
        "uk", "ai", "dev", "tech", "app", "gmail", "yahoo", "outlook",
        "hotmail", "protonmail",
    }

    # Also don't try to derive a "company name" from generic public
    # email providers -- there's no meaningful brand to extract.
    generic_providers = {
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
        "protonmail.com", "icloud.com", "aol.com", "rediffmail.com",
        "live.com", "yandex.com", "zoho.com",
    }
    if domain in generic_providers:
        return ""

    parts = domain.split(".")
    # Remove trailing parts that look like TLDs/known suffixes (e.g.
    # "company.co.in" -> ["company"]).
    while len(parts) > 1 and parts[-1] in known_suffixes:
        parts.pop()

    if not parts:
        return ""

    core = parts[0]
    core = re.sub(r"[-_.]+", " ", core).strip()

    if not core or len(core) < 2:
        return ""

    return core.title()


# ---------------------------------------------------------------------------
# A curated bank of professional subject line templates. Placeholders:
#   {name}    -> applicant's full name (config.APPLICANT_NAME)
#   {role}    -> target role/position (config.APPLICANT_ROLE)
#   {company} -> company name derived from the recipient's email domain
#                (some templates gracefully work with or without it)
# ---------------------------------------------------------------------------
_TEMPLATES_WITH_COMPANY = [
    "Application for {role} at {company} - {name}",
    "{name} | Application for {role} Position at {company}",
    "Interested in {role} Opportunity at {company}",
    "Application for {role} Role - {company}",
    "Excited to Apply for {role} at {company} - {name}",
    "{name} - Applying for {role} at {company}",
    "Application for {role} Position | {company}",
    "Seeking {role} Opportunity at {company} - Resume Attached",
    "Enthusiastic Application for {role} at {company}",
    "{name}'s Application for {role} - {company}",
]

_TEMPLATES_WITHOUT_COMPANY = [
    "Application for {role} - {name}",
    "{name} | Application for {role}",
    "Interest in {role} Opportunity - {name}",
    "Application for the Position of {role}",
    "Seeking {role} Opportunity - Resume Attached",
    "{name} - Application for {role} Role",
    "Enthusiastic Application for {role} Position",
    "Application for {role} - Resume Attached",
    "{name}'s Application for the {role} Position",
    "Keen Interest in {role} Opportunity - {name}",
]


def _format_template(template: str, name: str, role: str, company: str) -> str:
    """Fill a template's placeholders and tidy up any leftover whitespace."""
    subject = template.format(name=name, role=role, company=company)
    # Collapse any accidental double spaces (e.g. if company was empty
    # but a template without a company placeholder was used anyway).
    subject = re.sub(r"\s{2,}", " ", subject).strip()
    return subject


def generate_subject_suggestions(recipient_email: str) -> list[str]:
    """
    Generate a list of 5-10 professional email subject line suggestions
    for a job/internship application -- entirely locally, with no
    external API calls or API keys required.

    Args:
        recipient_email: The HR email address the application will be
                          sent to. Used only to (optionally) derive a
                          company name for more personalized subjects.

    Returns:
        A list of subject line strings, length controlled by
        config.NUM_SUBJECT_SUGGESTIONS (clamped between 5 and 10).
    """
    name = config.APPLICANT_NAME.strip() or "Applicant"
    role = config.APPLICANT_ROLE.strip() or "the open position"
    company = _extract_company_name(recipient_email)

    template_pool = _TEMPLATES_WITH_COMPANY if company else _TEMPLATES_WITHOUT_COMPANY

    # Shuffle a copy so suggestions feel fresh across different runs,
    # while remaining fully deterministic in the sense that no network
    # call or external state is involved.
    shuffled_templates = template_pool.copy()
    random.shuffle(shuffled_templates)

    num_needed = config.NUM_SUBJECT_SUGGESTIONS

    subjects: list[str] = []
    seen = set()

    for template in shuffled_templates:
        subject = _format_template(template, name, role, company)
        key = subject.lower()
        if key not in seen:
            seen.add(key)
            subjects.append(subject)
        if len(subjects) >= num_needed:
            break

    # If the chosen pool didn't have enough unique templates (e.g. a
    # very high NUM_SUBJECT_SUGGESTIONS), top up using the other pool's
    # templates as well so we always return the requested count.
    if len(subjects) < num_needed:
        other_pool = _TEMPLATES_WITHOUT_COMPANY if company else _TEMPLATES_WITH_COMPANY
        for template in other_pool:
            subject = _format_template(template, name, role, company or config.APPLICANT_ROLE)
            key = subject.lower()
            if key not in seen:
                seen.add(key)
                subjects.append(subject)
            if len(subjects) >= num_needed:
                break

    logger.info(
        "Generated %d local subject suggestions for recipient domain of '%s' (company='%s').",
        len(subjects), recipient_email, company or "N/A",
    )

    return subjects
