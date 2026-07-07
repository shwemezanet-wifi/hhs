import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import yt_dlp

BOT_TOKEN = "8887542224:AAFEfEvHKlH09TBx0nAjuGZ2kOrDy_l_7Ss"
BASE_URL = f"https://api.telegram-proxy.org/bot{BOT_TOKEN}"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_message(chat_id, text):
    try: requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15)
    except: pass

def download_and_send(chat_id, video_url):
    send_message(chat_id, "⏳ ဗီဒီယိုကို စစ်ဆေးပြီး ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    try:
        ydl_opts = {'format': 'best', 'outtmpl': 'video.%(ext)s', 'timeout': 60}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        with open(filename, 'rb') as f:
            requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files={'video': f}, timeout=100)
        if os.path.exists(filename): os.remove(filename)
    except:
        send_message(chat_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။")

def bot_polling():
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    offset = 0
    while True:
        try:
            response = requests.get(f"{BASE_URL}/getUpdates?offset={offset}&timeout=20", timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"]
                        if text.startswith('/start'):
                            send_message(chat_id, "👋 ဗီဒီယို Link ပို့ပေးပါ။")
                        else:
                            threading.Thread(target=download_and_send, args=(chat_id, text)).start()
        except: time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_health_check, daemon=True).start()
    bot_polling()
