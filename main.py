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

ADMIN_ID = 8391123176  # <--- သင့် Chat ID
ADMIN_USERNAME = "heinmezatg" # <--- သင့် Username (@ မပါဘဲ)

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
                if "current_ad" not in data:
                    data["current_ad"] = DEFAULT_AD
                return data
            except:
                pass
    return {"active_codes": [], "premium_users": [], "all_users": [], "current_ad": DEFAULT_AD}

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
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
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

def get_video_duration(video_url):
    ydl_opts = {'quiet': True, 'nocheckcertificate': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('duration', 0)
    except:
        return 0

def download_process(chat_id, video_url, quality):
    send_message(chat_id, f"⏳ {quality}p အရည်အသွေးဖြင့် ဗီဒီယိုကို စတင်ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
    
    if quality == 240:
        format_selector = "worst/worstvideo+worstaudio/best[height<=240]"
    elif quality == 480:
        format_selector = "best[height<=480]/bestvideo[height<=480]+bestaudio/best"
    else:
        format_selector = "bestvideo[height<=720]+bestaudio/best"
        
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
            if file_size_mb > 45:
                download_url = f"{SERVER_URL}/get_file/{file_id}"
                send_message(chat_id, f"📦 ဖိုင်ဆိုဒ် {file_size_mb:.2f} MB ရှိသဖြင့် Chrome မှ ဒေါင်းပါ-\n{download_url}\n\n⚠️ (၁ နာရီအတွင်းသာ ရပါမည်။)")
                auto_delete_file(filename, delay=3600)
            else:
                with open(filename, 'rb') as f:
                    requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id}, files={'video': f}, timeout=120)
                os.remove(filename)
        else: send_message(chat_id, "❌ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲ၍ မရပါ။ လင့်ခ်မှားယွင်းခြင်း သို့မဟုတ် မူရင်းဗီဒီယိုတွင် ဤကွာလတီမရှိခြင်း ဖြစ်နိုင်ပါသည်။")
    except Exception as e:
        send_message(chat_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")
        if os.path.exists(filename): os.remove(filename)

pending_db = {}

# 📢 ဗီဒီယို/ဓာတ်ပုံ/အသံဖိုင်များပါ အစုလိုက် Forward လုပ်ပြီး ပို့ပေးမည့် စနစ်သစ်
def broadcast_forward_process(admin_id, from_chat_id, message_id):
    db = load_data()
    users = db.get("all_users", [])
    send_message(admin_id, f"⏳ မီဒီယာကြော်ငြာ (Video/Photo/Audio) ကို User <code>{len(users)}</code> ဦးထံ စတင် Forward လုပ်နေပါပြီ...")
    
    success_count = 0
    for u_id in users:
        try:
            payload = {
                "chat_id": int(u_id),
                "from_chat_id": from_chat_id,
                "message_id": message_id
            }
            res = requests.post(f"{BASE_URL}/forwardMessage", json=payload, timeout=5).json()
            if res.get("ok"):
                success_count += 1
            time.sleep(0.1) # API Limit မမိအောင် ထိန်းခြင်း
        except:
            pass
            
    send_message(admin_id, f"✅ မီဒီယာကြော်ငြာ ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\n📊 အောင်မြင်မှု: <code>{success_count}</code> ဦး")

def bot_polling():
    print("🚀 MULTIMEDIA ADS BOT ACTIVE...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        chat_id = cq["message"]["chat"]["id"]
                        cb_data = cq["data"]
                        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cq["id"]})
                        
                        if cb_data.startswith("approve_"):
                            target_user = cb_data.replace("approve_", "")
                            db = load_data()
                            if target_user not in db["premium_users"] and int(target_user) not in db["premium_users"]:
                                db["premium_users"].append(int(target_user))
                                save_data(db)
                            
                            send_message(ADMIN_ID, f"✅ User <code>{target_user}</code> အား Premium ဖွင့်ပေးလိုက်ပါပြီ။")
                            send_message(int(target_user), "🎉 <b>ဂုဏ်ယူပါသည်!</b> Admin မှ သင်၏ငွေလွှဲမှုကို အတည်ပြုပြီး Premium Member အဖြစ် ထာဝရ သတ်မှတ်ပေးလိုက်ပါပြီ။\n🚀 ယခုမှစ၍ ဗီဒီယိုအရှည်ကြီးများနှင့် 480p/720p HD ဗီဒီယိုများကို စိတ်ကြိုက် ဒေါင်းလုဒ်ဆွဲနိုင်ပါပြီဗျာ။")
                            if int(target_user) in pending_db:
                                p_url = pending_db[int(target_user)]["url"]
                                p_qual = pending_db[int(target_user)]["quality"]
                                del pending_db[int(target_user)]
                                threading.Thread(target=download_process, args=(int(target_user), p_url, int(p_qual))).start()
                            continue

                        parts = cb_data.split("|", 1)
                        quality = parts[0].replace("q_", "")
                        video_url = parts[1]
                        
                        data = load_data()
                        if quality == "240":
                            duration = get_video_duration(video_url)
                            if duration > 300:
                                msg = (
                                    f"⚠️ <b>ခွင့်မပြုပါ!</b>\n\n"
                                    f"Free ဗားရှင်းတွင် မိနစ်တို ဗီဒီယိုများကိုသာ ဒေါင်းလုဒ်ဆွဲခွင့်ရှိပါသည်ဗျာ။\n"
                                    f"ယခုဗီဒီယိုသည် ကြာချိန် {int(duration/60)} မိနစ် ရှိနေသဖြင့် Premium အဖွဲ့ဝင်များသာ ဒေါင်းလုဒ်ဆွဲနိုင်ပါသည်။\n\n"
                                    f"💎 Premium အဖွဲ့ဝင်ဝင်ရန် အောက်ပါ ညွှန်ကြားချက်အတိုင်း ငွေ လွှဲပေးပါဦးဗျာ။"
                                )
                                send_message(chat_id, msg)
                                
                                pending_db[chat_id] = {"url": video_url, "quality": "480"}
                                kpay_msg = (
                                    f"💰 <b>ငွေပေးချေရန် KPay အချက်အလက် -</b>\n"
                                    f"• KPay နံပါတ်: <code>09784732943</code>\n"
                                    f"• အကောင့်နာမည်: <code>U Tun Tun Latt</code>\n"
                                    f"• ကျသင့်ငွေ: <code>10000</code> ကျပ်\n\n"
                                    f"👉 ကျေးဇူးပြု၍ အထက်ပါအကောင့်သို့ ငွေလွှဲပြီးနောက် ရရှိလာသော <b>ငွေလွှဲစလစ် (Screenshot) ပုံကို</b> ဤ bot ထဲသို့ တိုက်ရိုက် ပို့ပေးလိုက်ပါဗျာ။\n"
                                    f"Admin မှ စက္ကန့်ပိုင်းအတွင်း အတည်ပြုပြီး Premium ဖွင့်ပေးပါလိမ့်မည်။"
                                )
                                send_message(chat_id, kpay_msg)
                            else:
                                threading.Thread(target=download_process, args=(chat_id, video_url, 240)).start()
                        else:
                            if chat_id in data["premium_users"] or str(chat_id) in data["premium_users"]:
                                threading.Thread(target=download_process, args=(chat_id, video_url, int(quality))).start()
                            else:
                                pending_db[chat_id] = {"url": video_url, "quality": quality}
                                kpay_msg = (
                                    f"💰 <b>ငွေပေးချေရန် KPay အချက်အလက် -</b>\n"
                                    f"• KPay နံပါတ်: <code>09784732943</code>\n"
                                    f"• အကောင့်နာမည်: <code>U Tun Tun Latt</code>\n"
                                    f"• ကျသင့်ငွေ: <code>10000</code> ကျပ်\n\n"
                                    f"👉 ကျေးဇူးပြု၍ အထက်ပါအကောင့်သို့ Ngwe လွှဲပြီးနောက် ရရှိလာသော <b>ငွေလွှဲစလစ် (Screenshot) ပုံကို</b> ဤဘော့ထဲသို့ တိုက်ရိုက် ပို့ပေးလိုက်ပါဗျာ။\n"
                                    f"Admin မှ စက္ကန့်ပိုင်းအတွင်း အတည်ပြုပြီး Premium ဖွင့်ပေးပါလိမ့်မည်။"
                                )
                                send_message(chat_id, kpay_msg)

                    elif "message" in update:
                        msg_data = update["message"]
                        chat_id = msg_data["chat"]["id"]
                        message_id = msg_data["message_id"]
                        
                        db = load_data()
                        if "all_users" not in db: db["all_users"] = []
                        if chat_id not in db["all_users"] and str(chat_id) not in db["all_users"]:
                            db["all_users"].append(chat_id)
                            save_data(db)

                        # 🔒 Admin ဆီကနေ Video/Audio/Photo ကြော်ငြာတွေ Forward လုပ်လာရင် အစုလိုက် ပြန်ပို့ပေးမည့် စနစ်
                        if chat_id == ADMIN_ID and ("video" in msg_data or "audio" in msg_data or "voice" in msg_data or "animation" in msg_data or ("photo" in msg_data and "reply_to_message" not in msg_data)):
                            # အကယ်၍ caption ထဲမှာ /ad ပါရင် သို့မဟုတ် ဒီတိုင်း ပို့လာရင် အစုလိုက်ပို့မည်
                            threading.Thread(target=broadcast_forward_process, args=(ADMIN_ID, ADMIN_ID, message_id)).start()
                            continue

                        if "photo" in msg_data and chat_id != ADMIN_ID:
                            file_id = msg_data["photo"][-1]["file_id"]
                            approve_menu = {
                                "inline_keyboard": [[{"text": "🔑 အတည်ပြုပြီး Premium ဖွင့်ပေးရန်", "callback_data": f"approve_{chat_id}"}]]
                            }
                            payload = {"chat_id": ADMIN_ID, "photo": file_id, "caption": f"📩 <b>User ထံမှ Ngweလွှဲစလစ် ရောက်လာပါသည်-</b>\n• Chat ID: <code>{chat_id}</code>", "parse_mode": "HTML", "reply_markup": json.dumps(approve_menu)}
                            requests.post(f"{BASE_URL}/sendPhoto", json=payload)
                            send_message(chat_id, "📥 သင်၏ ငွေလွှဲစလစ်ပုံကို လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးနေပါသဖြင့် ခေတ္တစောင့်ဆိုင်းပေးပါဦးဗျာ...")
                            continue

                        if "text" in msg_data:
                            text = msg_data["text"].strip()
                            
                            if chat_id == ADMIN_ID and text.startswith("/setad "):
                                new_ad = text.replace("/setad ", "", 1)
                                if new_ad:
                                    db = load_data()
                                    db["current_ad"] = new_ad
                                    save_data(db)
                                    send_message(ADMIN_ID, f"✅ <b>အောင်မြင်ပါသည်!</b> ပုံသေပြသမည့် ကြော်ငြာစာသားကို ပြောင်းလဲလိုက်ပါပြီ-\n\n{new_ad}")
                                continue

                            if chat_id == ADMIN_ID and text.startswith("/ad "):
                                ad_content = text.replace("/ad ", "", 1)
                                if ad_content:
                                    db = load_data()
                                    users = db.get("all_users", [])
                                    threading.Thread(target=broadcast_forward_process, args=(ADMIN_ID, ADMIN_ID, message_id)).start() # စာသားကိုလည်း Forward အနေနဲ့ ပို့နိုင်သည်
                                continue

                            if chat_id != ADMIN_ID and not text.startswith('/'):
                                send_message(ADMIN_ID, f"📩 <b>User စာပို့လာသည်:</b>\n• Chat ID: <code>{chat_id}</code>\n• Message: {text}")

                            if text.startswith('/start'):
                                welcome_msg = (
                                    f"👋 <b>မြန်မာနိုင်ငံ၏ အကောင်းဆုံး Video Downloader ဘော့မှ ကြိုဆိုပါသည်!</b>\n\n"
                                    f"Facebook နှင့် TikTok ဗီဒီယိုလင့်ခ်များကို ပို့ပေးရုံဖြင့် အလွယ်တကူ ဒေါင်းလုဒ်ဆွဲနိုင်ပါသည်။\n\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🎬 <b>Free အသုံးပြုသူများ (240p):</b>\n"
                                    f"• (၅) မိနစ်အောက် ဗီဒီယိုတိုများကို အခမဲ့ အကန့်အသတ်မရှိ ဒေါင်းနိုင်ပါသည်။\n\n"
                                    f"💎 <b>Premium အဖွဲ့ဝင်များ (ဗီဒီယိုအရှည် + 480p / 720p HD):</b>\n"
                                    f"• မိနစ်ရှည် ဗီဒီယိုကြီးများနှင့် ပိုမိုကြည်လင်ပြတ်သားသော HD ကွာလတီများကို စိတ်ကြိုက် ဒေါင်းလုဒ်ဆွဲနိုင်ခွင့် ရှိပါသည်။\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"🚀 <b>အသုံးပြုရန် -</b> ဗီဒီယိုလင့်ခ်ကို ဤနေရာတွင် တန်းပြီး ပို့ပေးလိုက်ပါဗျာ...\n\n"
                                    f"_(သင့် Chat ID: <code>{chat_id}</code> )_"
                                )
                                send_message(chat_id, welcome_msg)
                                
                            elif text == '/usercount':
                                if chat_id == ADMIN_ID or str(chat_id) == str(ADMIN_ID):
                                    db = load_data()
                                    total = len(db.get("all_users", []))
                                    premium = len(db.get("premium_users", []))
                                    send_message(chat_id, f"📊 <b>ဘော့အခြေအနေ:</b>\n\n• စုစုပေါင်းအသုံးပြုသူ: <code>{total}</code> ဦး\n• Premium အဖွဲ့ဝင်: <code>{premium}</code> ဦး")

                            elif text.startswith("http://") or text.startswith("https://"):
                                if chat_id in pending_db: del pending_db[chat_id]
                                menu = {
                                    "inline_keyboard": [
                                        [{"text": "🎬 240p (Free - အတိုသာရမည်)", "callback_data": f"q_240|{text}"}],
                                        [{"text": "⭐ 480p (Premium)", "callback_data": f"q_480|{text}"}],
                                        [{"text": "💎 720p (Premium)", "callback_data": f"q_720|{text}"}]
                                    ]
                                }
                                db = load_data()
                                current_ad_text = db.get("current_ad", DEFAULT_AD)
                                msg_with_ad = f"⬇️ ဗီဒီယို အရည်အသွေး (Quality) ကို ရွေးချယ်ပေးပါ-\n\n{current_ad_text}"
                                send_message(chat_id, msg_with_ad, reply_markup=menu)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    threading.Thread(target=bot_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
