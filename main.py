import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

# အောက်က နေရာမှာ ခုနကရလာတဲ့ API Token ကို အစားထိုးထည့်ပါ
BOT_TOKEN = "8887542224:AAHv0kM9OoR4SQC3Vikjk-x4arRg-cqMOy8"

# Premium ID စာရင်း (လောလောဆယ် စမ်းသပ်ဖို့ သင့် ID အစစ်သိရင် ထည့်ထားနိုင်ပါတယ်)
PREMIUM_USERS = [] 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    url = update.message.text
    is_premium = user_id in PREMIUM_USERS

    await update.message.reply_text("ဗီဒီယိုကို စစ်ဆေးနေပါပြီ၊ ခေတ္တစောင့်ပါ။...")

    try:
        with yt_dlp.YoutubeDL() as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)

        if not is_premium:
            if duration > 3600:
                await update.message.reply_text("❌ ဒီဗီဒီယိုက ၁ နာရီထက် ကျော်နေပါတယ်။ အခမဲ့သမားတွေ ဒေါင်းလို့မရပါ။ Premium ဝယ်ယူပါ။")
                return
            
            ydl_opts = {
                'format': 'bestvideo[height<=480]+bestaudio/best', 
                'outtmpl': 'free_video.%(ext)s',
                'merge_output_format': 'mp4',
            }
            await update.message.reply_text("⏳ သင်က အခမဲ့အသုံးပြုသူဖြစ်လို့ 480p ရုပ်ထွက်နဲ့ ဒေါင်းလုဒ်လုပ်ပေးနေပါတယ်...")

        else:
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best', 
                'outtmpl': 'premium_video.%(ext)s',
                'merge_output_format': 'mp4',
            }
            await update.message.reply_text("🚀 သင်က Premium အသုံးပြုသူဖြစ်လို့ အမြင့်ဆုံး Quality နဲ့ ဒေါင်းလုဒ်လုပ်ပေးနေပါတယ်...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            download_info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(download_info)
            if not os.path.exists(filename):
                filename = os.path.splitext(filename)[0] + ".mp4"

        with open(filename, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="ဒေါင်းလုဒ် အောင်မြင်ပါပြီ။")
            
        os.remove(filename)

    except Exception as e:
        await update.message.reply_text(f"အမှားအယွင်းရှိခဲ့သည်- Link မမှန်ပါ သို့မဟုတ် ဒေါင်းလုဒ်မရနိုင်ပါခင်ဗျာ။")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot စတင်လည်ပတ်ပါပြီ...")
    app.run_polling()

if __name__ == '__main__':
    main()
