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
from supabase import create_client, Client

sys.stdout.reconfigure(line_buffering=True)

app = FastAPI()

# --- Configurations ---
BOT_TOKEN = "8887542224:AAHvmusig10GJT0R5ndT1M8QFWEvQcVcvjo"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SERVER_URL = "https://hhs-zlhu.onrender.com" 

OWNER_ID = 8391123176  
ADMIN_IDS = [6622954461, ]  

DEFAULT_AD = "📢 <b>[ကြော်ငြာ]</b> မင်္ဂလာပါ"
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# ⚠️ သင်ယူလာသော Supabase URL နှင့် Key ကို ဤနေရာတွင် အစားထိုးပါ
# --- Supabase Setup ---
SUPABASE_URL = "https://hpmgsufadkirbfbmfese.supabase.co" 
SUPABASE_KEY = "sb_publishable_M4bT4XMJ44EXvdm44macDA_Mj-V2vsn" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

download_queue = queue.Queue()

def load_data():
    try:
        response = supabase.table("bot_data").select("data_value").eq("id", "config").execute()
        if response.data:
            data = response.data[0]["data_value"]
            if "current_ad" not in data: data["current_ad"] = DEFAULT_AD
            if "all_users" not in data: data["all_users"] = []
            if "premium_users" not in data: data["premium_users"] = {}
            if "active_codes" not in data: data["active_codes"] = {}
            if "resellers" not in data: data["resellers"] = [] 
            if "reseller_wallets" not in data: data["reseller_wallets"] = {} 
            if "user_referrals" not in data: data["user_referrals"] = {} 
            return data
    except Exception as e:
        print(f"Supabase Load Error: {e}", flush=True)
        
    return {
        "active_codes": {}, "premium_users": {}, "all_users": [], 
        "current_ad": DEFAULT_AD, "resellers": [], "reseller_wallets": {}, "user_referrals": {}
    }

def save_data(data):
    try:
        supabase.table("bot_data").update({"data_value": data}).eq("id", "config").execute()
    except Exception as e:
        print(f"Supabase Save Error: {e}", flush=True)

def is_premium(chat_id):
    if int(chat_id) in ADMIN_IDS or chat_id in ADMIN_IDS:
        return True, time.time() + 315360000
        
    db = load_data()
    premiums = db.get("premium_users", {})
    
    uid = str(chat_id)
    if uid in premiums:
        expire_time = premiums[uid]
        if time.time() < expire_time:
            return True, expire_time
            
    if isinstance(chat_id, int) and str(chat_id) in premiums:
        expire_time = premiums[str(chat_id)]
        if time.time() < expire_time:
            return True, expire_time
            
    return False, 0

@app.get("/")
@app.head("/")
def health_check():
    return {"status": "active", "message": "Bot Server is Running with Supabase"}

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

def edit_message_caption(chat_id, message_id, caption, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "caption": caption, "parse_mode": "HTML"}
    if reply_markup is not None: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{BASE_URL}/editMessageCaption", json=payload, timeout=10)
    except: pass

def auto_delete_file(file_path, delay=3600):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path): os.remove(file_path)
    threading.Thread(target=delete, daemon=True).start()

def get_video_duration(video_url):
    ydl_opts = {
        'quiet': True, 
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'extractor_args': {'instagram': {'check_embed': True}},
        'add_header': [
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language: en-US,en;q=0.9'
        ]
    }
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
        format_selector = "worst/worstvideo+worstaudio/best"
        
    file_id = f"video_{chat_id}_{int(time.time())}.mp4"
    filename = os.path.join(DOWNLOAD_DIR, file_id)
    
    ydl_opts = {
        'format': format_selector,
        'outtmpl': filename,
        'timeout': 90,
        'nocheckcertificate': True,
        'quiet': True,
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'extractor_args': {'instagram': {'check_embed': True}},
        'add_header': [
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language: en-US,en;q=0.9'
        ]
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
    print("🚀 PREMIUM, RESELLER & QUEUE BOT ACTIVE WITH SUPABASE...", flush=True)
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
            response = requests.get(url, timeout=25).json()
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
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
                                continue
                            
                            answer_callback_query(cb_id, "📥 တန်းစီဇယားထဲ ထည့်သွင်းလိုက်ပါပြီ။")
                            edit_message(chat_id, msg_id, "📥 သင်၏ ဗီဒီယိုကို တန်းစီဇယားထဲ ထည့်သွင်းလိုက်ပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါဦးဗျာ...")
                            download_queue.put((chat_id, v_url, selected_q, msg_id))
                            continue

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
                            edit_message(chat_id, msg_id, f"✅ အေးဂျင့် ID: {agent_id} ဆီသို့ ကုဒ်များ ပို့ဆောင်ပေးလိုက်ပါပြီ။")
                            send_message(agent_id, f"🎉 <b>Owner မှ ခွင့်ပြုလိုက်ပါပြီ!</b>\n\n🎫 <b>ကုဒ်စာရင်း -</b>\n{codes_text}")
                            continue
                            
                        if cb_data.startswith("reject_"):
                            parts = cb_data.split("_")
                            agent_id = int(parts[1])
                            answer_callback_query(cb_id, "❌ တောင်းခံမှုကို ငြင်းပယ်လိုက်ပါပြီ။")
                            edit_message(chat_id, msg_id, f"❌ အေးဂျင့် ID: {agent_id} ၏ တောင်းခံမှုကို ငြင်းပယ်လိုက်ပါသည်။")
                            send_message(agent_id, "❌ <b>ဆောရီးဗျာ!</b>\n\nကုဒ်ထုတ်ခွင့်ကို ပိုင်ရှင်မှ ငြင်းပယ်လိုက်ပါသည်။")
                            continue

                        if cb_data.startswith("check_start_"):
                            parts = cb_data.split("_")
                            cust_id = parts[2]
                            c_name = parts[3] if len(parts) > 3 else "User"
                            answer_callback_query(cb_id, "⚙️ သင် ဤစလစ်ကို စစ်ဆေးနေပါသည်...")
                            
                            updated_keyboard = {
                                "inline_keyboard": [
                                    [{"text": "✅ ကုဒ်ပေးပြီးပြီ (Done)", "callback_data": f"check_done_{cust_id}_{c_name}"}]
                                ]
                            }
                            orig_caption = cb["message"].get("caption", "")
                            new_caption = orig_caption.split("📊 အခြေအနေ:")[0] + f"📊 <b>အခြေအနေ:</b> စစ်ဆေးနေဆဲ 🟡" if "📊 အခြေအနေ:" in orig_caption else orig_caption + f"\n\n📊 <b>အခြေအနေ:</b> စစ်ဆေးနေဆဲ 🟡"
                            edit_message_caption(chat_id, msg_id, new_caption, reply_markup=updated_keyboard)
                            continue
                            
                        if cb_data.startswith("check_done_"):
                            parts = cb_data.split("_")
                            answer_callback_query(cb_id, "✅ ပြီးဆုံးကြောင်း မှတ်သားပြီးပါပြီ။")
                            orig_caption = cb["message"].get("caption", "")
                            new_caption = orig_caption.split("📊 အခြေအနေ:")[0] + f"📊 <b>အခြေအနေ:</b> စစ်ဆေးပြီး/အောင်မြင် ✅" if "📊 အခြေအနေ:" in orig_caption else orig_caption + f"\n\n📊 <b>အခြေအနေ:</b> စစ်ဆေးပြီး/အောင်မြင် ✅"
                            edit_message_caption(chat_id, msg_id, new_caption, reply_markup={"inline_keyboard": []})
                            continue
                        continue

                    if "message" in update:
                        msg_data = update["message"]
                        chat_id = msg_data["chat"]["id"]
                        message_id = msg_data["message_id"]
                        
                        first_name = msg_data["from"].get("first_name", "အသုံးပြုသူ")
                        username = msg_data["from"].get("username", "No_Username")
                        
                        db = load_data()
                        if chat_id not in db["all_users"] and str(chat_id) not in db["all_users"]:
                            db["all_users"].append(chat_id)
                            save_data(db)

                        if chat_id in ADMIN_IDS and ("video" in msg_data or "audio" in msg_data or "voice" in msg_data or "animation" in msg_data):
                            threading.Thread(target=broadcast_forward_process, args=(chat_id, chat_id, message_id)).start()
                            continue

                        if "photo" in msg_data and int(chat_id) not in ADMIN_IDS and chat_id not in ADMIN_IDS:
                            file_id = msg_data["photo"][-1]["file_id"]
                            clean_name = first_name.replace("_", "").replace("-", "")
                            check_keyboard = {"inline_keyboard": [[{"text": "⏳ မစစ်ရသေး (စစ်မည်)", "callback_data": f"check_start_{chat_id}_{clean_name}"},{"text": "✅ ကုဒ်ပေးပြီးပြီ", "callback_data": f"check_done_{chat_id}_{clean_name}"}]]}
                            
                            for current_admin in ADMIN_IDS:
                                try:
                                    requests.post(f"{BASE_URL}/sendPhoto", json={"chat_id": int(current_admin), "photo": file_id, "caption": f"📩 <b>User စလစ်ပုံ:</b>\n• နာမည်: <b>{first_name}</b>\n• Chat ID: <code>{chat_id}</code>\n• Username: @{username}", "parse_mode": "HTML", "reply_markup": json.dumps(check_keyboard)})
                                except: pass
                            if int(OWNER_ID) not in ADMIN_IDS and OWNER_ID not in ADMIN_IDS:
                                try:
                                    requests.post(f"{BASE_URL}/sendPhoto", json={"chat_id": int(OWNER_ID), "photo": file_id, "caption": f"📩 <b>[OWNER] User စလစ်ပုံ:</b>\n• Chat ID: <code>{chat_id}</code>", "parse_mode": "HTML", "reply_markup": json.dumps(check_keyboard)})
                                except: pass
                            send_message(chat_id, "📥 သင်၏ ငွေလွှဲစလစ်ပုံကို လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီး ပရီမီယမ်ကုဒ် လာပေးပါလိမ့်မည်။")
                            continue 

                        if "text" in msg_data:
                            text = msg_data["text"].strip()
                            
                            if (chat_id in ADMIN_IDS or int(chat_id) == OWNER_ID) and text.startswith("/add_agent "):
                                try:
                                    target_id = text.split()[1].strip()
                                    db = load_data()
                                    if target_id not in db["resellers"]:
                                        db["resellers"].append(target_id)
                                        db["reseller_wallets"][target_id] = 0
                                        save_data(db)
                                        send_message(chat_id, f"✅ ID: <code>{target_id}</code> ကို Reseller အဖြစ် ထည့်သွင်းပြီးပါပြီ။")
                                    else:
                                        send_message(chat_id, "⚠️ ဤ ID သည် Reseller ဖြစ်ပြီးသားပါ။")
                                except: pass
                                continue

                            if text == "/link":
                                db = load_data()
                                if str(chat_id) in db["resellers"]:
                                    bot_info = requests.get(f"{BASE_URL}/getMe").json()
                                    bot_username = bot_info["result"]["username"]
                                    ref_link = f"https://t.me/{bot_username}?start=R_{chat_id}"
                                    wallet_balance = db["reseller_wallets"].get(str(chat_id), 0)
                                    send_message(chat_id, f"🤝 <b>Reseller Link:</b>\n<code>{ref_link}</code>\n\n💰 <b>လက်ရှိကော်မရှင်:</b> <code>{wallet_balance}</code> ကျပ်")
                                else:
                                    send_message(chat_id, "❌ သင်သည် Reseller မဟုတ်ပါ။")
                                continue

                            if (chat_id in ADMIN_IDS or int(chat_id) == OWNER_ID) and text.startswith("/gen"):
                                parts = text.split()
                                if len(parts) < 2 or parts[1].lower() not in ["week", "month", "year"]:
                                    continue
                                duration_type = parts[1].lower()
                                count = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 1
                                
                                if int(chat_id) == OWNER_ID:
                                    db = load_data()
                                    generated_codes_list = []
                                    for _ in range(count):
                                        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                                        generated_code = f"PREM-{duration_type.upper()}-{random_str}"
                                        db["active_codes"][generated_code] = duration_type
                                        generated_codes_list.append(f"• <code>{generated_code}</code>")
                                    save_data(db)
                                    send_message(chat_id, f"✅ <b>ကုဒ်စာရင်း ({count} ခု) -</b>\n" + "\n".join(generated_codes_list))
                                else:
                                    approve_keyboard = {"inline_keyboard": [[{"text": "✅ ခွင့်ပြုမည်", "callback_data": f"approve_{chat_id}_{duration_type}_{count}"},{"text": "❌ ငြင်းပယ်မည်", "callback_data": f"reject_{chat_id}"}]]}
                                    send_message(OWNER_ID, f"🔔 <b>အေးဂျင့် ID {chat_id} မှ ကုဒ်တောင်းခံမှု ({duration_type.upper()} x {count})</b>", reply_markup=approve_keyboard)
                                continue

                            if text.startswith("/redeem "):
                                user_code = text.replace("/redeem ", "", 1).strip()
                                db = load_data()
                                if user_code in db.get("active_codes", {}):
                                    dtype = db["active_codes"][user_code]
                                    code_prices = {"week": 300, "month": 1000, "year": 10000}
                                    commission = int(code_prices.get(dtype, 1000) * 0.10)
                                    
                                    now = time.time()
                                    current_prem, current_expire = is_premium(chat_id)
                                    base_time = current_expire if current_prem else now
                                    add_seconds = (7*24*60*60) if dtype == "week" else (30*24*60*60) if dtype == "month" else (365*24*60*60)
                                    
                                    new_expire = base_time + add_seconds
                                    db["premium_users"][str(chat_id)] = new_expire
                                    del db["active_codes"][user_code]
                                    
                                    referrer_id = db["user_referrals"].get(str(chat_id))
                                    if referrer_id and str(referrer_id) in db["resellers"]:
                                        db["reseller_wallets"][str(referrer_id)] = db["reseller_wallets"].get(str(referrer_id), 0) + commission
                                        try: send_message(int(referrer_id), f"💰 <b>Referral ကော်မရှင်ဝင်ပါသည်:</b> +<code>{commission}</code> ကျပ်")
                                        except: pass
                                    save_data(db)
                                    send_message(chat_id, f"🎉 <b>Premium {dtype.upper()} ဖြစ်သွားပါပြီ!</b>\n📅 သက်တမ်းကုန်ရက်: <code>{datetime.fromtimestamp(new_expire).strftime('%Y-%m-%d')}</code>")
                                else:
                                    send_message(chat_id, "❌ ကုဒ်မမှန်ကန်ပါ သို့မဟုတ် အသုံးပြုပြီးသားဖြစ်နေသည်။")
                                continue

                            if text.startswith('/start'):
                                db = load_data()
                                if len(text.split()) > 1 and text.split()[1].startswith("R_"):
                                    inviter_id = text.split()[1].replace("R_", "", 1)
                                    if str(chat_id) not in db["user_referrals"]:
                                        db["user_referrals"][str(chat_id)] = inviter_id
                                        save_data(db)
                                send_message(chat_id, f"👋 မင်္ဂလာပါ <b>{first_name}</b>... ဗီဒီယိုလင့်ခ်များကို ဤနေရာတွင် တိုက်ရိုက်ပေးပို့ပြီး ဒေါင်းလုဒ်ဆွဲနိုင်ပါပြီဗျာ...")
                                continue

                            elif text.startswith("http://") or text.startswith("https://") or any(domain in text for domain in ["instagram.com", "facebook.com", "fb.watch", "youtu.be", "youtube.com", "tiktok.com", "x.com", "twitter.com"]):
                                duration = get_video_duration(text)
                                prem_status, _ = is_premium(chat_id)
                                if duration > 3600:
                                    send_message(chat_id, "⚠️ (၁) နာရီထက် ပိုရှည်သော ဗီဒီယိုများကို ဒေါင်းလုဒ်ဆွဲခွင့် မပြုပါ။")
                                    continue
                                if not prem_status and duration > 300:
                                    send_message(chat_id, "⚠️ Free ဗားရှင်းတွင် (၅) မိနစ်အောက် ဗီဒီယိုများကိုသာ ရနိုင်ပါသည်။ HD ရရန် Premium ဝယ်ယူပေးပါဦးဗျာ။")
                                    continue
                                
                                inline_keyboard = {"inline_keyboard": [[{"text": "🎬 240p (Free)", "callback_data": f"q_240p_{text}"}],[{"text": "⭐ 480p (Premium)", "callback_data": f"q_480p_{text}"}],[{"text": "💎 720p (Premium)", "callback_data": f"q_720p_{text}"}]]}
                                db = load_data()
                                send_message(chat_id, f"⬇️ <b>ဗီဒီယို အရည်အသွေးကို ရွေးချယ်ပါ-</b>\n\n{db.get('current_ad', DEFAULT_AD)}", reply_markup=inline_keyboard)
        except:
            time.sleep(5)

if __name__ == '__main__':
    try: requests.get(f"{BASE_URL}/deleteWebhook")
    except: pass
    threading.Thread(target=queue_worker, daemon=True).start()
    threading.Thread(target=bot_polling, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
