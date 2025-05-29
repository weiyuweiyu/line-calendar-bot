from flask import Flask, request, redirect
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, json, datetime, base64

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = Flask(__name__)

# 將 credentials.json 從環境變數還原出來
base64_creds = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
if base64_creds:
    with open("credentials.json", "wb") as f:
        f.write(base64.b64decode(base64_creds))

# LINE 設定
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

# 暫存使用者授權資訊（正式版可改為 Firebase）
user_tokens = {}

@app.route("/")
def index():
    return "LINE Bot with Google Calendar is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'

@app.route("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/calendar.readonly'],
        redirect_uri='https://line-calendar-bot-9ua3.onrender.com/oauth2callback'
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # 將使用者憑證儲存起來（這裡固定成 default_user）
    user_tokens["default_user"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    return "✅ Google Calendar 授權成功！你可以回到 LINE 詢問『今天行程』囉。"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    if text == "今天行程":
        user_data = user_tokens.get("default_user")
        if not user_data:
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=['https://www.googleapis.com/auth/calendar.readonly'],
                redirect_uri='https://line-calendar-bot-9ua3.onrender.com/oauth2callback'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            reply = f"請先授權 Google 日曆使用權限：\n{auth_url}"
        else:
            creds = Credentials(**user_data)
            service = build('calendar', 'v3', credentials=creds)

            now = datetime.datetime.utcnow().isoformat() + 'Z'
            end = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat() + 'Z'
            events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=end,
                                                  maxResults=5, singleEvents=True,
                                                  orderBy='startTime').execute()
            events = events_result.get('items', [])

            if not events:
                reply = "今天沒有行程喔 📭"
            else:
                reply = "📅 你今天的行程：\n"
                for e in events:
                    start = e['start'].get('dateTime', e['start'].get('date'))
                    reply += f"- {e['summary']} @ {start}\n"
    else:
        reply = "輸入『今天行程』我會幫你查 Google Calendar！"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


