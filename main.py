import os
import sys
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    
    try:
        # Telegram Bot များအတွက် အထူးပြုလုပ်ထားသော တည်ငြိမ်သည့် ဒေါင်းလုဒ် API
        api_url = f"https://co.wuk.sh/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": video_url,
            "vQuality": "720",
            "isAudioOnly": False
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30).json()
        
        if "url" in response:
            download_link = response["url"]
            
            # ဗီဒီယိုဖိုင်ကို API ထံမှ လှမ်းဆွဲခြင်း
            video_data = requests.get(download_link, timeout=60).content
            
            # Telegram သို့ တိုက်ရိုက် ပို့ဆောင်ခြင်း
            files = {'video': ('video.mp4', video_data, 'video/mp4')}
            requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files=files, timeout=90)
            
        elif response.get("status") == "error":
            send_message(chat_id, f"❌ ဒေါင်းလုဒ်လုပ်၍မရပါ။ အကြောင်းရင်း: {response.get('text', 'လင့်ခ်မှားယွင်းနေပါသည်')}")
        else:
            send_message(chat_id, "❌ ဗီဒီယိုကို ရှာမတွေ့ပါ။ လင့်ခ်အမှန် ဖြစ်ရပါမည်။")
            
    except Exception as e:
        print(f"API Error: {e}", flush=True)
        send_message(chat_id, "❌ ဆာဗာမှ တုံ့ပြန်မှု မရှိပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")

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
