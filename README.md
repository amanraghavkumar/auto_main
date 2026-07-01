# 📬 Telegram Job Mail Bot

A production-ready Telegram bot that automates sending job/internship
application emails. It validates an HR email address, generates several
professional email **subject line suggestions locally** (no external
AI API or API key required), displays them as inline keyboard buttons,
and sends the application email (with your resume attached) via
**Gmail SMTP** the instant you tap a subject.

Built with a **minimal file structure** on purpose — almost all logic
lives in `bot.py` — so the project is easy to read top-to-bottom, easy
to deploy, and easy to maintain without jumping between dozens of
modules.

---

## ✨ Features

- ✅ **Email validation** — rejects malformed or placeholder addresses before doing any work.
- ✏️ **Smart subject line suggestions** — 5–10 professional subject lines generated locally from curated templates (personalized with your name, target role, and the recruiter's company name derived from their email domain). No external API, no API key, no internet dependency for this step.
- 🔘 **Inline keyboard workflow** — tap a subject, and the email is sent instantly.
- 📎 **Automatic resume attachment** — `resume.pdf` is attached to every email.
- ✉️ **Predefined HTML email body** — polished, professional body with your applicant details filled in.
- 🗄️ **SQLite history tracking** — every sent email is logged locally.
- ⏳ **Duplicate-send protection** — configurable cooldown period prevents accidentally emailing the same recruiter twice in a short window (with an explicit "Send Anyway" override).
- 🪵 **Structured logging** — clear, timestamped logs for debugging and monitoring in production.
- 🛡️ **Comprehensive error handling** — invalid input and SMTP failures are all handled gracefully with user-friendly messages.
- ☁️ **Cloud-deploy ready** — runs via long-polling, so it works out of the box on Render, Railway, Koyeb, Fly.io, a VPS, or any host that can run a persistent Python process — no public webhook URL required.

---

## 🗂️ Project Structure

```
.
├── bot.py             # Telegram bot: handlers, inline keyboards, SQLite, workflow, logging
├── mailer.py          # SMTP email sending (HTML body + resume attachment)
├── ai_subject.py       # Local (no API key) subject-line suggestion generation
├── config.py           # Loads & validates all environment variables
├── resume.pdf          # Your resume, attached to every application email
├── requirements.txt     # Python dependencies
├── .env.example         # Template for required environment variables
├── .gitignore
└── README.md
```

That's it — no `handlers/`, `services/`, `models/`, or other subfolders.
The project is intentionally kept to a handful of files.

---

## ⚙️ Requirements

- Python **3.12+**
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Gmail account with a **Gmail App Password** (2-Step Verification must be enabled)

That's it — no third-party AI API key is needed anywhere in this project.

---

## 🚀 Local Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd <your-repo-directory>
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your resume**
   Replace the placeholder `resume.pdf` in the project root with your actual resume PDF (keep the filename `resume.pdf`, or set `RESUME_FILENAME` in `.env` to match a different filename).

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN`
   - `SMTP_EMAIL` and `SMTP_APP_PASSWORD` (Gmail App Password — **not** your normal Gmail password)
   - Your applicant details (`APPLICANT_NAME`, `APPLICANT_ROLE`, etc.)

6. **Run the bot**
   ```bash
   python bot.py
   ```
   You should see log output confirming the database was initialized and the bot is polling for updates. Open Telegram, find your bot, and send `/start`.

---

## 🔑 How to Get Each Credential

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

## 💬 Using the Bot

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
the cooldown window (`DUPLICATE_EMAIL_COOLDOWN_HOURS`, default 24 hours),
the bot will warn you and ask for explicit confirmation ("Send Anyway")
before sending again.

---

## ☁️ Deploying to the Cloud

This bot uses **long-polling**, so it does not require a public URL,
webhook, or open port — it just needs to run as a persistent background
process. This works on nearly any platform:

### Render / Railway / Koyeb (generic steps)
1. Push this repository to GitHub.
2. Create a new **Background Worker** (Render) or equivalent service on your platform.
3. Set the **Build Command**: `pip install -r requirements.txt`
4. Set the **Start Command**: `python bot.py`
5. Add all variables from `.env.example` as environment variables in your platform's dashboard (do **not** upload the `.env` file itself).
6. Deploy. Check the logs to confirm the bot connects and starts polling.

### Persisting the SQLite database
On most container-based platforms (Render, Railway, Koyeb), the local
filesystem is ephemeral across deploys/restarts unless you attach a
persistent disk/volume. If you need sent-email history to survive
redeploys, attach a persistent volume and point `DATABASE_FILENAME`
(via an absolute path) at a file inside that volume. For most use cases
(duplicate-prevention within a rolling cooldown window), the default
ephemeral behavior is acceptable.

---

## 🛠️ Configuration Reference

All configuration is controlled via environment variables (see
`.env.example` for the full list with descriptions), including:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather |
| `NUM_SUBJECT_SUGGESTIONS` | Number of subject suggestions to generate (5-10) |
| `SMTP_EMAIL` / `SMTP_APP_PASSWORD` | Gmail sending credentials |
| `APPLICANT_NAME`, `APPLICANT_ROLE`, etc. | Personalize the predefined email body & subject lines |
| `RESUME_FILENAME` | Resume PDF filename in the project root |
| `DUPLICATE_EMAIL_COOLDOWN_HOURS` | Cooldown period before re-emailing the same recipient |
| `ALLOWED_TELEGRAM_USER_IDS` | Optional comma-separated allow-list of Telegram user IDs |
| `LOG_LEVEL` | Logging verbosity |

---

## ✏️ How Subject Line Suggestions Work

`ai_subject.py` generates subject lines **entirely locally**, with no
network calls and no API key:

1. It derives a company name from the recipient's email domain (e.g.
   `hr@bright-solutions.com` → "Bright Solutions"). Generic providers
   like `gmail.com` are skipped since there's no real company to name.
2. It fills in a curated bank of professional subject-line templates
   using your `APPLICANT_NAME`, `APPLICANT_ROLE`, and (when available)
   the derived company name.
3. It shuffles and de-duplicates the results, returning the number of
   suggestions configured by `NUM_SUBJECT_SUGGESTIONS` (5–10).

This makes the bot fast, free, and 100% reliable — there's no external
service that can go down, rate-limit you, or require billing.

---

## 🧩 Tech Stack

- [`python-telegram-bot`](https://docs.python-telegram-bot.org/) v22+ (async, `Application`/`ContextTypes` API)
- `smtplib` (standard library) — Gmail SMTP over STARTTLS
- `sqlite3` (standard library) — history & cooldown tracking
- `python-dotenv` — environment variable loading

---

## ⚠️ Security Notes

- Never commit your `.env` file — it's excluded via `.gitignore`.
- Use a **Gmail App Password**, never your real account password.
- Consider setting `ALLOWED_TELEGRAM_USER_IDS` if you don't want strangers using your bot to send email on your behalf.

---

## 📄 License

Use, modify, and deploy freely for personal or commercial job-search automation.
