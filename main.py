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
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True)

app = FastAPI()

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SERVER_URL = "https://hhs-zlhu.onrender.com" 

ADMIN_IDS = [8391123176, 573829102]  # <--- အက်ဒမင်နှင့် အေးဂျင့် ID များ

DEFAULT_AD = "📢 <b>[ကြော်ငြာ]</b> မြန်မာနိုင်ငံ၏ ယုံကြည်စိတ်ချရဆုံး အွန်လိုင်းစျေးဝယ်ပလက်ဖောင်းကို အသုံးပြုရန် ဤနေရာကိုနှိပ်ပါ"

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

JSON_FILE = "codes.json"

def load_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            try:
                data = json.load(f)
                if "current_ad" not in data: data["current_ad"] = DEFAULT_AD
                if "all_users" not in data: data["all_users"] = []
                if "premium_users" not in data: data["premium_users"] = {} # dict ပုံစံပြောင်းသည် {str(chat_id): expire_timestamp}
                if "active_codes" not in data: data["active_codes"] = {} # dict ပုံစံပြောင်းသည် {code: duration_type}
                return data
            except: pass
    return {"active_codes": {}, "premium_users": {}, "all_users": [], "current_ad": DEFAULT_AD}

def save_data(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def is_premium(chat_id):
    db = load_data()
    premiums = db.get("premium_users", {})
    uid = str(chat_id)
    if uid in premiums:
        expire_time = premiums[uid]
        if time.time() < expire_time:
            return True, expire_time
    return False, 0

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
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
    except: pass

def auto_delete_file(file_path, delay=3600):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path): os.remove(file_path)
    threading.Thread(target=delete, daemon=True).start()

def get_video_duration(video_url):
    ydl_opts = {'quiet': True, 'nocheckcertificate': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('duration', 0)
    except: return 0

def download_process(chat_id, video_url, is_prem_user):
    quality_text = "720p (HD)" if is_prem_user else "240p (Free)"
    send_message(chat_id, f"⏳ သင်သည် {quality_text} ဖြင့် ဗီဒီယိုကို စတင်ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    
    if is_prem_user:
        format_selector = "bestvideo[height<=720]+bestaudio/best"
    else:
        format_selector = "worst/worstvideo+worstaudio/best[height<=240]"
        
    file_id = f"video_{chat_id}_{int(time.time())}.mp4"
    filename = os.path.join(DOWNLOAD_DIR, file_id)
    
    ydl_opts = {
        'format': format_selector,
        'outtmpl': filename,
        'timeout': 60,
        'nocheckcertificate': True,
        'quiet': True,
        'merge_output_format': 'mp4'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(filename):
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)
            db = load_data()
            ad_text = db.get("current_ad", DEFAULT_AD)
            
            if file_size_mb > 45:
                download_url = f"{SERVER_URL}/get_file/{file_id}"
                send_message(chat_id, f"📦 ဖိုင်ဆိုဒ် {file_size_mb:.2f} MB ရှိသဖြင့် Chrome မှ ဒေါင်းပါ-\n{download_url}\n\n⚠️ (၁ နာရီအတွင်းသာ ရပါမည်။)\n\n{ad_text}")
                auto_delete_file(filename, delay=3600)
            else:
                with open(filename, 'rb') as f:
                    requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id, 'caption': ad_text, 'parse_mode': 'HTML'}, files={'video': f}, timeout=120)
                os.remove(filename)
        else: send_message(chat_id, "❌ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲ၍ မရပါ။ လင့်ခ်မှားယွင်းနေခြင်း ဖြစ်နိုင်ပါသည်။")
    except Exception as e:
        send_message(chat_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")
        if os.path.exists(filename): os.remove(filename)

def broadcast_forward_process(admin_id, from_chat_id, message_id):
    db = load_data()
    users = db.get("all_users", [])
    send_message(admin_id, f"⏳ မီဒီယာကြော်ငြာကို User <code>{len(users)}</code> ဦးထံ စတင် Forward လုပ်နေပါပြီ...")
    success_count = 0
    for u_id in users:
        try:
            payload = {"chat_id": int(u_id), "from_chat_id": from_chat_id, "message_id": message_id}
            res = requests.post(f"{BASE_URL}/forwardMessage", json=payload, timeout=5).json()
            if res.get("ok"): success_count += 1
            time.sleep(0.1)
        except: pass
    send_message(admin_id, f"✅ ကြော်ငြာ ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\n📊 အောင်မြင်မှု: <code>{success_count}</code> ဦး")

def bot_polling():
    print("🚀 SUBSCRIPTION & AUTO-QUALITY BOT ACTIVE...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg_data = update["message"]
                        chat_id = msg_data["chat"]["id"]
                        message_id = msg_data["message_id"]
                        
                        db = load_data()
                        if chat_id not in db["all_users"] and str(chat_id) not in db["all_users"]:
                            db["all_users"].append(chat_id)
                            save_data(db)

                        # Admin Forward Ads
                        if chat_id in ADMIN_IDS and ("video" in msg_data or "audio" in msg_data or "voice" in msg_data or "animation" in msg_data or ("photo" in msg_data and "reply_to_message" not in msg_data)):
                            threading.Thread(target=broadcast_forward_process, args=(chat_id, chat_id, message_id)).start()
                            continue

                        # User Screenshot
                        if "photo" in msg_data and chat_id not in ADMIN_IDS:
                            file_id = msg_data["photo"][-1]["file_id"]
                            for current_admin in ADMIN_IDS:
                                payload = {"chat_id": current_admin, "photo": file_id, "caption": f"📩 <b>User ထံမှ စလစ် ရောက်လာပါသည်-</b>\n• Chat ID: <code>{chat_id}</code>\n\n<i>မှတ်ချက်- ပရီမီယမ်သက်တမ်းတိုးရန် ဤ User အတွက် /gen ကိုသုံး၍ ကုဒ်ထုတ်ပေးလိုက်ပါဗျာ။</i>", "parse_mode": "HTML"}
                                requests.post(f"{BASE_URL}/sendPhoto", json=payload)
                            send_message(chat_id, "📥 သင်၏ ငွေလွှဲစလစ်ပုံကို လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီး ပရီမီယမ်ကုဒ် လာပေးပါလိမ့်မည်။ ခေတ္တစောင့်ဆိုင်းပေးပါဦးဗျာ...")
                            continue

                        if "text" in msg_data:
                            text = msg_data["text"].strip()
                            
                            # 🔑 1. အက်ဒမင်များ ပရီမီယမ်ကုဒ် ထုတ်သည့်စနစ် (/gen week, /gen month, /gen year)
                            if chat_id in ADMIN_IDS and text.startswith("/gen"):
                                parts = text.split()
                                if len(parts) < 2 or parts[1].lower() not in ["week", "month", "year"]:
                                    send_message(chat_id, "❌ ပုံစံမှားနေပါသည်။ အောက်ပါအတိုင်း ရိုက်ပါ-\n• <code>/gen week</code>\n• <code>/gen month</code>\n• <code>/gen year</code>")
                                    continue
                                
                                duration_type = parts[1].lower()
                                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                                generated_code = f"PREM-{duration_type.upper()}-{random_str}"
                                
                                db = load_data()
                                db["active_codes"][generated_code] = duration_type
                                save_data(db)
                                
                                send_message(chat_id, f"✅ <b>ပရီမီယမ်ကုဒ် အောင်မြင်စွာထုတ်ပြီးပါပြီ!</b>\n\n🎫 ကုဒ်: <code>{generated_code}</code>\n⏱️ သက်တမ်းအမျိုးအစား: <b>{duration_type.upper()}</b>\n\n👉 ဤကုဒ်ကို ကော်ပီယူပြီး အသုံးပြုသူထံ လက်ဆောင်ပေးလိုက်ပါဗျာ။")
                                continue

                            # 🎁 2. အသုံးပြုသူများ ကုဒ်ပြန်လည်အသုံးပြုသည့်စနစ် (/redeem [ကုဒ်])
                            if text.startswith("/redeem "):
                                user_code = text.replace("/redeem ", "", 1).strip()
                                db = load_data()
                                
                                if user_code in db.get("active_codes", {}):
                                    dtype = db["active_codes"][user_code]
                                    
                                    # သက်တမ်းတွက်ချက်ခြင်း
                                    now = time.time()
                                    current_prem, current_expire = is_premium(chat_id)
                                    base_time = current_expire if current_prem else now
                                    
                                    if dtype == "week": add_seconds = 7 * 24 * 60 * 60
                                    elif dtype == "month": add_seconds = 30 * 24 * 60 * 60
                                    else: add_seconds = 365 * 24 * 60 * 60
                                    
                                    new_expire = base_time + add_seconds
                                    db["premium_users"][str(chat_id)] = new_expire
                                    del db["active_codes"][user_code] # သုံးပြီးသားကုဒ်ဖျက်သည်
                                    save_data(db)
                                    
                                    expire_date = datetime.fromtimestamp(new_expire).strftime('%Y-%m-%d %H:%M:%S')
                                    send_message(chat_id, f"🎉 <b>ကုဒ်အသုံးပြုမှု အောင်မြင်ပါသည်!</b>\n\n💎 သင်၏အကောင့်သည် <b>{dtype.upper()}</b> ပရီမီယမ်အဖြစ်သို့ ရောက်ရှိသွားပါပြီ။\n📅 သက်တမ်းကုန်ဆုံးမည့်ရက်: <code>{expire_date}</code>\n🚀 ယခုမှစ၍ မိနစ်အရှည်ကြီးများနှင့် HD ဗီဒီယိုများကို ခလုတ်နှိပ်စရာမလိုဘဲ တိုက်ရိုက်ဒေါင်းနိုင်ပါပြီဗျာ။")
                                else:
                                    send_message(chat_id, "❌ သင်ရိုက်ထည့်လိုက်သော ကုဒ် မမှန်ကန်ပါ သို့မဟုတ် အသုံးပြုပြီးသားဖြစ်နေပါသည်။")
                                continue

                            # Admin /setad
                            if chat_id in ADMIN_IDS and text.startswith("/setad "):
                                new_ad = text.replace("/setad ", "", 1)
                                if new_ad:
                                    db = load_data()
                                    db["current_ad"] = new_ad
                                    save_data(db)
                                    send_message(chat_id, f"✅ <b>Inline Ad ပြောင်းလဲပြီးပါပြီ!</b>")
                                continue

                            # Admin /ad
                            if chat_id in ADMIN_IDS and text.startswith("/ad "):
                                ad_content = text.replace("/ad ", "", 1)
                                if ad_content:
                                    threading.Thread(target=broadcast_forward_process, args=(chat_id, chat_id, message_id)).start()
                                continue

                            if text.startswith('/start'):
                                welcome_msg = (
                                    f"👋 <b>Video Downloader ဘော့မှ ကြိုဆိုပါသည်!</b>\n\n"
                                    f"Facebook နှင့် TikTok ဗီဒီယိုလင့်ခ်များကို ပို့ပေးရုံဖြင့် တိုက်ရိုက်ဒေါင်းလုဒ်ဆွဲနိုင်ပါသည်။\n\n"
                                    f"🎫 <b>ပရီမီယမ်ကုဒ်ရှိပါက -</b> <code>/redeem မိမိကုဒ်</code> ဟုရိုက်ထည့်ပါ။\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🎬 Free သမားများ: (၅) မိနစ်အောက် ဗီဒီယိုကို 240p ဖြင့် ရမည်။\n"
                                    f"💎 Premium သမားများ: ဗီဒီယိုအရှည်ကြီးများကို 720p HD ဖြင့် ရမည်။\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"🚀 ဗီဒီယိုလင့်ခ်ကို ဤနေရာတွင် တန်းပို့ပေးလိုက်ပါဗျာ..."
                                )
                                send_message(chat_id, welcome_msg)
                                continue
                                
                            elif text == '/usercount' and chat_id in ADMIN_IDS:
                                db = load_data()
                                total = len(db.get("all_users", []))
                                prem_count = sum(1 for uid, exp in db.get("premium_users", {}).items() if time.time() < exp)
                                send_message(chat_id, f"📊 <b>ဘော့အခြေအနေ:</b>\n\n• စုစုပေါင်းအသုံးပြုသူ: <code>{total}</code> ဦး\n• လက်ရှိ Premium အသုံးပြုသူ: <code>{prem_count}</code> ဦး")
                                continue

                            # 🎬 3. ဗီဒီယိုလင့်ခ် ပို့လိုက်လျှင် အော်တို ဒေါင်းလုဒ်ဆွဲပေးသည့်စနစ်
                            elif text.startswith("http://") or text.startswith("https://"):
                                prem_status, expire_timestamp = is_premium(chat_id)
                                
                                if not prem_status: # Free သမားဆိုလျှင် ၅ မိနစ်ကျော်ကန့်သတ်ချက်စစ်မည်
                                    duration = get_video_duration(text)
                                    if duration > 300:
                                        msg = (
                                            f"⚠️ <b>Free ဗားရှင်းတွင် (၅) မိနစ်အောက် ဗီဒီယိုများကိုသာ ခွင့်ပြုပါသည်။</b>\n\n"
                                            f"💎 သက်တမ်းအလိုက် ပရီမီယမ်ဝယ်ယူရန် Ngwe လွှဲပေးပါဦးဗျာ။\n"
                                            f"• KPay နံပါတ်: <code>09123456789</code> (U Mya)\n"
                                            f"• ၁ ပတ် - ၃၀၀၀ ကျပ် | ၁ လ - ၅၀၀၀ ကျပ် | ၁ နှစ်စာ ၄၀၀၀၀ ကျပ်\n\n"
                                            f"👉 Ngwe လွှဲပြီး စလစ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။ Admin မှ ပရီမီယမ်ကုဒ် ပေးပါလိမ့်မည်။"
                                        )
                                        send_message(chat_id, msg)
                                        continue
                                
                                # ကွာလတီရွေးခိုင်းခြင်းမရှိတော့ဘဲ တိုက်ရိုက်ဒေါင်းလုပ်ဆွဲပေးမည်
                                threading.Thread(target=download_process, args=(chat_id, text, prem_status)).start()

        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    threading.Thread(target=bot_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
