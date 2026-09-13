"""
Email Service — Gmail SMTP for password reset emails.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import APP_BASE_URL, SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, token: str) -> bool:
    """
    Send a password reset email via Gmail SMTP.
    Returns True on success, False on failure.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured — cannot send reset email.")
        return False

    reset_url = f"{APP_BASE_URL}/auth/reset-password?token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your SmartRecruit password"
    msg["From"]    = f"SmartRecruit <{SMTP_EMAIL}>"
    msg["To"]      = to_email

    plain = f"""Hi,

You requested a password reset for your SmartRecruit account.

Click the link below to set a new password (valid for 1 hour):

{reset_url}

If you did not request this, you can safely ignore this email.
Your password will not change unless you click the link above.

— The SmartRecruit Team
"""

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f0fafa;padding:32px;margin:0">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;
              border:1px solid #b2e4de;padding:40px">
    <div style="text-align:center;margin-bottom:28px">
      <span style="display:inline-block;width:40px;height:40px;border-radius:10px;
                   background:linear-gradient(135deg,#14b8a6,#0d9488);
                   line-height:40px;text-align:center;font-size:20px">🔐</span>
      <h2 style="color:#0d2926;margin:12px 0 4px;font-size:20px">Reset your password</h2>
      <p style="color:#4d7a75;font-size:14px;margin:0">SmartRecruit Account</p>
    </div>

    <p style="color:#1e3a38;font-size:15px;line-height:1.6">
      We received a request to reset the password for your SmartRecruit account
      associated with <strong>{to_email}</strong>.
    </p>
    <p style="color:#1e3a38;font-size:15px;line-height:1.6">
      Click the button below to choose a new password. This link expires in
      <strong>1 hour</strong>.
    </p>

    <div style="text-align:center;margin:32px 0">
      <a href="{reset_url}"
         style="display:inline-block;background:#14b8a6;color:#ffffff;
                text-decoration:none;padding:14px 32px;border-radius:8px;
                font-weight:600;font-size:15px">
        Reset Password
      </a>
    </div>

    <p style="color:#4d7a75;font-size:13px;line-height:1.5">
      If the button doesn't work, copy and paste this URL into your browser:<br/>
      <a href="{reset_url}" style="color:#0d9488;word-break:break-all">{reset_url}</a>
    </p>

    <hr style="border:none;border-top:1px solid #b2e4de;margin:28px 0"/>
    <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0">
      If you didn't request a password reset, ignore this email — your password
      won't change.<br/>
      © 2026 SmartRecruit Platform
    </p>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        logger.info("Password reset email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send reset email to %s: %s", to_email, exc)
        return False
