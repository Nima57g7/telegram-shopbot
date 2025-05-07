#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random
import aiosqlite
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# تنظیمات پیشرفته
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل گفتگو
SELECTING_ACTION, CONFIRM_PAYMENT, ADMIN_ACTIONS = range(3)

# اطلاعات محصولات
PRODUCTS = {
    'mafia': {
        'name': 'چیت بازی شب های مافیا',
        'price': '450,000 تومان',
        'card_number': '6037-9972-XXXX-XXXX',
        'description': 'نمایش نقش‌های مخفی بازیکنان'
    },
    'zodiac': {
        'name': 'چیت بازی شب های مافیا زودیاک',
        'price': '550,000 تومان',
        'card_number': '6219-8612-XXXX-XXXX',
        'description': 'نمایش نقش‌های مخفی بازیکنان'
    }
}

ADMIN_ID = 7641419665  # بهتر است از متغیر محیطی استفاده شود
SUPPORT_ID = "@redhotmafia"
BOT_TOKEN = "8011890168:AAFiNKP-hd_YASbRTMRdg_8BhGaFWcX8KFM"

# ذخیره سفارش در دیتابیس
async def save_order(user, product, tracking_code, photo_id, status="pending"):
    try:
        async with aiosqlite.connect("orders.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    user_id INTEGER,
                    full_name TEXT,
                    product TEXT,
                    price TEXT,
                    tracking_code TEXT PRIMARY KEY,
                    photo_id TEXT,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                INSERT INTO orders (user_id, full_name, product, price, tracking_code, photo_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user.id, user.full_name, product['name'], product['price'], tracking_code, photo_id, status))
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving order: {e}")
        raise

# مشاهده سفارشات برای ادمین
async def view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("🚫 دسترسی محدود شد!")
            return

        async with aiosqlite.connect("orders.db") as db:
            async with db.execute("""
                SELECT rowid, user_id, full_name, product, price, tracking_code, photo_id, status 
                FROM orders 
                ORDER BY timestamp DESC 
                LIMIT 10
            """) as cursor:
                rows = await cursor.fetchall()
                if not rows:
                    await update.message.reply_text("هیچ سفارشی یافت نشد.")
                    return
                
                for row in rows:
                    rowid, user_id, name, product, price, code, photo_id, status = row
                    status_icon = "✅" if status == "confirmed" else "🕒" if status == "pending" else "❌"
                    
                    msg = f"""
📋 سفارش #{rowid}
━━━━━━━━━━━━━━━━
👤 کاربر: {name} ({user_id})
📦 محصول: {product}
💰 مبلغ: {price}
🔖 کد پیگیری: {code}
{status_icon} وضعیت: {status}
"""
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ تایید", callback_data=f"confirm_{rowid}"),
                            InlineKeyboardButton("❌ حذف", callback_data=f"delete_{rowid}")
                        ]
                    ]
                    try:
                        await context.bot.send_photo(
                            chat_id=ADMIN_ID,
                            photo=photo_id,
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logger.error(f"Error sending order info: {e}")
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"خطا در ارسال عکس سفارش #{rowid}\n{msg}",
                            reply_markup=InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"Error in view_orders: {e}")
        await update.message.reply_text("⚠️ خطایی در مشاهده سفارشات رخ داد!")

# تایید سفارش توسط ادمین
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("🚫 دسترسی محدود شد!")
            return
        
        order_id = query.data.split('_')[1]
        
        async with aiosqlite.connect("orders.db") as db:
            await db.execute("UPDATE orders SET status = 'confirmed' WHERE rowid = ?", (order_id,))
            await db.commit()
            
            # دریافت اطلاعات سفارش برای ارسال به کاربر
            async with db.execute("SELECT user_id, tracking_code FROM orders WHERE rowid = ?", (order_id,)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    await query.edit_message_text("⚠️ سفارش یافت نشد!")
                    return
                    
                user_id, tracking_code = result
                
                user_msg = f"""
✅ سفارش شما تایید شد!
━━━━━━━━━━━━━━━━
🔖 کد پیگیری: {tracking_code}
📞 پشتیبانی: {SUPPORT_ID}
"""
                try:
                    await context.bot.send_message(chat_id=user_id, text=user_msg)
                except Exception as e:
                    logger.error(f"Failed to send confirmation to user {user_id}: {e}")
        
        await query.edit_message_text(f"✅ سفارش #{order_id} با موفقیت تایید شد!")
        await view_orders(update, context)
    except Exception as e:
        logger.error(f"Error in confirm_order: {e}")
        await query.edit_message_text("⚠️ خطایی در تایید سفارش رخ داد!")

# حذف سفارش توسط ادمین
async def delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("🚫 دسترسی محدود شد!")
            return
        
        order_id = query.data.split('_')[1]
        
        async with aiosqlite.connect("orders.db") as db:
            await db.execute("DELETE FROM orders WHERE rowid = ?", (order_id,))
            await db.commit()
        
        await query.edit_message_text(f"✅ سفارش #{order_id} با موفقیت حذف شد!")
        await view_orders(update, context)
    except Exception as e:
        logger.error(f"Error in delete_order: {e}")
        await query.edit_message_text("⚠️ خطایی در حذف سفارش رخ داد!")

# استارت ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        welcome_msg = f"""
🎮 خوش آمدید به ربات Red Hot Mafia!
━━━━━━━━━━━━━━━━
👤 نام: {user.first_name}
🆔 آی‌دی: {user.id}
"""
        await update.message.reply_text(welcome_msg)

        keyboard = [
            [InlineKeyboardButton(PRODUCTS['mafia']['name'], callback_data='mafia')],
            [InlineKeyboardButton(PRODUCTS['zodiac']['name'], callback_data='zodiac')],
            [InlineKeyboardButton("🔐 پنل ادمین", callback_data='admin')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "لطفا محصول مورد نظر را انتخاب کنید:",
            reply_markup=reply_markup
        )
        return SELECTING_ACTION
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("⚠️ خطایی در شروع ربات رخ داد!")
        return ConversationHandler.END

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        product = PRODUCTS[query.data]
        product_info = f"""
📦 اطلاعات محصول
━━━━━━━━━━━━━━━━
🔹 نام: {product['name']}
💰 قیمت: {product['price']}
📝 توضیحات: {product['description']}

💳 اطلاعات پرداخت
━━━━━━━━━━━━━━━━
🔸 شماره کارت: {product['card_number']}
"""
        keyboard = [
            [InlineKeyboardButton("✅ تایید پرداخت", callback_data=f'pay_{query.data}')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back')]
        ]

        await query.edit_message_text(
            product_info,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in show_product: {e}")
        await query.edit_message_text("⚠️ خطایی در نمایش محصول رخ داد!")

async def payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        product_type = query.data.split('_')[1]
        product = PRODUCTS[product_type]

        context.user_data['selected_product'] = product_type

        payment_msg = f"""
💳 دستورالعمل پرداخت
━━━━━━━━━━━━━━━━
1. مبلغ {product['price']} را به شماره کارت زیر واریز کنید:
{product['card_number']}

2. تصویر فیش پرداخت را ارسال کنید
3. منتظر تایید باشید
"""
        await query.edit_message_text(payment_msg)
        return CONFIRM_PAYMENT
    except Exception as e:
        logger.error(f"Error in payment_confirmation: {e}")
        await query.edit_message_text("⚠️ خطایی در نمایش اطلاعات پرداخت رخ داد!")
        return SELECTING_ACTION

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.photo:
            await update.message.reply_text("⚠️ لطفا تصویر فیش پرداخت را ارسال کنید")
            return CONFIRM_PAYMENT

        user = update.effective_user
        product_type = context.user_data.get('selected_product')
        if not product_type:
            await update.message.reply_text("⚠️ خطا در دریافت اطلاعات محصول")
            return ConversationHandler.END

        product = PRODUCTS.get(product_type)
        if not product:
            await update.message.reply_text("⚠️ محصول انتخاب شده نامعتبر است")
            return ConversationHandler.END

        tracking_code = f"RHMAF-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000,9999)}"
        photo_file_id = update.message.photo[-1].file_id

        await save_order(user, product, tracking_code, photo_file_id)

        admin_msg = f"""
🆕 پرداخت جدید
━━━━━━━━━━━━━━━━
👤 کاربر: {user.full_name}
🆔 آی‌دی: {user.id}
📦 محصول: {product['name']}
💰 مبلغ: {product['price']}
🔖 کد پیگیری: {tracking_code}
"""
        await context.bot.send_photo(
            chat_id=ADMIN_ID, 
            photo=photo_file_id, 
            caption=admin_msg
        )

        user_msg = f"""
✅ پرداخت شما ثبت شد!
━━━━━━━━━━━━━━━━
🔖 کد پیگیری: {tracking_code}
📞 پشتیبانی: {SUPPORT_ID}

لطفا کد پیگیری را به پشتیبانی ارسال کنید.
"""
        await update.message.reply_text(user_msg)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in handle_receipt: {e}")
        await update.message.reply_text("⚠️ خطایی در پردازش فیش پرداخت رخ داد!")
        return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("🚫 دسترسی محدود شد!")
            return SELECTING_ACTION

        admin_menu = """
🔐 پنل ادمین
━━━━━━━━━━━━━━━━
1. مشاهده سفارشات اخیر
/orders

2. تایید/حذف سفارشات
از طریق دکمه‌های زیر اقدام کنید
"""
        keyboard = [
            [InlineKeyboardButton("📋 مشاهده سفارشات", callback_data='view_orders')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='back')]
        ]

        await query.edit_message_text(
            admin_menu,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ADMIN_ACTIONS
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        await query.edit_message_text("⚠️ خطایی در نمایش پنل ادمین رخ داد!")
        return SELECTING_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد")
    return ConversationHandler.END

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                SELECTING_ACTION: [
                    CallbackQueryHandler(show_product, pattern='^(mafia|zodiac)$'),
                    CallbackQueryHandler(payment_confirmation, pattern='^pay_'),
                    CallbackQueryHandler(admin_panel, pattern='^admin$'),
                    CallbackQueryHandler(start, pattern='^back$')
                ],
                CONFIRM_PAYMENT: [
                    MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt),
                ],
                ADMIN_ACTIONS: [
                    CallbackQueryHandler(view_orders, pattern='^view_orders$'),
                    CallbackQueryHandler(confirm_order, pattern='^confirm_'),
                    CallbackQueryHandler(delete_order, pattern='^delete_'),
                    CallbackQueryHandler(start, pattern='^back$')
                ]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('orders', view_orders))

        logger.info("""
███████╗██████╗ ███████╗██████╗ ██╗  ██╗ ██████╗ ████████╗
██╔════╝██╔══██╗██╔════╝██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝
█████╗  ██████╔╝█████╗  ██║  ██║███████║██║   ██║   ██║   
██╔══╝  ██╔══██╗██╔══╝  ██║  ██║██╔══██║██║   ██║   ██║   
███████╗██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝   ██║   
╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ╚═╝   
        """)

        application.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
