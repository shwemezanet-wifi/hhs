import os
import sys
import time
import asyncio
import threading
import requests
from fastapi import FastAPI
import uvicorn

sys.stdout.reconfigure(line_buffering=True)

# FastAPI တည်ဆောက်ခြင်း (Render ပုံမှန်နိုးကြားစေရန်)
app = FastAPI()

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.get("/")
def health_check():
    return {"status": "active", "message": "Bot Server is Running"}

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

def download_and_send(chat_id, video_url):
    send_message(chat_id, "⏳ ဗီဒီယိုကို စစ်ဆေးပြီး ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    
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
        except:
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

# Bot Polling ကို Background မှာ ပတ်ခိုင်းထားခြင်း
def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_polling()

if __name__ == '__main__':
    try:
        requests.get(f"{BASE_URL}/deleteWebhook")
    except:
        pass
    
    # Bot ကို Thread တစ်ခုခွဲပြီး မောင်းနှင်ခြင်း
    threading.Thread(target=start_bot, daemon=True).start()
    
    # Render အတွက် Web Server မောင်းနှင်ခြင်း
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
