import smtplib
from app.config import settings
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Gmail SMTP 서버 정보
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# 계정 정보 (앱 비밀번호 사용)
SENDER_EMAIL = settings.email
SENDER_PASSWORD = settings.imap  # Gmail 앱 비밀번호 사용

# 수신자 이메일
RECIPIENT_EMAIL = settings.email


def encode_base64(data):
    return base64.b64encode(data).decode("utf-8")  # ✅ FastAPI가 아닌 `base64` 모듈 사용

def send_email_with_attachment(subject, body, attachment_path):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = subject

        # ✅ HTML 본문 추가
        msg.attach(MIMEText(body, "html"))

        # ✅ 파일 첨부
        with open(attachment_path, "rb") as file:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file.read())
            encoders.encode_base64(part)  # ✅ FastAPI가 아닌 email.encoders 사용
            part.add_header("Content-Disposition", f'attachment; filename="{attachment_path}"')
            msg.attach(part)

        # ✅ SMTP 서버 연결 및 이메일 전송
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()

        print(f"✅ 이메일이 {RECIPIENT_EMAIL}로 성공적으로 전송되었습니다.")
    except Exception as e:
        print(f"❌ 이메일 전송 실패: {e}")
