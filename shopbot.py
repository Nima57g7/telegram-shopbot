#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اطلاعات محصولات
PRODUCTS = {
    'mafia': {
        'name': 'چیت بازی شب‌های مافیا',
        'price': '450,000 تومان',
        'card_number': '6037-9972-1234-5678'  # شماره کارت موقت
    },
    'zodiac': {
        'name': 'چیت بازی شب‌های مافیا زودیاک',
        'price': '550,000 تومان',
        'card_number': '6219-8612-3456-7890'  # شماره کارت موقت
    }
}

# مشخصات شما
SUPPORT_ID = '@redhotmafia'  # آیدی پشتیبانی
ADMIN_ID = 7641419665  # آیدی عددی شما
BOT_TOKEN = '8011890168:AAFiNKP-hd_YASbRTMRdg_8BhGaFWcX8KFM'  # توکن ربات

# تابع ایجاد کیبورد محصولات
def products_keyboard():
    keyboard = [
        [InlineKeyboardButton(PRODUCTS['mafia']['name'], callback_data='mafia')],
        [InlineKeyboardButton(PRODUCTS['zodiac']['name'], callback_data='zodiac')]
    ]
    return InlineKeyboardMarkup(keyboard)

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"سلام {user.first_name} 👋\n"
        "به ربات فروش چیت بازی‌های شب‌های مافیا خوش آمدید.\n"
        "لطفا محصول مورد نظر خود را انتخاب کنید:",
        reply_markup=products_keyboard()
    )

# نمایش جزئیات محصول
async def product_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    product = PRODUCTS[query.data]
    message = (
        f"🛍 محصول: {product['name']}\n"
        f"💰 قیمت: {product['price']}\n\n"
        f"💳 لطفا مبلغ را به شماره کارت زیر واریز کنید:\n"
        f"{product['card_number']}\n\n"
        "پس از واریز، لطفا تصویر فیش واریزی را ارسال کنید."
    )
    
    await query.edit_message_text(text=message)

# پردازش فیش واریزی
async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.photo:
        context.user_data['payment_received'] = True
        user = update.effective_user
        
        # اطلاع به ادمین
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📌 پرداخت جدید از کاربر:\n"
                 f"👤 نام: {user.full_name}\n"
                 f"🆔 آیدی: {user.id}\n"
                 f"📷 فیش واریزی ارسال شده است."
        )
        
        await update.message.reply_text(
            "✅ فیش واریزی دریافت شد.\n"
            "لطفا منتظر بمانید تا پرداخت شما بررسی و تایید شود."
        )
        
        logger.info(f"پرداخت جدید از کاربر {user.id} ({user.full_name})")
    else:
        await update.message.reply_text("لطفا تصویر فیش واریزی را ارسال کنید.")

# تایید پرداخت (فقط برای ادمین)
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id == ADMIN_ID:
        user_id = context.args[0] if context.args else None
        if user_id:
            try:
                user_id = int(user_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ پرداخت شما تایید شد.\n\n"
                         f"🛒 کد پیگیری: TC-{user_id}\n\n"
                         f"لطفا این کد را به پشتیبانی ما ارسال کنید:\n"
                         f"{SUPPORT_ID}\n\n"
                         "تا محصول را دریافت کنید.\n"
                         "با تشکر از خرید شما! 🤝"
                )
                await update.message.reply_text("✅ تایید پرداخت برای کاربر ارسال شد.")
            except (ValueError, IndexError):
                await update.message.reply_text("⚠️ لطفا آیدی کاربر را وارد کنید:\n/confirm <user_id>")
        else:
            await update.message.reply_text("⚠️ لطفا آیدی کاربر را وارد کنید:\n/confirm <user_id>")
    else:
        await update.message.reply_text("⛔ دسترسی غیرمجاز!")

# مدیریت خطاها
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("خطا در پردازش درخواست:", exc_info=context.error)
    if isinstance(update, Update):
        await update.message.reply_text('⚠️ متاسفانه خطایی رخ داده است. لطفا دوباره تلاش کنید.')

# تابع کمکی برای ادمین
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "🔧 دستورات ادمین:\n"
            "/confirm <user_id> - تایید پرداخت کاربر\n"
            "/stats - آمار ربات"
        )

# تابع اصلی
def main() -> None:
    # ساخت Application با توکن شما
    application = Application.builder().token(BOT_TOKEN).build()

    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("confirm", confirm_payment))
    application.add_handler(CommandHandler("admin", admin_help))
    application.add_handler(CallbackQueryHandler(product_details, pattern='^(mafia|zodiac)$'))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt))
    
    # ثبت هندلر خطاها
    application.add_error_handler(error_handler)

    # شروع ربات
    application.run_polling()
    logger.info("ربات با موفقیت شروع به کار کرد...")

if __name__ == '__main__':
    main()
