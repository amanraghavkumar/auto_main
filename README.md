#  Telegram Job Mail Bot

A production-ready Telegram bot that automates sending job/internship
application emails. It validates an HR email address, generates several
professional email **subject line suggestions locally** (no external
AI API or API key required), displays them as inline keyboard buttons,
and sends the application email (with your resume attached) via
**Gmail SMTP** the instant you tap a subject.


##  How to Get Each Credential

### Telegram Bot Token
1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. Copy the token BotFather gives you into `TELEGRAM_BOT_TOKEN`.

### Gmail App Password
1. Enable **2-Step Verification** on your Google account: https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail" and copy the 16-character password into `SMTP_APP_PASSWORD`.
4. Set `SMTP_EMAIL` to the corresponding Gmail address.

---

##  Using the Bot

1. Send `/start` to see the welcome message.
2. Send an HR/recruiter email address, e.g.:
   ```
   hr@company.com
   ```
3. The bot validates the address and instantly generates 5–10 professional subject line suggestions (personalized using your name, role, and the recruiter's company name, derived from their email domain).
4. Tap the subject you like best from the inline keyboard.
5. The bot sends the application email (HTML body + `resume.pdf` attached) via Gmail SMTP.
6. You'll receive a confirmation message with the recipient, subject, and timestamp.

Other commands:
- `/help` — usage instructions
- `/history` — view your 10 most recently sent applications
- `/cancel` — cancel a pending email/subject selection

**Duplicate protection:** if you try to email the same address again within
the cooldown window (`DUPL
Use, modify, and deploy freely for personal or commercial job-search automation.
