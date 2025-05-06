async def handle_video_link(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        return
    
    url = update.message.text
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            yt = YouTube(url)
            yt.register_on_progress_callback(lambda s, c, br: download_progress(s, c, br, update, context))
            context.user_data['yt'] = yt
            
            info = (
                f"📌 **العنوان**: {yt.title}\n"
                f"⏳ **المدة**: {str(timedelta(seconds=yt.length))}\n"
                f"👀 **المشاهدات**: {yt.views:,}\n"
                f"📊 **خيارات التحميل**:\n"
                f"   - مقطع صوتي (جودة صوت عالية)\n"
                f"   - فيديو مع جودة قابلة للاختيار"
            )
            await update.message.reply_text(info, parse_mode="Markdown")
            
            buttons = ReplyKeyboardMarkup([["مقطع صوتي 🎵", "فيديو 🎥"]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("اختر نوع التحميل المطلوب:", reply_markup=buttons)
            
        except Exception as e:
            await update.message.reply_text("⚠ حدث خطأ في معالجة الفيديو! يرجى المحاولة لاحقًا.")
    else:
        await update.message.reply_text("⚠ الرابط غير صالح! يرجى إرسال رابط يوتيوب صحيح.")

async def handle_format_choice(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        return
    
    choice = update.message.text
    yt = context.user_data.get('yt')
    
    if not yt:
        await update.message.reply_text("⚠ يرجى إرسال الرابط أولاً!")
        return
    
    if "صوتي" in choice:  # يتطابق مع "مقطع صوتي 🎵"
        try:
            audio = yt.streams.filter(only_audio=True).first()
            progress_msg = await update.message.reply_text("⏳ جاري تحضير المقطع الصوتي...\n▢▢▢▢▢▢▢▢▢▢ 0%")
            context.user_data['progress_msg_id'] = progress_msg.message_id
            
            file = audio.download(output_path=DOWNLOAD_FOLDER)
            mp3_file = file.replace(".mp4", ".mp3")
            os.rename(file, mp3_file)
            
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=progress_msg.message_id)
            await update.message.reply_audio(
                audio=open(mp3_file, 'rb'),
                title=yt.title,
                performer="تم التحميل بواسطة البوت"
            )
            os.remove(mp3_file)
            
        except Exception as e:
            await update.message.reply_text("❌ فشل التحميل! يرجى المحاولة بفيديو آخر.")

    elif "فيديو" in choice:  # يتطابق مع "فيديو 🎥"
        streams = yt.streams.filter(file_extension="mp4", progressive=True).order_by('resolution')
        buttons = []
        for stream in streams:
            size_mb = round(stream.filesize / (1024 * 1024), 2)
            quality = stream.resolution.replace('p', ' بيكسل')
            buttons.append([f"{quality} (~{size_mb} ميجابايت)"])
        
        if not buttons:
            await update.message.reply_text("⚠ لا تتوفر جودات متاحة لهذا الفيديو!")
            return
        
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("اختر جودة الفيديو المناسبة:", reply_markup=reply_markup)
        context.user_data['awaiting_quality'] = True

async def handle_quality_choice(update: Update, context: CallbackContext):
    if not await check_subscription(update, context):
        return
    
    if not context.user_data.get('awaiting_quality'):
        return
    
    quality_choice = update.message.text.split()[0]  # استخراج الدقة (مثال: "720 بيكسل")
    yt = context.user_data.get('yt')
    
    try:
        resolution = quality_choice.replace(" بيكسل", "p")
        video = yt.streams.filter(res=resolution, file_extension="mp4", progressive=True).first()
        
        if not video:
            await update.message.reply_text("⚠ الجودة غير متوفرة! يرجى اختيار جودة أخرى.")
            return
        
        progress_msg = await update.message.reply_text(f"⏳ جاري تحميل الفيديو بجودة {quality_choice}...\n▢▢▢▢▢▢▢▢▢▢ 0%")
        context.user_data['progress_msg_id'] = progress_msg.message_id
        
        file = video.download(output_path=DOWNLOAD_FOLDER)
        
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=progress_msg.message_id)
        await update.message.reply_video(
            video=open(file, 'rb'),
            supports_streaming=True,
            caption=f"🎥 {yt.title}\nالجودة: {quality_choice}"
        )
        os.remove(file)
    
    except Exception as e:
        await update.message.reply_text("❌ فشل تحميل الفيديو! يرجى المحاولة مرة أخرى.")
    
    finally:
        context.user_data['awaiting_quality'] = False