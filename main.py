import os
import sys
import time
import asyncio
import threading
import json
import random
import string
import requests
import queue
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
import yt_dlp
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

app = FastAPI()

BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SERVER_URL = "https://hhs-zlhu.onrender.com" 

OWNER_ID = 8391123176  # <--- လူကြီးမင်း (Owner) ရဲ့ ID အမှန်
ADMIN_IDS = [6622954461,]  # <--- မိမိ ID နှင့် ပါတနာ အက်ဒမင် ID များ

DEFAULT_AD = "📢 <b>[ကြော်ငြာ]</b> မြန်မာနိုင်ငံ၏ ယုံကြည်စိတ်ချရဆုံး အွန်လိုင်းစျေးဝယ်ပလက်ဖောင်းကို အသုံးပြုရန် ဤနေရာကိုနှိပ်ပါ"

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

JSON_FILE = "codes.json"

download_queue = queue.Queue()

def load_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            try:
                data = json.load(f)
                if "current_ad" not in data: data["current_ad"] = DEFAULT_AD
                if "all_users" not in data: data["all_users"] = []
                if "premium_users" not in data: data["premium_users"] = {}
                if "active_codes" not in data: data["active_codes"] = {}
                if "resellers" not in data: data["resellers"] = [] # Reseller list
                if "reseller_wallets" not in data: data["reseller_wallets"] = {} # Wallet balance
                if "user_referrals" not in data: data["user_referrals"] = {} # ဝယ်သူက ဘယ်သူ့လူလဲ မှတ်ရန်
                return data
            except: pass
    return {
        "active_codes": {}, "premium_users": {}, "all_users": [], 
        "current_ad": DEFAULT_AD, "resellers": [], "reseller_wallets": {}, "user_referrals": {}
    }

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
    try: 
        res = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10).json()
        return res.get("result")
    except: return None

def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup is not None: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{BASE_URL}/editMessageText", json=payload, timeout=10)
    except: pass

def answer_callback_query(callback_query_id, text, show_alert=False):
    payload = {"callback_query_id": callback_query_id, "text": text, "show_alert": show_alert}
    try: requests.post(f"{BASE_URL}/answerCallbackQuery", json=payload, timeout=10)
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

def raw_download_process(chat_id, video_url, target_quality, status_msg_id):
    if target_quality == "720p":
        format_selector = "bestvideo[height<=720]+bestaudio/best"
    elif target_quality == "480p":
        format_selector = "bestvideo[height<=480]+bestaudio/best"
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
            
            edit_message(chat_id, status_msg_id, "✅ ဒေါင်းလုဒ်လုပ်ခြင်း ပြီးဆုံးပါပြီ။ ဗီဒီယိုဖိုင်ကို ပို့ပေးနေပါပြီ...")
            
            if file_size_mb > 45:
                download_url = f"{SERVER_URL}/get_file/{file_id}"
                send_message(chat_id, f"📦 ဖိုင်ဆိုဒ် {file_size_mb:.2f} MB ရှိသဖြင့် Chrome မှ ဒေါင်းပါ-\n{download_url}\n\n⚠️ (၁ နာရီအတွင်းသာ ရပါမည်။)\n\n{ad_text}")
                auto_delete_file(filename, delay=3600)
            else:
                with open(filename, 'rb') as f:
                    requests.post(f"{BASE_URL}/sendVideo", data={'chat_id': chat_id, 'caption': ad_text, 'parse_mode': 'HTML'}, files={'video': f}, timeout=120)
                os.remove(filename)
        else: 
            edit_message(chat_id, status_msg_id, "❌ ဗီဒီယို ဒေါင်းလုဒ်ဆွဲ၍ မရပါ။ လင့်ခ်မှားယွင်းနေခြင်း ဖြစ်နိုင်ပါသည်။")
    except Exception as e:
        edit_message(chat_id, status_msg_id, "❌ ဒေါင်းလုဒ်လုပ်ရတာ အဆင်မပြေပါ။ ခေတ္တစောင့်ပြီးမှ ပြန်ပို့ပေးပါ။")
        if os.path.exists(filename): os.remove(filename)

def queue_worker():
    print("🤖 BACKEND QUEUE WORKER STARTED...", flush=True)
    while True:
        try:
            task = download_queue.get()
            chat_id, video_url, target_quality, status_msg_id = task
            edit_message(chat_id, status_msg_id, f"⏳ သင့်အလှည့် ရောက်ပါပြီ။ <b>{target_quality}</b> ဖြင့် ဗီဒီယိုကို စတင်ဒေါင်းလုဒ်လုပ်နေပါပြီ...")
            raw_download_process(chat_id, video_url, target_quality, status_msg_id)
            download_queue.task_done()
        except Exception as e:
            time.sleep(2)

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
    print("🚀 PREMIUM, RESELLER & QUEUE BOT ACTIVE...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
                    # 📩 Callback Query ကိုကိုင်တွယ်ခြင်း
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        chat_id = cb["message"]["chat"]["id"]
                        msg_id = cb["message"]["message_id"]
                        cb_data = cb["data"]
                        
                        prem_status, _ = is_premium(chat_id)
                        
                        if cb_data.startswith("q_"):
                            parts = cb_data.split("_", 2)
                            selected_q = parts[1]
                            v_url = parts[2]
                            
                            if selected_q in ["480p", "720p"] and not prem_status:
                                answer_callback_query(cb_id, "⚠️ Premium အဖွဲ့ဝင်များသာ လျှင် အရည်အသွေးကောင်းမွန်စွာ ရယူနိုင်ပါသည်။", show_alert=True)
                                msg = (
                                    f"⚠️ <b>HD ဗီဒီယို ဒေါင်းလုဒ်ဆွဲရန်မှာ ပရီမီယမ်များအတွက်သာ ဖြစ်ပါသည်။</b>\n\n"
                                    f"💎 သက်တမ်းအလိုက် ပရီမီယမ်ဝယ်ယူရန် Ngwe လွှဲပေးပါဦးဗျာ။\n"
                                    f"• KPay နံပါတ်: <code>09784732943</code> (U Tun Tun Latt)\n"
                                    f"• ၁ ပတ် - ၃၀၀၀ ကျပ် | ၁ လ - ၅၀၀၀ | ၁ နှစ်စာ ၄၅၀၀၀ ကျပ်\n\n"
                                    f"👉 Ngwe လွှဲပြီး စလစ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။ Admin မှ ပရီမီယမ်ကုဒ် ပေးပါလိမ့်မည်။"
                                )
                                send_message(chat_id, msg)
                                continue
                            
                            answer_callback_query(cb_id, "📥 တန်းစီဇယားထဲ ထည့်သွင်းလိုက်ပါပြီ။")
                            edit_message(chat_id, msg_id, "📥 သင်၏ ဗီဒီယိုကို တန်းစီဇယားထဲ ထည့်သွင်းလိုက်ပါပြီ။ သင့်အလှည့်ရောက်လျှင် အလိုအလျောက် ဒေါင်းပေးမည်ဖြစ်၍ ခေတ္တစောင့်ဆိုင်းပေးပါဦးဗျာ...")
                            download_queue.put((chat_id, v_url, selected_q, msg_id))
                            continue

                        # 👑 Owner Approval Handling
                        if cb_data.startswith("approve_"):
                            parts = cb_data.split("_")
                            agent_id = int(parts[1])
                            duration_type = parts[2]
                            count = int(parts[3])
                            
                            db = load_data()
                            generated_codes_list = []
                            for _ in range(count):
                                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                                generated_code = f"PREM-{duration_type.upper()}-{random_str}"
                                db["active_codes"][generated_code] = duration_type
                                generated_codes_list.append(f"• <code>{generated_code}</code>")
                            save_data(db)
                            
                            codes_text = "\n".join(generated_codes_list)
                            answer_callback_query(cb_id, "✅ ကုဒ်ထုတ်ခွင့် ပြုလိုက်ပါပြီ။")
                            edit_message(chat_id, msg_id, f"✅ <b>အေးဂျင့် ID: {agent_id} ၏ တောင်းခံမှုကို ခွင့်ပြုပြီး ကုဒ်များကို အေးဂျင့်ဆီသို့ ပို့ဆောင်ပေးလိုက်ပါပြီ။</b>")
                            send_message(agent_id, f"🎉 <b>Owner မှ ခွင့်ပြုလိုက်ပါပြီ!</b>\n\n✅ <b>သင်တောင်းဆိုထားသော ပရီမီယမ်ကုဒ် ({count}) ခု ထွက်လာပါပြီ-</b>\n\n🎫 <b>ကုဒ်စာရင်း -</b>\n{codes_text}")
                            continue
                            
                        if cb_data.startswith("reject_"):
                            parts = cb_data.split("_")
                            agent_id = int(parts[1])
                            answer_callback_query(cb_id, "❌ တောင်းခံမှုကို Ngengပယ်လိုက်ပါပြီ။")
                            edit_message(chat_id, msg_id, f"❌ <b>အေးဂျင့် ID: {agent_id} ၏ တောင်းခံမှုကို သင်က Ngengပယ်လိုက်ပါသည်။</b>")
                            send_message(agent_id, "❌ <b>ဆောရီးဗျာ!</b>\n\nသင်တောင်းဆိုထားသော ပရီမီယမ်ကုဒ် ထုတ်ခွင့်ကို ပိုင်ရှင် (Owner) မှ <b>ငြင်းပယ် (Reject)</b> လိုက်ပါသဖြင့် ကုဒ်မထွက်လာပါ။")
                            continue
                        continue

                    # ✉️ Message Handling
                    if "message" in update:
                        msg_data = update["message"]
                        chat_id = msg_data["chat"]["id"]
                        message_id = msg_data["message_id"]
                        
                        # 👤 User အချက်အလက်များရယူခြင်း (နာမည်ခေါ်ရန်)
                        first_name = msg_data["from"].get("first_name", "အသုံးပြုသူ")
                        username = msg_data["from"].get("username", "No_Username")
                        
                        db = load_data()
                        if chat_id not in db["all_users"] and str(chat_id) not in db["all_users"]:
                            db["all_users"].append(chat_id)
                            save_data(db)

                        # Admin Forward Ads
                        if chat_id in ADMIN_IDS and ("video" in msg_data or "audio" in msg_data or "voice" in msg_data or "animation" in msg_data or ("photo" in msg_data and "reply_to_message" not in msg_data)):
                            threading.Thread(target=broadcast_forward_process, args=(chat_id, chat_id, message_id)).start()
                            continue

                        # User Screenshot Slip
                        if "photo" in msg_data and chat_id not in ADMIN_IDS:
                            file_id = msg_data["photo"][-1]["file_id"]
                            for current_admin in ADMIN_IDS:
                                payload = {"chat_id": current_admin, "photo": file_id, "caption": f"📩 <b>User ထံမှ စလစ် ရောက်လာပါသည်-</b>\n• နာမည်: <b>{first_name}</b>\n• Chat ID: <code>{chat_id}</code>\n• Username: @{username}\n\n<i>မှတ်ချက်- ပရီမီယမ်သက်တမ်းတိုးရန် ဤ User အတွက် /gen ကိုသုံး၍ ကုဒ်ထုတ်ပေးလိုက်ပါဗျာ။</i>", "parse_mode": "HTML"}
                                requests.post(f"{BASE_URL}/sendPhoto", json=payload)
                            send_message(chat_id, f"📥 <b>{first_name}</b> ရေ... သင်၏ ငွေလွှဲစလစ်ပုံကို လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီး ပရီမီယမ်ကုဒ် လာပေးပါလိမ့်မည်။ ခေတ္တစောင့်ဆိုင်းပေးပါဦးဗျာ...")
                            continue

                        if "text" in msg_data:
                            text = msg_data["text"].strip()
                            
                            # 🤝 ၁။ Admin မှ Reseller အသစ်ထည့်သွင်းခြင်း (/add_agent [Chat_ID])
                            if chat_id in ADMIN_IDS and text.startswith("/add_agent "):
                                try:
                                    target_id = text.split()[1].strip()
                                    db = load_data()
                                    if target_id not in db["resellers"]:
                                        db["resellers"].append(target_id)
                                        db["reseller_wallets"][target_id] = 0
                                        save_data(db)
                                        send_message(chat_id, f"✅ <b>Reseller အဖြစ် သတ်မှတ်မှု အောင်မြင်ပါသည်!</b>\n\n👤 ID: <code>{target_id}</code> ကို အေးဂျင့် (Reseller) အဖြစ် စနစ်ထဲသို့ ထည့်သွင်းပြီးပါပြီ။")
                                        send_message(int(target_id), "🎉 <b>ဂုဏ်ယူပါသည်!</b>\n\nသင့်ကို ပိုင်ရှင်မှ <b>Reseller (အေးဂျင့်)</b> အဖြစ် သတ်မှတ်ပေးလိုက်ပါပြီ။\n👉 ကိုယ်ပိုင် Referral Link ထုတ်ရန် ဘော့ထဲတွင် `/link` ဟု ရိုက်ပို့နိုင်ပါပြီဗျာ။")
                                    else:
                                        send_message(chat_id, "⚠️ ဤ ID သည် စနစ်ထဲတွင် Reseller ဖြစ်ပြီးသားပါ။")
                                except:
                                    send_message(chat_id, "❌ ပုံစံမှားနေပါသည်။ ဥပမာ- <code>/add_agent 12345678</code>")
                                continue

                            # 🔗 ၂။ Reseller သမားများ ကိုယ်ပိုင် Link ထုတ်ယူခြင်း (/link)
                            if text == "/link":
                                db = load_data()
                                if str(chat_id) in db["resellers"]:
                                    bot_info = requests.get(f"{BASE_URL}/getMe").json()
                                    bot_username = bot_info["result"]["username"]
                                    ref_link = f"https://t.me/{bot_username}?start=R_{chat_id}"
                                    wallet_balance = db["reseller_wallets"].get(str(chat_id), 0)
                                    
                                    msg = (
                                        f"🤝 <b>Reseller ရုံးခန်းမှ ကြိုဆိုပါသည်!</b>\n\n"
                                        f"🔗 <b>သင်၏ ကိုယ်ပိုင် မိတ်ဆက်လင့်ခ်-</b>\n<code>{ref_link}</code>\n\n"
                                        f"💰 <b>လက်ရှိရရှိထားသော ကော်မရှင် စုစုပေါင်း:</b> <code>{wallet_balance}</code> ကျပ်\n\n"
                                        f"💡 <i>မှတ်ချက်- အထက်ပါလင့်ခ်ကို ကော်ပီယူ၍ ဝယ်သူများကို ဖိတ်ခေါ်ပါ။ ဝယ်သူများ ကုဒ်ဝယ်ယူသုံးစွဲတိုင်း သင်သည် 10% ကော်မရှင် အော်တို ရရှိပါမည်။ ငွေစိုက်ရန် လုံးဝမလိုပါ။</i>"
                                    )
                                    send_message(chat_id, msg)
                                else:
                                    send_message(chat_id, "❌ သင်သည် စနစ်ထဲတွင် Reseller (အေးဂျင့်) မဟုတ်ပါ။")
                                continue

                            # 🔑 ၃။ အက်ဒမင်များ ကုဒ်ထုတ်ခြင်း (/gen week [အရေအတွက်])
                            if chat_id in ADMIN_IDS and text.startswith("/gen"):
                                parts = text.split()
                                if len(parts) < 2 or parts[1].lower() not in ["week", "month", "year"]:
                                    send_message(chat_id, "❌ ပုံစံမှားနေပါသည်။ အောက်ပါအတိုင်း ရိုက်ပါ-\n• <code>/gen week</code> (၁ ကုဒ်ထုတ်ရန်)\n• <code>/gen week 10</code> (၁၀ ကုဒ် တစ်ပြိုင်တည်းထုတ်ရန်)")
                                    continue
                                
                                duration_type = parts[1].lower()
                                count = 1
                                if len(parts) >= 3:
                                    try: count = int(parts[2])
                                    except: count = 1
                                
                                if chat_id == OWNER_ID:
                                    db = load_data()
                                    generated_codes_list = []
                                    for _ in range(count):
                                        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                                        generated_code = f"PREM-{duration_type.upper()}-{random_str}"
                                        db["active_codes"][generated_code] = duration_type
                                        generated_codes_list.append(f"• <code>{generated_code}</code>")
                                    save_data(db)
                                    codes_text = "\n".join(generated_codes_list)
                                    send_message(chat_id, f"✅ <b>ပရီမီယမ်ကုဒ် ({count}) ခု အောင်မြင်စွာထုတ်ပြီးပါပြီ!</b>\n\n🎫 <b>ကုဒ်စာရင်း -</b>\n{codes_text}")
                                else:
                                    send_message(chat_id, "⏳ ဤကုဒ်ကို ထုတ်ရန်အတွက် ပိုင်ရှင် (Owner) ထံသို့ ခွင့်ပြုချက် (Approval) တောင်းခံနေပါသည်။ ခေတ္တစောင့်ဆိုင်းပါ...")
                                    approve_keyboard = {
                                        "inline_keyboard": [
                                            [
                                                {"text": "✅ ခွင့်ပြုမည်", "callback_data": f"approve_{chat_id}_{duration_type}_{count}"},
                                                {"text": "❌ Ngengပယ်မည်", "callback_data": f"reject_{chat_id}"}
                                            ]
                                        ]
                                    }
                                    send_message(OWNER_ID, f"🔔 <b>ကုဒ်ထုတ်ခွင့် တောင်းခံလာပါသည်!</b>\n\n👤 <b>အေးဂျင့် ID:</b> <code>{chat_id}</code>\n⏱️ <b>သက်တမ်း:</b> <b>{duration_type.upper()}</b>\n📦 <b>အရေအတွက်:</b> <code>{count}</code> ခု\n\n👉 ဤတောင်းခံမှုကို ခွင့်ပြုမလားဗျာ?", reply_markup=approve_keyboard)
                                continue

                            # 🎁 ၄။ အသုံးပြုသူများ ကုဒ်ပြန်လည်အသုံးပြုခြင်း + Reseller 10% ခွဲဝေခြင်း စနစ်သစ်
                            if text.startswith("/redeem "):
                                user_code = text.replace("/redeem ", "", 1).strip()
                                db = load_data()
                                
                                if user_code in db.get("active_codes", {}):
                                    dtype = db["active_codes"][user_code]
                                    
                                    # 💰 ဈေးနှုန်းအလိုက် 10% ကော်မရှင် တွက်ချက်ခြင်း
                                    code_prices = {"week": 300, "month": 1000, "year": 10000}
                                    code_value = code_prices.get(dtype, 1000)
                                    commission = int(code_value * 0.10) # 10% Auto Commission
                                    
                                    now = time.time()
                                    current_prem, current_expire = is_premium(chat_id)
                                    base_time = current_expire if current_prem else now
                                    
                                    if dtype == "week": add_seconds = 7 * 24 * 60 * 60
                                    elif dtype == "month": add_seconds = 30 * 24 * 60 * 60
                                    else: add_seconds = 365 * 24 * 60 * 60
                                    
                                    new_expire = base_time + add_seconds
                                    db["premium_users"][str(chat_id)] = new_expire
                                    del db["active_codes"][user_code]
                                    
                                    # 💸 Reseller ထံသို့ 10% ကော်မရှင် အော်တို ခွဲဝေပေးခြင်း
                                    referrer_id = db["user_referrals"].get(str(chat_id))
                                    if referrer_id and str(referrer_id) in db["resellers"]:
                                        ref_str = str(referrer_id)
                                        db["reseller_wallets"][ref_str] = db["reseller_wallets"].get(ref_str, 0) + commission
                                        total_wallet = db["reseller_wallets"][ref_str]
                                        
                                        # Reseller ထံသို့ သတင်းစကားလှမ်းပို့ခြင်း
                                        ref_msg = (
                                            f"💰 <b>ကော်မရှင်အသစ် ရရှိပါသည်!</b>\n\n"
                                            f"👤 ဝယ်သူ: <b>{first_name}</b> (@{username})\n"
                                            f"🎫 အသုံးပြုသည့်ကုဒ်: {dtype.upper()}\n"
                                            f"💸 သင်ရရှိသောကော်မရှင် (10%): <code>{commission}</code> ကျပ်\n"
                                            f"📊 လက်ရှိ သင်၏ စုစုပေါင်းရငွေ: <code>{total_wallet}</code> ကျပ်"
                                        )
                                        send_message(int(referrer_id), ref_msg)

                                    save_data(db)
                                    
                                    expire_date = datetime.fromtimestamp(new_expire).strftime('%Y-%m-%d %H:%M:%S')
                                    send_message(chat_id, f"🎉 <b>{first_name} ရေ... ကုဒ်အသုံးပြုမှု အောင်မြင်ပါသည်!</b>\n\n💎 သင်၏အကောင့်သည် <b>{dtype.upper()}</b> ပရီမီယမ် ဖြစ်သွားပါပြီ။\n📅 သက်တမ်းကုန်ဆုံးမည့်ရက်: <code>{expire_date}</code>")
                                else:
                                    send_message(chat_id, f"❌ <b>{first_name}</b>... သင်ရိုက်ထည့်လိုက်သော ကုဒ် မမှန်ကန်ပါ သို့မဟုတ် အသုံးပြုပြီးသား ဖြစ်နေပါသည်။")
                                continue

                            if chat_id in ADMIN_IDS and text.startswith("/setad "):
                                new_ad = text.replace("/setad ", "", 1)
                                if new_ad:
                                    db = load_data()
                                    db["current_ad"] = new_ad
                                    save_data(db)
                                    send_message(chat_id, f"✅ <b>Inline Ad ပြောင်းလဲပြီးပါပြီ!</b>")
                                continue

                            if chat_id in ADMIN_IDS and text.startswith("/ad "):
                                ad_content = text.replace("/ad ", "", 1)
                                if ad_content:
                                    threading.Thread(target=broadcast_forward_process, args=(chat_id, chat_id, message_id)).start()
                                continue

                            # 🕴️ အေးဂျင့် သို့မဟုတ် အက်ဒမင်များအတွက် သီးသန့် ID ထုတ်ပေးရန် Command
                            if text.lower() == '/agent' or text.lower() == '/admin':
                                agent_msg = (
                                    f"👑 <b>Agent/Admin Dashboard Setup</b>\n\n"
                                    f"လူကြီးမင်း၏ အေးဂျင့်အကောင့် သို့မဟုတ် အက်ဒမင်အကောင့် ပြုလုပ်ရန်အတွက် အောက်ပါ Chat ID နံပါတ်ကို ကော်ပီကူး၍ အက်ဒမင်ထံ ပေးပို့ပေးပါဗျာ။\n\n"
                                    f"🔑 သင့်ရဲ Chat ID: <code>{chat_id}</code>\n\n"
                                    f"_(စာလုံးအပြာရောင်လေးကို ဖိနှိပ်ပြီး အလွယ်တကူ Copy ကူးနိုင်ပါသည်)_"
                                )
                                send_message(chat_id, agent_msg)
                                continue

                            # 👥 ၅။ Start Message နှုတ်ဆက်ခြင်းနှင့် နာမည်ခေါ်ခြင်း၊ Referral မှတ်သားခြင်း
                            if text.startswith('/start'):
                                db = load_data()
                                
                                # မိတ်ဆက်လင့်ခ်မှ တဆင့် ဝင်လာခြင်း ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
                                if len(text.split()) > 1:
                                    start_param = text.split()[1]
                                    if start_param.startswith("R_"):
                                        inviter_id = start_param.replace("R_", "", 1)
                                        # အကယ်၍ ဤဝယ်သူသည် ယခင်က ဘယ်သူ့လူမှ မဟုတ်သေးလျှင် ယခု ဖိတ်ခေါ်သူ၏ လူအဖြစ် မှတ်သားမည်
                                        if str(chat_id) not in db["user_referrals"]:
                                            db["user_referrals"][str(chat_id)] = inviter_id
                                            save_data(db)
                                
                                welcome_msg = (
                                    f"👋 <b>{first_name}</b> ရေ... <b>Video Downloader ဘော့မှ လှိုက်လှဲစွာ ကြိုဆိုပါသည်!</b>\n\n"
                                    f"Facebook နှင့် TikTok ဗီဒီယိုလင့်ခ်များကို ပို့ပေးရုံဖြင့် တိုက်ရိုက်ဒေါင်းလုဒ်ဆွဲနိုင်ပါသည်။\n\n"
                                    f"🎫 <b>ပရီမီယမ်ကုဒ်ရှိပါက -</b> <code>/redeem မိမိကုဒ်</code> ဟုရိုက်ထည့်ပါ။\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🎬 Free အသုံးပြုသူများ (240p):\n• (၅) မိနစ်အောက် ဗီဒီယိုတိုများကို အခမဲ့ အကန့်အသတ်မရှိ ရယူနိုင်ပါသည်။\n\n"
                                    f"💎 Premium အဖွဲ့ဝင်များ (480p / 720p HD):\n• မိနစ်ရှည် ဗီဒီယိုကြီးများနှင့် ပိုမိုကြည်လင်ပြတ်သားသော HD ကွာလတီများကို စိတ်ကြိုက် ရယူနိုင်ပါသည်။\n"
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

                            elif text.startswith("http://") or text.startswith("https://"):
                                duration = get_video_duration(text)
                                prem_status, _ = is_premium(chat_id)
                                
                                if duration > 3600:
                                    send_message(chat_id, f"⚠️ <b>{first_name}</b>... ဆာဗာလုံခြုံရေးအရ (၁) နာရီထက် ပိုရှည်သော ဗီဒီယိုများကို ဒေါင်းလုဒ်ဆွဲခွင့် မပြုသေးပါ။")
                                    continue

                                if not prem_status and duration > 300:
                                    msg = (
                                        f"⚠️ <b>{first_name}</b>... <b>Free ဗားရှင်းတွင် (၅) မိနစ်အောက် ဗီဒီယိုများကိုသာ ခွင့်ပြုပါသည်။</b>\n\n"
                                        f"💎 သက်တမ်းအလိုက် ပရီမီယမ်ဝယ်ယူရန် Ngwe လွှဲပေးပါဦးဗျာ။\n"
                                        f"• KPay နံ接တ်: <code>09123456789</code> (U Mya)\n"
                                        f"• ၁ ပတ် - ၃၀၀၀ ကျပ် | ၁ လ - ၅၀၀၀ | ၁ နှစ်စာ ၄၅၀၀၀ ကျပ်\n\n"
                                        f"👉 Ngwe လွှဲပြီး စလစ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။ Admin မှ ပရီမီယမ်ကုဒ် ပေးပါလိမ့်မည်။"
                                    )
                                    send_message(chat_id, msg)
                                    continue
                                
                                inline_keyboard = {
                                    "inline_keyboard": [
                                        [{"text": "🎬 240p (Free - အတိုသာရမည်)", "callback_data": f"q_240p_{text}"}],
                                        [{"text": "⭐ 480p (Premium)", "callback_data": f"q_480p_{text}"}],
                                        [{"text": "💎 720p (Premium)", "callback_data": f"q_720p_{text}"}]
                                    ]
                                }
                                db = load_data()
                                ad_text = db.get("current_ad", DEFAULT_AD)
                                send_message(chat_id, f"⬇️ <b>ဗီဒီယို အရည်အသွေး (Quality) ကို ရွေးချယ်ပေးပါ-</b>\n\n{ad_text}", reply_markup=inline_keyboard)

        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    
    threading.Thread(target=queue_worker, daemon=True).start()
    threading.Thread(target=bot_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
