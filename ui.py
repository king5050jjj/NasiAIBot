from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu(owner=False):
    rows = [
        [InlineKeyboardButton("💬 چت هوشمند", callback_data="chat"),
         InlineKeyboardButton("📝 ابزار متن", callback_data="text")],
        [InlineKeyboardButton("🖼️ تصویر", callback_data="image"),
         InlineKeyboardButton("🎙️ صدا", callback_data="voice")],
        [InlineKeyboardButton("🎬 ویدیو", callback_data="video"),
         InlineKeyboardButton("✨ انیمیشن", callback_data="animation")],
        [InlineKeyboardButton("📁 فایل", callback_data="file"),
         InlineKeyboardButton("🌐 وب", callback_data="web")],
        [InlineKeyboardButton("🧠 حافظه و یادگیری", callback_data="memory"),
         InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("👤 حساب من", callback_data="account")]
    ]
    if owner:
        rows.append([InlineKeyboardButton("👑 پنل مالک", callback_data="owner")])
    return InlineKeyboardMarkup(rows)

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="home")]])
