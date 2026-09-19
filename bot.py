import asyncio
import os
import uuid
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

from config import settings
from db import init_db
from memory import ensure_user, add_memory, get_memories, clear_memories, log_usage
from ai import AIProvider
from web import WebProvider
from ui import main_menu, back_menu
from prompts import SYSTEM_PROMPT
from files import extract_text

ai = AIProvider()
web = WebProvider(ai)

STORAGE = Path("storage")
STORAGE.mkdir(exist_ok=True)


def set_mode(context, mode: str):
    context.user_data["mode"] = mode


def get_mode(context) -> str:
    return context.user_data.get("mode", "chat")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update.effective_user.id)
    context.user_data.clear()
    owner = update.effective_user.id == settings.owner_id
    await update.message.reply_text(
        "🤖 سلام! من دستیار هوش مصنوعی شخصی تو هستم.\nیک قابلیت را انتخاب کن:",
        reply_markup=main_menu(owner),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    if data == "home":
        context.user_data.clear()
        await q.edit_message_text("🏠 منوی اصلی:", reply_markup=main_menu(uid == settings.owner_id))
        return

    if data == "owner" and uid != settings.owner_id:
        await q.edit_message_text("⛔ دسترسی مجاز نیست.", reply_markup=back_menu())
        return

    if data == "memory":
        rows = await get_memories(uid, 10)
        text = "🧠 حافظه اخیر:\n" + ("\n".join(f"• {x.content}" for x in rows) if rows else "خالی است.")
        kb = [[InlineKeyboardButton("🗑️ پاک‌کردن حافظه", callback_data="clear_memory")],
              [InlineKeyboardButton("🔙 برگشت", callback_data="home")]]
        await q.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "clear_memory":
        await clear_memories(uid)
        await q.edit_message_text("🗑️ حافظه شخصی پاک شد.", reply_markup=back_menu())
        return

    if data == "settings":
        await q.edit_message_text(
            "⚙️ تنظیمات فعلی:\n"
            f"🤖 مدل چت: {settings.chat_model or 'gpt-5.6-luna'}\n"
            f"🎨 مدل تصویر: {settings.image_model or 'gpt-image-1'}\n"
            f"🎬 مدل ویدیو: {settings.video_model}\n"
            "🔐 کلیدهای API فقط در Railway Variables نگهداری می‌شوند.",
            reply_markup=back_menu(),
        )
        return

    if data == "account":
        await q.edit_message_text(
            f"👤 حساب شما\n🆔 Telegram ID: {uid}\n🧠 حافظه شخصی فعال است.",
            reply_markup=back_menu(),
        )
        return

    if data == "owner":
        await q.edit_message_text(
            "👑 پنل مالک\n\nربات فعال است. برای مدیریت API و دیتابیس از Railway Variables استفاده کن.",
            reply_markup=back_menu(),
        )
        return

    labels = {
        "chat": ("chat", "💬 چت هوشمند فعال شد. پیام بعدی‌ات را بفرست."),
        "text": ("text", "📝 ابزار متن فعال شد. متن یا درخواستت را بفرست؛ بازنویسی، خلاصه، ترجمه و اصلاح انجام می‌دهم."),
        "image": ("image", "🖼️ تصویر فعال شد. توضیح تصویر را بفرست. اگر عکس بفرستی، می‌توانم آن را تحلیل یا ویرایش کنم."),
        "voice": ("voice", "🎙️ یک Voice بفرست تا به متن تبدیل شود؛ یا متن بفرست تا برایت صوت بسازم."),
        "video": ("video", "🎬 توضیح ویدیوی موردنظر را بفرست. تولید ویدیو با LTX در Hugging Face انجام می‌شود."),
        "animation": ("animation", "✨ توضیح انیمیشن را بفرست. تصویر هم می‌توانی همراهش بفرستی."),
        "file": ("file", "📁 فایل PDF/Word/TXT/CSV/XLSX بفرست تا متنش استخراج و برای سؤال‌و‌جواب آماده شود."),
        "web": ("web", "🌐 سؤال یا عبارت جست‌وجو را بفرست تا با جست‌وجوی وب پاسخ بدهم."),
    }
    if data in labels:
        mode, message = labels[data]
        set_mode(context, mode)
        await q.edit_message_text(message, reply_markup=back_menu())
        return

    await q.edit_message_text("انتخاب شد.", reply_markup=back_menu())


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await ensure_user(uid)
    text = (update.message.text or "").strip()
    mode = get_mode(context)
    await log_usage(uid, mode)

    lowered = text.lower()
    if any(x in lowered for x in ["یاد بگیر", "یادت باشه", "remember", "learn this"]):
        await add_memory(uid, text, "user_learning", 0.9)

    memories = await get_memories(uid, 12)
    memory_text = "\n".join(x.content for x in memories)

    try:
        if mode == "image":
            data = await ai.generate_image(text)
            await update.message.reply_photo(data, caption="🖼️ تصویر ساخته شد.")
            return

        if mode == "voice":
            data = await ai.text_to_speech(text)
            await update.message.reply_voice(data, caption="🔊 صوت ساخته شد.")
            return

        if mode == "video":
            await update.message.reply_text("🎬 تولید ویدیو شروع شد؛ ممکن است چند دقیقه طول بکشد...")
            data = await ai.generate_video(text)
            await update.message.reply_video(data, caption="🎬 ویدیو آماده شد.", supports_streaming=True)
            return

        if mode == "animation":
            await update.message.reply_text("✨ ساخت انیمیشن شروع شد؛ لطفاً صبر کن...")
            data = await ai.generate_animation(text)
            await update.message.reply_video(data, caption="✨ انیمیشن آماده شد.", supports_streaming=True)
            return

        if mode == "web":
            result = await web.search(text)
            answer = result[0]["snippet"] if result else "نتیجه‌ای پیدا نشد."
            await update.message.reply_text(answer[:4000])
            return

        if mode == "text":
            instruction = (
                "You are a professional Persian/Dari writing assistant. Perform the user's requested writing task "
                "such as rewrite, summarize, translate, correct, format, or generate text. Preserve meaning.\n\n"
                f"Request: {text}\n\n"
                f"Memory/context:\n{memory_text}"
            )
        else:
            instruction = f"{SYSTEM_PROMPT}\nUser memory:\n{memory_text}\n\nUser:\n{text}"

        answer = await ai.chat(instruction, context=memory_text)
        await update.message.reply_text(answer[:4000])
    except Exception as exc:
        await update.message.reply_text(f"❌ خطا در اجرای این قابلیت:\n{str(exc)[:1500]}")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    doc = update.message.document
    if not doc:
        return
    if doc.file_size and doc.file_size > settings.max_file_mb * 1024 * 1024:
        await update.message.reply_text(f"❌ حجم فایل بیشتر از {settings.max_file_mb}MB است.")
        return
    path = STORAGE / f"{uid}_{uuid.uuid4().hex}_{doc.file_name}"
    try:
        tgfile = await doc.get_file()
        await tgfile.download_to_drive(str(path))
        content = extract_text(str(path))
        await add_memory(uid, f"File knowledge: {content[:10000]}", "file", 0.7)
        mode = get_mode(context)
        if mode == "file" and content:
            answer = await ai.chat(
                f"این محتوای فایل است. آن را خلاصه و نکات مهمش را به زبان کاربر توضیح بده:\n\n{content[:30000]}"
            )
            await update.message.reply_text(answer[:4000])
        else:
            await update.message.reply_text("📁 فایل دریافت شد و متن آن وارد حافظه شد. حالا درباره فایل سؤال بپرس.")
    except Exception as exc:
        await update.message.reply_text(f"❌ پردازش فایل نشد: {str(exc)[:1500]}")
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await ensure_user(uid)
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    path = STORAGE / f"{uid}_{uuid.uuid4().hex}.ogg"
    try:
        tgfile = await voice.get_file()
        await tgfile.download_to_drive(str(path))
        await update.message.reply_text("🎙️ در حال تبدیل صدا به متن...")
        text = await ai.transcribe(str(path))
        if not text:
            await update.message.reply_text("❌ متنی از صدا دریافت نشد.")
            return
        await update.message.reply_text(f"📝 متن صدا:\n{text[:4000]}")
        await add_memory(uid, f"Voice transcript: {text[:5000]}", "voice", 0.8)
        if get_mode(context) == "chat":
            answer = await ai.chat(f"{SYSTEM_PROMPT}\nUser said by voice:\n{text}")
            await update.message.reply_text(answer[:4000])
    except Exception as exc:
        await update.message.reply_text(f"❌ تبدیل صدا انجام نشد:\n{str(exc)[:1500]}")
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    photos = update.message.photo
    if not photos:
        return
    path = STORAGE / f"{uid}_{uuid.uuid4().hex}.jpg"
    try:
        tgfile = await photos[-1].get_file()
        await tgfile.download_to_drive(str(path))
        caption = (update.message.caption or "").strip()
        mode = get_mode(context)
        if mode in {"image", "animation"} and caption:
            await update.message.reply_text("🖼️ در حال ویرایش/تبدیل تصویر...")
            data = await (ai.generate_animation(caption, str(path)) if mode == "animation" else ai.edit_image(str(path), caption))
            if mode == "animation":
                await update.message.reply_video(data, caption="✨ انیمیشن ساخته شد.")
            else:
                await update.message.reply_photo(data, caption="🖼️ تصویر ویرایش شد.")
            return
        prompt = caption or "این تصویر را دقیق و کامل توصیف کن و اگر متن دارد آن را بخوان."
        answer = await ai.analyze_image(str(path), prompt)
        await update.message.reply_text(answer[:4000])
    except Exception as exc:
        await update.message.reply_text(f"❌ پردازش تصویر انجام نشد:\n{str(exc)[:1500]}")
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


async def error_handler(update, context):
    print("ERROR:", repr(context.error))


async def run_bot():
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing")
    if not settings.owner_id:
        print("WARNING: OWNER_ID is not set; owner-only controls will be unavailable.")
    await init_db()
    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    print("Bot started.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
