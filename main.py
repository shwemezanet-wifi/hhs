import os
import sys
import time
import asyncio
import threading
import json
import random
import string
import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
import yt_dlp

sys.stdout.reconfigure(line_buffering=True)

app = FastAPI()

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SERVER_URL = "https://hhs-zlhu.onrender.com" 

# 👑 လူကြီးမင်း၏ တရားဝင် Telegram Chat ID (လူကြီးမင်း တစ်ဦးတည်းသာ ကုဒ်ထုတ်နိုင်ရန်)
# သင့် Chat ID ကို မသိပါက ဘော့ထဲ /start ဟု ပို့လျှင် ၎င်း ID နံပါတ် ထွက်လာပါလိမ့်မည်။
ADMIN_ID = 123456789  # <--- မိမိ၏ Chat ID ဂဏန်းအမှန်ဖြင့် ဤနေရာတွင် အစားထိုးလဲလှယ်ပါ ⚠️

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

JSON_FILE = "codes.json"

# ဒေတာများကို ဖိုင်ဖြင့် သိမ်းဆည်း/ဖတ်ရှုသည့် စနစ်
def load_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    return {"active_codes": [], "premium_users": []}

def save_data(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.get("/")
@app.head("/")
def health_check():
    return {"status": "active", "message": "Bot Server is Running"}

@app.get("/get_file/{file_name}")
def get_file(file_name: str):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4", filename=file_name)
    return {"error": "File not found or expired"}

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
    except: pass

def auto_delete_file(file_path, delay=3600):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
    threading.Thread(target=delete, daemon=True).start()

# 🎬 ဒေါင်းလုဒ်လုပ်ငန်းစဉ်
def download_process(chat_id, video_url, quality):
    send_message(chat_id, f"⏳ {quality}p အရည်အသွေးဖြင့် ဗီဒီယိုကို စတင်ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    format_selector = f"best[height<={quality}][ext=mp4]/best[height<={quality}]/best"
    if quality == "360":
        format_selector = "best[height<=360][ext=mp4]/bestvideo[height<=360]+bestaudio/best"
        
    file_id = f"video_{chat_id}_{int(time.time())}.mp4"
    filename = os.path.join(DOWNLOAD_DIR, file_id)
    ydl_opts = {'format': format_selector, 'outtmpl': filename, 'timeout': 60, 'nocheckcertificate': True, 'quiet': True}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(filename):
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)
            if file_size_mb > 45:
                download_url = f"{SERVER_URL}/get_file/{file_id}"
                send_message(chat_id, f"📦 ဖိုင်ဆိုဒ် {file_size_mb:.2f} MB ရှိသဖြင့် Chrome မှ ဒေါင်းပါ-\n{download_url}\n\n⚠️ (၁ နာရီအတွင်းသာ ရပါမည်။)")
                auto_delete_file(filename, delay=3600)
            else:
                with open(filename, 'rb') as f:
                    requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files={'video': f}, timeout=120)
                os.remove(filename)
        else: send_message(chat_id, "❌ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲ၍ မရပါ။")
    except Exception as e:
        send_message(chat_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")
        if os.path.exists(filename): os.remove(filename)

# ယာယီ Pending မှတ်ရန် Memory DB
pending_db = {}

def bot_polling():
    print("🚀 WAY 2 PREMIUM BOT STARTED SUCCESSFULLY...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
                    # ၁။ Inline Keyboard နှိပ်ချက်များ စစ်ဆေးခြင်း
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        chat_id = cq["message"]["chat"]["id"]
                        cb_data = cq["data"]
                        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cq["id"]})
                        
                        parts = cb_data.split("|", 1)
                        quality = parts[0].replace("q_", "")
                        video_url = parts[1]
                        
                        data = load_data()
                        if quality == "360":
                            threading.Thread(target=download_process, args=(chat_id, video_url, 360)).start()
                        else:
                            if chat_id in data["premium_users"] or str(chat_id) in data["premium_users"]:
                                threading.Thread(target=download_process, args=(chat_id, video_url, int(quality))).start()
                            else:
                                pending_db[chat_id] = {"url": video_url, "quality": quality}
                                send_message(chat_id, f"🔒 {quality}p အသုံးပြုရန် Premium လိုင်စင်ကုဒ် လိုအပ်ပါသည်။\n\n🔑 ၎င်းကုဒ်ကို ဝယ်ယူရန် Admin ထံ ဆက်သွယ်ပါ။ ရရှိလာသော လိုင်စင်ကုဒ်ကို ဤနေရာတွင် တန်းရိုက်ထည့်ပေးပါ...")

                    # ၂။ ပုံမှန် စာသား သို့မဟုတ် လင့်ခ် စစ်ဆေးခြင်း
                    elif "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        
                        if text.startswith('/start'):
                            send_message(chat_id, f"👋 မင်္ဂလာပါ! ဗီဒီယိုလင့်ခ် ပို့ပေးပါ။\n(သင့် Chat ID: `{chat_id}`)")
                            
                        # 👑 ADMIN သီးသန့် ကုဒ်ထုတ်ပေးသည့်စနစ်
                        elif text == '/gen':
                            if chat_id == ADMIN_ID:
                                new_code = "VIP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                                db = load_data()
                                db["active_codes"].append(new_code)
                                save_data(db)
                                send_message(chat_id, f"🔑 လိုင်စင်ကုဒ် အသစ်ထွက်လာပါပြီ-\n\n`{new_code}`\n\n(ဝယ်ယူသူကို ဤကုဒ် ပေးလိုက်ပါ၊ သုံးပြီးလျှင် အလိုအလျောက် ပျက်ပြယ်ပါမည်။)")
                            else:
                                send_message(chat_id, "❌ သင်သည် Admin မဟုတ်သဖြင့် ကုဒ်ထုတ်ပိုင်ခွင့် မရှိပါ။")
                                
                        # အသုံးပြုသူက လိုင်စင်ကုဒ် လာရိုက်ထည့်ခြင်း စစ်ဆေးခြင်း
                        elif chat_id in pending_db and not (text.startswith("http://") or text.startswith("https://")):
                            db = load_data()
                            if text in db["active_codes"]:
                                db["active_codes"].remove(text) # ကုဒ်ကို ဖျက်ပစ်ခြင်း (တစ်ခါသုံး)
                                if chat_id not in db["premium_users"]:
                                    db["premium_users"].append(chat_id)
                                save_data(db)
                                
                                p_url = pending_db[chat_id]["url"]
                                p_qual = pending_db[chat_id]["quality"]
                                del pending_db[chat_id]
                                
                                send_message(chat_id, "✅ လိုင်စင်ကုဒ် အောင်မြင်ပါသည်။ သင်သည် ထာဝရ Premium Member ဖြစ်သွားပါပြီ။")
                                threading.Thread(target=download_process, args=(chat_id, p_url, int(p_qual))).start()
                            else:
                                send_message(chat_id, "❌ လိုင်စင်ကုဒ် မှားယွင်းနေပါသည် သို့မဟုတ် သုံးစွဲပြီးသားဖြစ်နေပါသည်။ ပြန်စစ်ပေးပါ။")
                                
                        # လင့်ခ်အသစ် ရောက်လာခြင်း
                        elif text.startswith("http://") or text.startswith("https://"):
                            menu = {
                                "inline_keyboard": [
                                    [{"text": "🎬 360p (Free)", "callback_data": f"q_360|{text}"}],
                                    [{"text": "⭐ 480p (Premium)", "callback_data": f"q_480|{text}"}],
                                    [{"text": "💎 720p (Premium)", "callback_data": f"q_720|{text}"}]
                                ]
                            }
                            send_message(chat_id, "⬇️ ဒေါင်းလုဒ်ဆွဲလိုသည့် ဗီဒီယို အရည်အသွေး (Quality) ကို ရွေးချယ်ပေးပါ-", reply_markup=menu)
        except Exception as e:
            print(f"Network error: {e}", flush=True)
            time.sleep(5)

def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_polling()

if __name__ == '__main__':
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
