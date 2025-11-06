#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ZAZA Telegram Bot - Система обратной связи
Поддерживает несколько ботов с разными токенами
"""

import logging
import asyncio
import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import requests
import uuid
import shutil
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Импорт моделей БД из нашего проекта
from database import ActiveTicket, User

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
class States(Enum):
    CATEGORY_SELECTION = 1
    # Проблемы с оплатой криптовалютой
    CRYPTO_ORDER_NUMBER = 10
    # Диспут
    DISPUTE_ORDER_NUMBER = 20
    DISPUTE_VIDEO = 21
    DISPUTE_PHOTOS = 22
    DISPUTE_DESCRIPTION = 23
    DISPUTE_MESSAGES = 24
    # Общие вопросы
    GENERAL_QUESTION = 30
    # Трудоустройство
    JOB_ABOUT = 40

@dataclass
class TicketData:
    """Временное хранение данных тикета"""
    category: str
    user_id: int
    username: str
    data: Dict[str, Any]

class ZAZABot:
    """Основной класс бота ZAZA"""
    
    def __init__(self, bot_token: str, bot_id: int = None):
        self.bot_token = bot_token
        self.bot_id = bot_id
        self.application = None
        self.db_session = None
        
        # Временное хранение данных тикетов
        self.ticket_data: Dict[int, TicketData] = {}
        
        # Настройка БД
        self.setup_database()
        
        # Настройка приложения
        self.setup_application()

    def setup_database(self):
        """Настройка подключения к БД"""
        # Используем ту же настройку, что и админка
        from database import engine, SessionLocal
        from sqlalchemy.orm import sessionmaker
        
        self.engine = engine
        self.session_maker = SessionLocal

    async def download_telegram_file(self, file_id: str, file_type: str) -> Optional[dict]:
        """Скачивает файл из Telegram и сохраняет на сервере"""
        try:
            # Получаем информацию о файле
            get_file_url = f"https://api.telegram.org/bot{self.bot_token}/getFile"
            get_file_response = requests.get(get_file_url, params={"file_id": file_id})
            
            if get_file_response.status_code != 200:
                logger.error(f"Ошибка получения информации о файле: {get_file_response.text}")
                return None
            
            file_info = get_file_response.json()["result"]
            file_path = file_info["file_path"]
            file_size = file_info.get("file_size", 0)
            
            # Проверяем размер файла (Telegram Bot API ограничение 20 МБ)
            max_size_mb = 20
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                logger.warning(f"Файл слишком большой для скачивания: {file_size / (1024*1024):.1f} МБ (максимум {max_size_mb} МБ)")
                return None
            
            # Создаем уникальное имя файла
            file_extension = Path(file_path).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Определяем папку для сохранения
            media_folder = {
                "photo": "photos",
                "video": "videos", 
                "document": "documents"
            }.get(file_type, "documents")
            
            # Создаем путь для сохранения в backend/media/
            backend_dir = Path(__file__).parent  # Папка где находится bot.py
            save_dir = backend_dir / "media" / media_folder
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / unique_filename
            
            # Скачиваем файл
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            download_response = requests.get(download_url, stream=True)
            
            if download_response.status_code != 200:
                logger.error(f"Ошибка скачивания файла: {download_response.text}")
                return None
            
            # Сохраняем файл
            with open(save_path, "wb") as f:
                shutil.copyfileobj(download_response.raw, f)
            
            return {
                "local_path": f"{media_folder}/{unique_filename}",  # Относительный путь от media/
                "original_filename": Path(file_path).name,
                "file_size": file_size
            }
            
        except Exception as e:
            logger.error(f"Исключение при скачивании файла: {e}")
            return None

    def setup_application(self):
        """Настройка Telegram Application"""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Основной conversation handler для создания тикетов
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_command)],
            states={
                States.CATEGORY_SELECTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.category_selected)
                ],
                # Проблемы с оплатой криптовалютой
                States.CRYPTO_ORDER_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.crypto_order_number)
                ],
                # Диспут
                States.DISPUTE_ORDER_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dispute_order_number)
                ],
                States.DISPUTE_VIDEO: [
                    MessageHandler(filters.VIDEO | filters.TEXT, self.dispute_video)
                ],
                States.DISPUTE_PHOTOS: [
                    MessageHandler(filters.PHOTO | filters.TEXT, self.dispute_photos)
                ],
                States.DISPUTE_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dispute_description)
                ],
                States.DISPUTE_MESSAGES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dispute_messages),
                    MessageHandler(filters.PHOTO, self.dispute_messages),
                    MessageHandler(filters.VIDEO, self.dispute_messages),
                    MessageHandler(filters.Document.ALL, self.dispute_messages),
                    CommandHandler('finish', self.finish_dispute)
                ],
                # Общие вопросы
                States.GENERAL_QUESTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.general_question)
                ],
                # Трудоустройство
                States.JOB_ABOUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.job_about)
                ],
            },
            fallbacks=[
                CommandHandler('start', self.start_command),
                CommandHandler('cancel', self.cancel_command)
            ],
            per_chat=True
        )
        
        self.application.add_handler(conversation_handler)
        
        # Глобальный обработчик команды /start (работает всегда, даже во время разговора)
        self.application.add_handler(CommandHandler('start', self.global_start_command))
        
        # Обработчик сообщений в активных тикетах (когда тикет уже создан и идет общение)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ticket_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_ticket_message))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_ticket_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_ticket_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Проверяем наличие открытых тикетов у пользователя
        existing_ticket = await self.check_existing_ticket(user.id)
        if existing_ticket:
            await update.message.reply_text(
                f"❗️ У вас уже есть открытый тикет #{existing_ticket}\n\n"
                "Пожалуйста, дождитесь решения по текущему обращению, "
                "прежде чем создавать новое.\n\n"
                "Если у вас есть дополнительная информация по тикету, "
                "просто напишите сообщение - оно будет добавлено к обращению.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем новые данные тикета
        self.ticket_data[user.id] = TicketData(
            category="",
            user_id=user.id,
            username=user.username or user.first_name,
            data={}
        )
        
        welcome_text = f"""
🤖 Добро пожаловать в службу поддержки ZAZA!

Привет, {user.first_name}! Я помогу вам создать обращение.
Пожалуйста, выберите тематику вашего вопроса:
"""
        
        keyboard = ReplyKeyboardMarkup([
            ["💳 Проблемы с оплатой криптовалютой"],
            ["⚖️ Диспут"],
            ["❓ Общие вопросы"],
            ["💼 Трудоустройство"]
        ], resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(welcome_text, reply_markup=keyboard)
        return States.CATEGORY_SELECTION

    async def category_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик выбора категории"""
        user_id = update.effective_user.id
        category_text = update.message.text
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Произошла ошибка. Пожалуйста, начните заново с /start")
            return ConversationHandler.END
        
        if category_text == "💳 Проблемы с оплатой криптовалютой":
            self.ticket_data[user_id].category = "crypto_payment"
            
            # Создаем тикет сразу при выборе категории
            ticket_id = await self.create_ticket(user_id, "crypto_payment")
            
            await update.message.reply_text(
                f"💳 **Проблемы с оплатой криптовалютой #{ticket_id}**\n\n"
                f"✅ Ваш тикет #{ticket_id} зарегистрирован!\n\n"
                f"Укажите номер заказа, TXID (хэш) транзакции вашей на наш адрес:",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Сохраняем ID тикета
            self.ticket_data[user_id].data['ticket_id'] = ticket_id
            return States.CRYPTO_ORDER_NUMBER
            
        elif category_text == "⚖️ Диспут":
            self.ticket_data[user_id].category = "dispute"
            
            # Создаем тикет сразу при выборе категории
            ticket_id = await self.create_ticket(user_id, "dispute")
            
            await update.message.reply_text(
                f"⚖️ **Диспут #{ticket_id}**\n\n"
                f"Для того чтобы мы могли разобраться в вашей проблеме и принять по ней решение просим вас указать:\n"
                f"• **Номер заказа**\n"
                f"• **Описать проблему** одним сообщением\n"
                f"• **Приложить фотографии и видео** с распаковки посылки\n\n"
                f"Вы можете отправлять несколько сообщений. Все они будут сохранены в тикете.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Сохраняем ID тикета
            self.ticket_data[user_id].data['ticket_id'] = ticket_id
            return States.DISPUTE_MESSAGES
            
        elif category_text == "❓ Общие вопросы":
            self.ticket_data[user_id].category = "general"
            
            # Создаем тикет сразу при выборе категории
            ticket_id = await self.create_ticket(user_id, "general")
            
            await update.message.reply_text(
                f"❓ **Общие вопросы #{ticket_id}**\n\n"
                f"✅ Ваш тикет #{ticket_id} зарегистрирован!\n\n"
                f"Напишите свой вопрос и ожидайте когда вам ответят:",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Сохраняем ID тикета
            self.ticket_data[user_id].data['ticket_id'] = ticket_id
            return States.GENERAL_QUESTION
            
        elif category_text == "💼 Трудоустройство":
            self.ticket_data[user_id].category = "employment"
            
            # Создаем тикет сразу при выборе категории
            ticket_id = await self.create_ticket(user_id, "employment")
            
            await update.message.reply_text(
                f"💼 **Трудоустройство #{ticket_id}**\n\n"
                f"✅ Ваш тикет #{ticket_id} зарегистрирован!\n\n"
                f"Распишите должность на которую хотите, опыт работы и все что считаете нужным:",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Сохраняем ID тикета
            self.ticket_data[user_id].data['ticket_id'] = ticket_id
            return States.JOB_ABOUT
        
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите категорию из предложенных вариантов."
            )
            return States.CATEGORY_SELECTION

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ПРОБЛЕМЫ С ОПЛАТОЙ КРИПТОВАЛЮТОЙ" ===
    
    async def crypto_order_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение номера заказа и TXID для криптоплатежей"""
        user_id = update.effective_user.id
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Тикет не найден. Начните заново с /start")
            return ConversationHandler.END
        
        ticket_id = self.ticket_data[user_id].data.get('ticket_id')
        
        # Сохраняем сообщение в БД
        await self.save_ticket_message(ticket_id, user_id, update.message)
        
        await update.message.reply_text(
            f"✅ **Информация добавлена к тикету #{ticket_id}**\n\n"
            f"Ожидайте ответа оператора. Мы свяжемся с вами в ближайшее время!"
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ДИСПУТ" ===
    
    async def dispute_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка сообщений от клиента в рамках диспута"""
        user_id = update.effective_user.id
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Тикет не найден. Начните заново с /start")
            return ConversationHandler.END
        
        ticket_id = self.ticket_data[user_id].data.get('ticket_id')
        
        # Сохраняем сообщение в БД
        await self.save_ticket_message(ticket_id, user_id, update.message)
        
        await update.message.reply_text(
            f"✅ Сообщение добавлено к тикету #{ticket_id}\n\n"
            f"Продолжайте отправлять сообщения, фото или видео. "
            f"Когда закончите, отправьте команду /finish"
        )
        
        return States.DISPUTE_MESSAGES
    
    async def finish_dispute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Завершение диспута"""
        user_id = update.effective_user.id
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Тикет не найден.")
            return ConversationHandler.END
        
        ticket_id = self.ticket_data[user_id].data.get('ticket_id')
        
        await update.message.reply_text(
            f"✅ **Диспут #{ticket_id} успешно создан!**\n\n"
            f"Все ваши сообщения сохранены.\n"
            f"Наши специалисты рассмотрят ваше обращение и свяжутся с вами в ближайшее время.\n\n"
            f"Для создания нового обращения используйте /start"
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END
    
    async def dispute_order_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение номера заказа для диспута"""
        user_id = update.effective_user.id
        order_number = update.message.text
        
        self.ticket_data[user_id].data['order_number'] = order_number
        
        # Кнопки для видео
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 У меня есть видео", callback_data="dispute_has_video")],
            [InlineKeyboardButton("❌ Видео нет", callback_data="dispute_no_video")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
        
        await update.message.reply_text(
            "Спасибо! У вас есть **видео с распаковки товара**?",
            reply_markup=keyboard
        )
        return States.DISPUTE_VIDEO

    async def dispute_video_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора о наличии видео"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        choice = query.data
        
        if choice == "cancel":
            await query.edit_message_text("❌ Операция отменена. Для создания нового обращения используйте /start")
            del self.ticket_data[user_id]
            return ConversationHandler.END
        
        if choice == "dispute_has_video":
            await query.edit_message_text(
                "📹 Отлично! Пожалуйста, пришлите **видео с распаковки товара**:"
            )
            self.ticket_data[user_id].data['video_expected'] = True
        else:  # dispute_no_video
            await query.edit_message_text("Понятно, видео нет.")
            self.ticket_data[user_id].data['video_file_id'] = None
            self.ticket_data[user_id].data['video_expected'] = False
            
        # Переходим к фото
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 У меня есть фото", callback_data="dispute_has_photos")],
            [InlineKeyboardButton("❌ Фото нет", callback_data="dispute_no_photos")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
        
        await query.message.reply_text(
            "У вас есть **фотографии товара, посылки или документов**?",
            reply_markup=keyboard
        )
        
        # Инициализируем список для фото
        if 'photos' not in self.ticket_data[user_id].data:
            self.ticket_data[user_id].data['photos'] = []
        
        return States.DISPUTE_PHOTOS

    async def dispute_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение видео для диспута"""
        user_id = update.effective_user.id
        
        if update.message.video:
            file_id = update.message.video.file_id
            self.ticket_data[user_id].data['video_file_id'] = file_id
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 У меня есть фото", callback_data="dispute_has_photos")],
                [InlineKeyboardButton("❌ Фото нет", callback_data="dispute_no_photos")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ])
            
            await update.message.reply_text(
                "Видео получено! ✅\n\nУ вас есть **фотографии товара, посылки или документов**?",
                reply_markup=keyboard
            )
            return States.DISPUTE_PHOTOS
        else:
            await update.message.reply_text(
                "Пожалуйста, пришлите видео файл или используйте кнопки выше."
            )
            return States.DISPUTE_VIDEO

    async def dispute_photos_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора о наличии фотографий"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        choice = query.data
        
        if choice == "cancel":
            await query.edit_message_text("❌ Операция отменена. Для создания нового обращения используйте /start")
            del self.ticket_data[user_id]
            return ConversationHandler.END
        
        if choice == "dispute_has_photos":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Готово", callback_data="photos_done")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ])
            
            await query.edit_message_text(
                "📸 Отлично! Пришлите **фотографии товара, посылки или документов**.\n"
                "Можете прислать несколько фото подряд. Когда закончите, нажмите кнопку 'Готово'."
            )
            await query.message.reply_text(
                "Жду ваши фотографии...",
                reply_markup=keyboard
            )
            self.ticket_data[user_id].data['photos_expected'] = True
        else:  # dispute_no_photos
            await query.edit_message_text("Понятно, фотографий нет.")
            self.ticket_data[user_id].data['photos'] = []
            
            # Переходим к описанию
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ])
            
            await query.message.reply_text(
                "Теперь опишите **суть диспута подробно**:",
                reply_markup=keyboard
            )
            return States.DISPUTE_DESCRIPTION
            
        return States.DISPUTE_PHOTOS

    async def dispute_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение фото для диспута"""
        user_id = update.effective_user.id
        
        # Если это callback (кнопка "Готово")
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            if query.data == "cancel":
                await query.edit_message_text("❌ Операция отменена. Для создания нового обращения используйте /start")
                del self.ticket_data[user_id]
                return ConversationHandler.END
            
            elif query.data == "photos_done":
                photo_count = len(self.ticket_data[user_id].data['photos'])
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
                ])
                
                await query.edit_message_text(
                    f"Фотографии получены ({photo_count} шт.)! ✅\n\n"
                    "Теперь опишите **суть диспута подробно**:"
                )
                return States.DISPUTE_DESCRIPTION
        
        # Если это фото
        elif update.message and update.message.photo:
            file_id = update.message.photo[-1].file_id  # Берем самое большое фото
            self.ticket_data[user_id].data['photos'].append(file_id)
            await update.message.reply_text(
                f"Фото получено! ✅ (всего: {len(self.ticket_data[user_id].data['photos'])})\n"
                "Пришлите еще фото или нажмите 'Готово' для продолжения."
            )
            return States.DISPUTE_PHOTOS
        
        else:
            await update.message.reply_text(
                "Пожалуйста, пришлите фото или нажмите кнопку 'Готово'."
            )
            return States.DISPUTE_PHOTOS

    async def dispute_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение описания проблемы диспута и создание тикета"""
        user_id = update.effective_user.id
        description = update.message.text
        
        self.ticket_data[user_id].data['description'] = description
        
        # Создаем тикет в БД
        ticket_id = await self.create_ticket(user_id, "dispute")
        
        photo_count = len(self.ticket_data[user_id].data.get('photos', []))
        has_video = self.ticket_data[user_id].data.get('video_file_id') is not None
        
        await update.message.reply_text(
            f"✅ **Ваше обращение №{ticket_id} зарегистрировано!**\n\n"
            f"Тема: Диспут\n"
            f"Приложено фото: {photo_count} шт.\n"
            f"Приложено видео: {'Да' if has_video else 'Нет'}\n"
            f"Статус: В обработке\n\n"
            f"Ожидайте ответа оператора. Мы рассмотрим ваш диспут в ближайшее время!"
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ОБЩИЕ ВОПРОСЫ" ===
    
    async def general_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение общего вопроса"""
        user_id = update.effective_user.id
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Тикет не найден. Начните заново с /start")
            return ConversationHandler.END
        
        ticket_id = self.ticket_data[user_id].data.get('ticket_id')
        
        # Сохраняем сообщение в БД
        await self.save_ticket_message(ticket_id, user_id, update.message)
        
        await update.message.reply_text(
            f"✅ **Вопрос добавлен к тикету #{ticket_id}**\n\n"
            f"Ожидайте ответа оператора. После ответа откроется полноценный чат для общения!"
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ТРУДОУСТРОЙСТВО" ===
    
    async def job_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение всей информации о трудоустройстве одним сообщением"""
        user_id = update.effective_user.id
        
        if user_id not in self.ticket_data:
            await update.message.reply_text("Тикет не найден. Начните заново с /start")
            return ConversationHandler.END
        
        ticket_id = self.ticket_data[user_id].data.get('ticket_id')
        
        # Сохраняем сообщение в БД
        await self.save_ticket_message(ticket_id, user_id, update.message)
        
        await update.message.reply_text(
            f"✅ **Информация добавлена к тикету #{ticket_id}**\n\n"
            f"Спасибо за вашу заявку! Наш HR-менеджер свяжется с вами в ближайшее время."
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END

    # === СЛУЖЕБНЫЕ КОМАНДЫ ===
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена текущего диалога"""
        user_id = update.effective_user.id
        
        if user_id in self.ticket_data:
            del self.ticket_data[user_id]
        
        await update.message.reply_text(
            "❌ Создание обращения отменено.\n"
            "Для начала нового обращения используйте /start"
        )
        return ConversationHandler.END

    # === РАБОТА С БАЗОЙ ДАННЫХ ===
    
    async def create_ticket(self, user_id: int, category: str) -> int:
        """Создание тикета в БД"""
        try:
            with self.session_maker() as session:
                ticket_data = self.ticket_data[user_id]
                
                # Определяем тематику на русском языке
                category_names = {
                    "crypto_payment": "Проблемы с оплатой криптовалютой",
                    "dispute": "Диспут", 
                    "general": "Общие вопросы",
                    "employment": "Трудоустройство"
                }
                
                # Формируем базовое описание тикета (детали будут в сообщениях)
                description = f"Тематика: {category_names.get(category, category)}\n\nДетали смотрите в сообщениях тикета."
                
                # Создаем тикет
                new_ticket = ActiveTicket(
                    subject=category_names.get(category, "Новое обращение"),
                    category=category,
                    description=description,
                    status="active",
                    priority="medium",
                    telegram_user_id=str(user_id),
                    telegram_username=ticket_data.username,
                    bot_id=self.bot_id  # ID бота из админки
                )
                
                session.add(new_ticket)
                session.commit()
                session.refresh(new_ticket)
                
                logger.info(f"Создан новый тикет #{new_ticket.id} от пользователя {user_id} ({ticket_data.username})")
                
                return new_ticket.id
                
        except Exception as e:
            logger.error(f"Ошибка создания тикета: {e}")
            return None
    
    async def check_existing_ticket(self, user_id: int) -> Optional[int]:
        """Проверка наличия открытого тикета у пользователя"""
        try:
            with self.session_maker() as session:
                # Ищем активные тикеты пользователя (только статус "active")
                existing_ticket = session.query(ActiveTicket).filter(
                    ActiveTicket.telegram_user_id == str(user_id),
                    ActiveTicket.status == "active"
                ).first()
                
                return existing_ticket.id if existing_ticket else None
                
        except Exception as e:
            logger.error(f"Ошибка проверки существующего тикета: {e}")
            return None
    
    async def save_ticket_message(self, ticket_id: int, user_id: int, message):
        """Сохранение сообщения тикета в БД"""
        file_download_failed = False
        try:
            from database import TicketMessage
            
            with self.session_maker() as session:
                # Определяем тип сообщения и контент
                message_type = "text"
                content = message.text or ""
                file_id = None
                local_file_path = None
                original_filename = None
                file_size = None
                
                if message.photo:
                    message_type = "photo"
                    file_id = message.photo[-1].file_id
                    content = message.caption or ""
                    
                    # Скачиваем фото
                    file_info = await self.download_telegram_file(file_id, "photo")
                    if file_info:
                        local_file_path = file_info["local_path"]
                        original_filename = file_info["original_filename"]
                        file_size = file_info["file_size"]
                    else:
                        file_download_failed = True
                        
                elif message.video:
                    message_type = "video"
                    file_id = message.video.file_id
                    content = message.caption or ""
                    
                    # Скачиваем видео
                    file_info = await self.download_telegram_file(file_id, "video")
                    if file_info:
                        local_file_path = file_info["local_path"]
                        original_filename = file_info["original_filename"]
                        file_size = file_info["file_size"]
                    else:
                        # Файл не удалось скачать (возможно, слишком большой)
                        file_download_failed = True
                        
                elif message.document:
                    message_type = "document"
                    file_id = message.document.file_id
                    content = message.caption or ""
                    
                    # Скачиваем документ
                    file_info = await self.download_telegram_file(file_id, "document")
                    if file_info:
                        local_file_path = file_info["local_path"]
                        original_filename = file_info["original_filename"] or message.document.file_name
                        file_size = file_info["file_size"] or message.document.file_size
                    else:
                        file_download_failed = True
                
                # Создаем запись о сообщении
                ticket_message = TicketMessage(
                    ticket_id=ticket_id,
                    telegram_user_id=str(user_id),
                    message_type=message_type,
                    content=content,
                    file_id=file_id,
                    local_file_path=local_file_path,
                    original_filename=original_filename,
                    file_size=file_size,
                    is_from_admin=False
                )
                
                session.add(ticket_message)
                session.commit()
                
                logger.info(f"Сохранено сообщение для тикета #{ticket_id}")
                return {"success": True, "file_download_failed": file_download_failed}
                
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения тикета: {e}")
            return {"success": False, "file_download_failed": file_download_failed}

    # === ЗАПУСК И ОСТАНОВКА БОТА ===
    
    async def start_bot(self):
        """Запуск бота"""
        logger.info(f"Запуск бота с токеном {self.bot_token[:10]}...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop_bot(self):
        """Остановка бота"""
        logger.info("Остановка бота...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
    
    async def global_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик команды /start - работает всегда"""
        # Останавливаем любой активный разговор
        if update.effective_user.id in self.ticket_data:
            del self.ticket_data[update.effective_user.id]
        
        # Сбрасываем состояние разговора
        context.user_data.clear()
        
        # Вызываем обычную функцию start
        return await self.start_command(update, context)
    
    async def handle_ticket_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик сообщений для активных тикетов"""
        user = update.effective_user
        
        # Проверяем, есть ли у пользователя активный тикет
        existing_ticket_id = await self.check_existing_ticket(user.id)
        
        if existing_ticket_id:
            # Сохраняем сообщение в тикет
            result = await self.save_ticket_message(existing_ticket_id, user.id, update.message)
            
            if result and result["success"]:
                response_text = f"✅ Ваше сообщение добавлено к тикету #{existing_ticket_id}\n\n"
                
                if result["file_download_failed"]:
                    response_text += "⚠️ Внимание: Файл слишком большой для автоматического сохранения (максимум 20 МБ).\n" \
                                   
                
                response_text += "Администратор получил уведомление и ответит в ближайшее время."
                
                await update.message.reply_text(response_text)
            else:
                await update.message.reply_text(
                    f"❌ Произошла ошибка при сохранении сообщения в тикет #{existing_ticket_id}\n\n"
                    "Попробуйте отправить сообщение еще раз."
                )
        else:
            # Если нет активного тикета, предлагаем создать новый
            await update.message.reply_text(
                "У вас нет активных обращений.\n"
                "Для создания нового обращения используйте команду /start"
            )

# === ФУНКЦИИ ДЛЯ ЗАПУСКА БОТА ===

async def run_bot_with_token(bot_token: str, bot_id: int = None):
    """Запуск бота с указанным токеном"""
    try:
        bot = ZAZABot(bot_token, bot_id)
        await bot.start_bot()
        
        # Ожидание завершения
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
        await bot.stop_bot()
    except Exception as e:
        logger.error(f"Ошибка работы бота: {e}")
        await bot.stop_bot()

def main():
    """Основная функция для тестирования бота с одним токеном"""
    if len(sys.argv) < 2:
        print("Использование: python bot.py <BOT_TOKEN> [BOT_ID]")
        print("Пример: python bot.py 123456789:ABCdefGHIjklmnoPQRstu-VWXyz012345678 1")
        sys.exit(1)
    
    bot_token = sys.argv[1]
    bot_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"🤖 Запуск ZAZA бота...")
    print(f"📝 Токен: {bot_token[:10]}...")
    if bot_id:
        print(f"🆔 ID бота: {bot_id}")
    
    try:
        asyncio.run(run_bot_with_token(bot_token, bot_id))
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")

if __name__ == "__main__":
    main()