import os
import time
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackContext, CallbackQueryHandler
)
from pytube import YouTube
from datetime import timedelta

# تأكد من إضافة هذه المتغيرات في إعدادات Railway
TOKEN = os.environ.get('7996451048:AAF93EiT40FVXkksnUIWCfHzkhfNXDeGHnQ')  # توكن البوت
REQUIRED_CHANNELS = [""]  # قنوات الاشتراك الإجباري
ADMIN_CHAT_ID = ""  # آيدي المشرف (اختياري)

# إنشاء مجلد التحميلات
DOWNLOAD_FOLDER = "downloads/"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ========== وظائف مساعدة ==========
async def check_subscription(update: Update, context: CallbackContext) -> bool:
    """التحقق من اشتراك المستخدم في القنوات المطلوبة"""
    user = update.effective_user
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status in ['left', 'kicked']:
                buttons = [[InlineKeyboardButton("اشترك هنا", url=f"https://t.me/{channel[1:]}")]]
                await update.message.reply_text(
                    "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return False
        except Exception as e:
            print(f"خطأ في التحقق من الاشتراك: {e}")
    return True

def progress_bar(current, total, bar_length=20):
    """إنشاء شريط تقدم مرئي"""
    percent = float(current) * 100 / total
    arrow = '▣' * int(percent / 100 * bar_length)
    spaces = '▢' * (bar_length - len(arrow))
    return f'{arrow}{spaces} {percent:.1f}%'

# ========== أوامر البوت ==========
async def start(update: Update, context: CallbackContext):
    """رسالة الترحيب"""
    if not await check_subscription(update, context):
        return
    
    await update.message.reply_text(
        "🎬 مرحباً بك في بوت تحميل اليوتيوب!\n"
        "أرسل رابط فيديو يوتيوب لبدأ التحميل.\n\n"
        "📢 تابع قناتنا للأحدث: @channel_username"
    )

async def handle_video_link(update: Update, context: CallbackContext):
    """معالجة روابط اليوتيوب"""
    if not await check_subscription(update, context):
        return
    
    url = update.message.text
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            yt = YouTube(
                url,
                on_progress_callback=lambda stream, chunk, bytes_remaining:
                    progress_callback(stream, chunk, bytes_remaining, update, context)
            )
            context.user_data['yt'] = yt
            
            info = (
                f"📌 العنوان: {yt.title}\n"
                f"⏳ المدة: {str(timedelta(seconds=yt.length))}\n"
                f"👀 المشاهدات: {yt.views:,}\n\n"
                f"📊 اختر نوع التحميل:"
            )
            
            buttons = ReplyKeyboardMarkup(
                [["مقطع صوتي 🎵", "فيديو 🎥"]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await update.message.reply_text(info, reply_markup=buttons)
            
        except Exception as e:
            await update.message.reply_text("⚠️ حدث خطأ في معالجة الفيديو!")
            print(f"Error: {e}")
    else:
        await update.message.reply_text("⚠️ الرابط غير صالح! يرجى إرسال رابط يوتيوب صحيح.")

async def progress_callback(stream, chunk, bytes_remaining, update, context):
    """تحديث شريط التقدم"""
    current = stream.filesize - bytes_remaining
    progress = progress_bar(current, stream.filesize)
    
    try:
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data.get('progress_msg_id'),
            text=f"⏳ جاري التحميل...\n{progress}"
        )
    except:
        pass

async def handle_choice(update: Update, context: CallbackContext):
    """معالجة اختيار المستخدم"""
    choice = update.message.text
    yt = context.user_data.get('yt')
    
    if not yt:
        await update.message.reply_text("⚠️ يرجى إرسال الرابط أولاً!")
        return
    
    if "صوتي" in choice:
        try:
            audio = yt.streams.filter(only_audio=True).first()
            progress_msg = await update.message.reply_text("⏳ جاري تحضير المقطع الصوتي...\n▢▢▢▢▢▢▢▢▢▢ 0%")
            context.user_data['progress_msg_id'] = progress_msg.message_id
            
            file = audio.download(output_path=DOWNLOAD_FOLDER)
            mp3_file = file.replace(".mp4", ".mp3")
            os.rename(file, mp3_file)
            
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=progress_msg.message_id
            )
            
            await update.message.reply_audio(
                audio=open(mp3_file, 'rb'),
                title=yt.title,
                performer="تم التحميل بواسطة البوت"
            )
            os.remove(mp3_file)
            
        except Exception as e:
            await update.message.reply_text("❌ فشل التحميل! يرجى المحاولة لاحقاً.")
            print(f"Error: {e}")
    
    elif "فيديو" in choice:
        streams = yt.streams.filter(file_extension="mp4", progressive=True).order_by('resolution')
        buttons = []
        
        for stream in streams:
            size_mb = round(stream.filesize / (1024 * 1024), 2)
            quality = stream.resolution.replace('p', ' بيكسل')
            buttons.append([f"{quality} (~{size_mb} ميجابايت)"])
        
        if not buttons:
            await update.message.reply_text("⚠️ لا تتوفر جودات متاحة لهذا الفيديو!")
            return
        
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("🎥 اختر جودة الفيديو:", reply_markup=reply_markup)
        context.user_data['awaiting_quality'] = True

async def handle_quality(update: Update, context: CallbackContext):
    """معالجة اختيار الجودة"""
    if not await check_subscription(update, context):
        return
    
    if not context.user_data.get('awaiting_quality'):
        return
    
    quality_choice = update.message.text.split()[0]
    yt = context.user_data.get('yt')
    
    try:
        resolution = quality_choice.replace(" بيكسل", "p")
        video = yt.streams.filter(res=resolution, file_extension="mp4", progressive=True).first()
        
        if not video:
            await update.message.reply_text("⚠️ الجودة غير متوفرة! يرجى اختيار جودة أخرى.")
            return
        
        progress_msg = await update.message.reply_text(f"⏳ جاري تحميل الفيديو بجودة {quality_choice}...\n▢▢▢▢▢▢▢▢▢▢ 0%")
        context.user_data['progress_msg_id'] = progress_msg.message_id
        
        file = video.download(output_path=DOWNLOAD_FOLDER)
        
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=progress_msg.message_id
        )
        
        await update.message.reply_video(
            video=open(file, 'rb'),
            supports_streaming=True,
            caption=f"🎥 {yt.title}\nالجودة: {quality_choice}"
        )
        os.remove(file)
    
    except Exception as e:
        await update.message.reply_text("❌ فشل تحميل الفيديو! يرجى المحاولة مرة أخرى.")
        print(f"Error: {e}")
    
    finally:
        context.user_data['awaiting_quality'] = False

# ========== تشغيل البوت ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^https?://'), handle_video_link))
    app.add_handler(MessageHandler(filters.Regex(r'^(مقطع صوتي|فيديو)'), handle_choice))
    app.add_handler(MessageHandler(filters.Regex(r'^(\d{3} بيكسل)'), handle_quality))
    
    print("✅ البوت يعمل...")
    app.run_polling()

if __name__ == '__main__':
    main()