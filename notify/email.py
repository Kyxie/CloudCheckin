import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def info(msg: str) -> None:
    print(msg, flush=True)


def send_error_mail(subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    mail_from = os.environ.get("MAIL_FROM", "").strip() or user
    mail_to = os.environ.get("MAIL_TO", "").strip()
    tls_mode = os.environ.get("SMTP_TLS", "starttls").strip().lower()

    if not host or not mail_from or not mail_to:
        print(
            "SMTP not configured (SMTP_HOST / MAIL_FROM / MAIL_TO missing); "
            f"skipping error mail. Subject was: {subject}",
            file=sys.stderr,
            flush=True,
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = mail_to
    message.set_content(body)

    try:
        if tls_mode == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(message)
        elif tls_mode == "none":
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(message)
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls(context=context)
                if user:
                    smtp.login(user, password)
                smtp.send_message(message)
    except Exception as exc:
        print(
            f"Failed to send error mail (subject={subject!r}): {exc}",
            file=sys.stderr,
            flush=True,
        )
