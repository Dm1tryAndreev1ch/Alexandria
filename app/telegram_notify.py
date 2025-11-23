"""Модуль для отправки уведомлений администраторам через Telegram"""
import asyncio
from app import create_app, db
from app.models import User


async def send_notification_to_admins_async(message: str, username: str = None):
    """Асинхронная отправка уведомления всем администраторам"""
    try:
        from telegram_bot.bot import bot_application
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        if not bot_application:
            print("Bot application not initialized. Cannot send notification.")
            return
        
        app = create_app()
        with app.app_context():
            # Получаем всех администраторов с telegram_id
            admins = User.query.filter_by(is_admin=True).filter(User.telegram_id.isnot(None)).all()
            
            if not admins:
                print("No admins with telegram_id found. Cannot send notification.")
                return
            
            bot = bot_application.bot
            
            # Создаем клавиатуру с кнопками, если указан username
            reply_markup = None
            if username:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{username}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{username}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            for admin in admins:
                try:
                    await bot.send_message(
                        chat_id=admin.telegram_id,
                        text=message,
                        reply_markup=reply_markup
                    )
                    print(f"Notification sent to admin {admin.username} (telegram_id: {admin.telegram_id})")
                except Exception as e:
                    print(f"Error sending notification to admin {admin.username}: {e}")
    
    except Exception as e:
        print(f"Error in send_notification_to_admins_async: {e}")


def send_notification_to_admins(message: str, username: str = None):
    """Синхронная обертка для отправки уведомления администраторам"""
    try:
        # Используем threading для запуска асинхронной функции в отдельном потоке
        import threading
        
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_notification_to_admins_async(message, username))
                loop.close()
            except Exception as e:
                print(f"Error in async notification thread: {e}")
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"Error in send_notification_to_admins: {e}")

