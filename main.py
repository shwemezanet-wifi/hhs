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
    
    # အမြဲတမ်း Update ဖြစ်နေပြီး ပိတ်မသွားနိုင်သော Cobalt Public API များစာရင်း
    api_endpoints = [
        "https://cobalt.api.unblockit.pro/api/json",
        "https://api.cobalt.tools/api/json",
        "https://cobalt-api.kwiatew.eu/api/json"
    ]
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": video_url,
        "vQuality": "720"
    }
    
    success = False
    
    # ဆာဗာတစ်ခု ပျက်နေပါက နောက်တစ်ခုသို့ Auto ပြောင်းလဲစမ်းသပ်သည့်စနစ်
    for api_url in api_endpoints:
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=15).json()
            if response.get("status") in ["stream", "picker"]:
                download_link = response.get("url")
                video_data = requests.get(download_link, timeout=60).content
                files = {'video': ('video.mp4', video_data, 'video/mp4')}
                requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files=files, timeout=90)
                success = True
                break
        except Exception as e:
            print(f"Failed endpoint {api_url}: {e}", flush=True)
            continue
            
    if not success:
        send_message(chat_id, "❌ ဗီဒီယိုကို ဒေါင်းလုဒ်ဆွဲ၍မရပါ။ လင့်ခ်မှားယွင်းနေခြင်း သို့မဟုတ် ဆာဗာများ အားလုံးမအားသေးခြင်း ဖြစ်နိုင်ပါသည်။")

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
