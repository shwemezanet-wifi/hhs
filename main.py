import os
import sys
import time
import asyncio
import threading
import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
import yt_dlp

sys.stdout.reconfigure(line_buffering=True)

app = FastAPI()

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
# သင့် Render ဆာဗာ၏ လင့်ခ်အမှန်
SERVER_URL = "https://hhs-zlhu.onrender.com" 

# ဒေါင်းလုဒ်လုပ်ထားသော ဗီဒီယိုဖိုင်ကြီးများကို သိမ်းဆည်းရန် Folder
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@app.get("/")
@app.head("/")
def health_check():
    return {"status": "active", "message": "Bot Server is Running"}

# ဖိုင်ဆိုဒ်ကြီးမားသော ဗီဒီယိုများကို လင့်ခ်ဖြင့် ဒေါင်းလုဒ်ပေးရန် Endpoint
@app.get("/get_file/{file_name}")
def get_file(file_name: str):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4", filename=file_name)
    return {"error": "File not found or expired"}

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

# သိမ်းဆည်းထားသော ဗီဒီယိုများကို ၁ နာရီပြည့်ပါက ဆာဗာနေရာလွတ်စေရန် အလိုအလျောက်ဖျက်သည့်စနစ်
def auto_delete_file(file_path, delay=3600):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🕒 Auto deleted expired file: {file_path}", flush=True)
    threading.Thread(target=delete, daemon=True).start()

def download_and_send(chat_id, video_url):
    send_message(chat_id, "⏳ ဗီဒီယိုကို စစ်ဆေးပြီး ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    
    # ၁။ YouTube ဖြစ်ပါက API အရန်လမ်းကြောင်းများဖြင့် ကျော်ဒေါင်းခြင်း
    if "youtube.com" in video_url or "youtu.be" in video_url:
        api_endpoints = [
            "https://cobalt.api.unblockit.pro/api/json",
            "https://api.cobalt.tools/api/json",
            "https://cobalt-api.kwiatew.eu/api/json"
        ]
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"url": video_url, "vQuality": "720"}
        
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
            send_message(chat_id, "❌ YouTube ဒေါင်းလုဒ်ဆွဲရန် API များ ယာယီ မအားသေးပါ။ ခေတ္တစောင့်ပြီး ပြန်စမ်းပါ။")

    # ၂။ Facebook သို့မဟုတ် TikTok ဖြစ်ပါက ဆာဗာမှ တိုက်ရိုက် (yt-dlp) စနစ်ဖြင့် ဒေါင်းခြင်း
    else:
        file_id = f"video_{chat_id}_{int(time.time())}.mp4"
        filename = os.path.join(DOWNLOAD_DIR, file_id)
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': filename,
            'timeout': 60,
            'nocheckcertificate': True,
            'quiet': True
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            if os.path.exists(filename):
                file_size_mb = os.path.getsize(filename) / (1024 * 1024)
                
                # ဖိုင်ဆိုဒ် 45MB ထက်ကြီးပါက Telegram API limit ကိုကျော်လွှားရန် Direct Link ပေးခြင်း
                if file_size_mb > 45:
                    download_url = f"{SERVER_URL}/get_file/{file_id}"
                    msg = (
                        f"📦 ဗီဒီယိုဖိုင်ဆိုဒ်သည် Telegram ကန့်သတ်ချက်ထက်ကျော်လွန်ပြီး {file_size_mb:.2f} MB ရှိနေပါသည်။\n\n"
                        f"👇 အောက်ပါလင့်ခ်ကို နှိပ်ပြီး Chrome Browser မှတစ်ဆင့် အရှိန်အပြည့်ဖြင့် ဒေါင်းလုဒ်ဆွဲနိုင်ပါပြီ-\n"
                        f"{download_url}\n\n"
                        f"⚠️ (မှတ်ချက်။ ။ ဤလင့်ခ်သည် ၁ နာရီအတွင်းသာ အလုပ်လုပ်မည်ဖြစ်ပြီး ပြီးပါက ဆာဗာမှ Auto ပျက်သွားပါမည်။)"
                    )
                    send_message(chat_id, msg)
                    auto_delete_file(filename, delay=3600) # ၁ နာရီကြာလျှင် ဖျက်ရန်
                else:
                    with open(filename, 'rb') as f:
                        requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files={'video': f}, timeout=120)
                    os.remove(filename)
            else:
                send_message(chat_id, "❌ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲ၍ မရပါ။ လင့်ခ်မှားယွင်းနေနိုင်ပါသည်။")
        except Exception as e:
            print(f"Direct Download Error: {e}", flush=True)
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

def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_polling()

if __name__ == '__main__':
    try:
        requests.get(f"{BASE_URL}/deleteWebhook")
    except:
        pass
    
    threading.Thread(target=start_bot, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
