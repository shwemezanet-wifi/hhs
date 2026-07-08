import os
import sys
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import yt_dlp

sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Active")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

def download_and_send(chat_id, video_url):
    send_message(chat_id, "⏳ ဗီဒီယိုကို စစ်ဆေးပြီး ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    
    # ဖိုင်သိမ်းမည့် နာမည်သတ်မှတ်ခြင်း
    filename = f"video_{chat_id}_{int(time.time())}.mp4"
    
    # YouTube တံတိုင်းကျော်ရန် ပုံသေ Token များ သုံးစွဲခြင်း
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': filename, 
        'timeout': 60,
        'nocheckcertificate': True,
        'quiet': True,
        # YouTube Bot Block ကို ကျော်ဖြတ်ရန် တိုက်ရိုက်ခိုင်းစေချက်
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
            
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files={'video': f}, timeout=120)
            os.remove(filename)
        else:
            send_message(chat_id, "❌ ဗီဒီယိုကို ဒေါင်းလုဒ်ဆွဲမရပါ။ လင့်ခ် ပြန်စစ်ပေးပါ။")
            
    except Exception as e:
        print(f"Download Error: {e}", flush=True)
        send_message(chat_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")
        if os.path.exists(filename):
            os.remove(filename)

def bot_polling():
    print("🚀 BOT POLLING STARTED SUCCESSFULLY...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"]
                        if text.startswith('/start'):
                            send_message(chat_id, "👋 မင်္ဂလာပါ! ဗီဒီယို Link ပို့ပေးပါ။")
                        else:
                            threading.Thread(target=download_and_send, args=(chat_id, text)).start()
        except Exception as e:
            print(f"Network error: {e}", flush=True)
            time.sleep(5)

if __name__ == '__main__':
    try:
        requests.get(f"{BASE_URL}/deleteWebhook")
    except:
        pass
    
    threading.Thread(target=run_health_check, daemon=True).start()
    bot_polling()

