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
    CRYPTO_SEND_ADDRESS = 11
    CRYPTO_AMOUNT = 12
    CRYPTO_DESCRIPTION = 13
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
    JOB_POSITION = 41
    JOB_EXPERIENCE = 42

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
                States.CRYPTO_SEND_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.crypto_send_address)
                ],
                States.CRYPTO_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.crypto_amount)
                ],
                States.CRYPTO_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.crypto_description)
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
                States.JOB_POSITION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.job_position)
                ],
                States.JOB_EXPERIENCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.job_experience)
                ],
            },
            fallbacks=[
                CommandHandler('start', self.start_command),
                CommandHandler('cancel', self.cancel_command)
            ],
            per_chat=True
        )
        
        self.application.add_handler(conversation_handler)
        
        # Обработчик сообщений в активных тикетах (когда тикет уже создан и идет общение)
        # self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ticket_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        user = update.effective_user
        
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
            await update.message.reply_text(
                "💳 **Проблемы с оплатой криптовалютой**\n\n"
                "Для решения вашей проблемы мне потребуется некоторая информация.\n"
                "Пожалуйста, укажите **номер заказа**:",
                reply_markup=ReplyKeyboardRemove()
            )
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
            await update.message.reply_text(
                "❓ **Общие вопросы**\n\n"
                "Опишите ваш вопрос подробно. После этого я создам обращение, "
                "и наш оператор ответит вам в ближайшее время:",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.GENERAL_QUESTION
            
        elif category_text == "💼 Трудоустройство":
            self.ticket_data[user_id].category = "employment"
            await update.message.reply_text(
                "💼 **Трудоустройство**\n\n"
                "Расскажите немного о себе, вашем опыте и навыках:",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.JOB_ABOUT
        
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите категорию из предложенных вариантов."
            )
            return States.CATEGORY_SELECTION

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ПРОБЛЕМЫ С ОПЛАТОЙ КРИПТОВАЛЮТОЙ" ===
    
    async def crypto_order_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение номера заказа для криптоплатежей"""
        user_id = update.effective_user.id
        order_number = update.message.text
        
        self.ticket_data[user_id].data['order_number'] = order_number
        
        await update.message.reply_text(
            "Спасибо! Теперь укажите **адрес отправки криптовалюты**:"
        )
        return States.CRYPTO_SEND_ADDRESS

    async def crypto_send_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение адреса отправки криптовалюты"""
        user_id = update.effective_user.id
        send_address = update.message.text
        
        self.ticket_data[user_id].data['send_address'] = send_address
        
        # Кнопки выбора валюты
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data="crypto_btc")],
            [InlineKeyboardButton("💎 Ethereum (ETH)", callback_data="crypto_eth")],
            [InlineKeyboardButton("💵 USDT (TRC20)", callback_data="crypto_usdt_trc20")],
            [InlineKeyboardButton("💵 USDT (ERC20)", callback_data="crypto_usdt_erc20")],
            [InlineKeyboardButton("💸 Другая валюта", callback_data="crypto_other")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
        
        await update.message.reply_text(
            "Отлично! Теперь выберите **криптовалюту** и укажите сумму:",
            reply_markup=keyboard
        )
        return States.CRYPTO_AMOUNT

    async def crypto_currency_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора криптовалюты"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        currency_data = query.data
        
        if currency_data == "cancel":
            await query.edit_message_text("❌ Операция отменена. Для создания нового обращения используйте /start")
            del self.ticket_data[user_id]
            return ConversationHandler.END
        
        # Определяем валюту
        currency_map = {
            "crypto_btc": "Bitcoin (BTC)",
            "crypto_eth": "Ethereum (ETH)", 
            "crypto_usdt_trc20": "USDT (TRC20)",
            "crypto_usdt_erc20": "USDT (ERC20)",
            "crypto_other": "Другая валюта"
        }
        
        currency = currency_map.get(currency_data, "Не указана")
        self.ticket_data[user_id].data['currency'] = currency
        
        if currency_data == "crypto_other":
            await query.edit_message_text(
                "Укажите название валюты и сумму.\n"
                "Например: _100 LTC_ или _0.5 BNB_"
            )
        else:
            await query.edit_message_text(
                f"Валюта: **{currency}**\n\n"
                f"Теперь укажите сумму.\n"
                f"Например: _100_ или _0.05_"
            )
        
        return States.CRYPTO_AMOUNT

    async def crypto_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение суммы криптовалюты"""
        user_id = update.effective_user.id
        amount = update.message.text
        
        self.ticket_data[user_id].data['amount'] = amount
        
        # Кнопка отмены
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ])
        
        await update.message.reply_text(
            "Почти готово! Теперь опишите **проблему подробно**:",
            reply_markup=keyboard
        )
        return States.CRYPTO_DESCRIPTION

    async def crypto_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение описания проблемы с криптоплатежом и создание тикета"""
        user_id = update.effective_user.id
        description = update.message.text
        
        self.ticket_data[user_id].data['description'] = description
        
        # Создаем тикет в БД
        ticket_id = await self.create_ticket(user_id, "crypto_payment")
        
        await update.message.reply_text(
            f"✅ **Ваше обращение №{ticket_id} зарегистрировано!**\n\n"
            f"Тема: Проблемы с оплатой криптовалютой\n"
            f"Статус: В обработке\n\n"
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
        """Получение общего вопроса и создание тикета"""
        user_id = update.effective_user.id
        question = update.message.text
        
        self.ticket_data[user_id].data['question'] = question
        
        # Создаем тикет в БД
        ticket_id = await self.create_ticket(user_id, "general")
        
        await update.message.reply_text(
            f"✅ **Ваше обращение №{ticket_id} зарегистрировано!**\n\n"
            f"Тема: Общие вопросы\n"
            f"Статус: В обработке\n\n"
            f"Ожидайте ответа оператора. После ответа откроется полноценный чат для общения!"
        )
        
        # Очищаем временные данные
        del self.ticket_data[user_id]
        return ConversationHandler.END

    # === ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИИ "ТРУДОУСТРОЙСТВО" ===
    
    async def job_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о себе для трудоустройства"""
        user_id = update.effective_user.id
        about = update.message.text
        
        self.ticket_data[user_id].data['about'] = about
        
        await update.message.reply_text(
            "Спасибо! Теперь укажите **желаемую вакансию или должность**:"
        )
        return States.JOB_POSITION

    async def job_position(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение желаемой позиции"""
        user_id = update.effective_user.id
        position = update.message.text
        
        self.ticket_data[user_id].data['position'] = position
        
        await update.message.reply_text(
            "Отлично! И последний вопрос - расскажите о вашем **опыте работы и навыках**:"
        )
        return States.JOB_EXPERIENCE

    async def job_experience(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение опыта работы и создание тикета"""
        user_id = update.effective_user.id
        experience = update.message.text
        
        self.ticket_data[user_id].data['experience'] = experience
        
        # Создаем тикет в БД
        ticket_id = await self.create_ticket(user_id, "employment")
        
        await update.message.reply_text(
            f"✅ **Ваше обращение №{ticket_id} зарегистрировано!**\n\n"
            f"Тема: Трудоустройство\n"
            f"Статус: В обработке\n\n"
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
                
                # Формируем описание тикета
                description_parts = [f"Тематика: {category_names.get(category, category)}"]
                
                if category == "crypto_payment":
                    data = ticket_data.data
                    description_parts.extend([
                        f"Номер заказа: {data.get('order_number', 'Не указан')}",
                        f"Адрес отправки: {data.get('send_address', 'Не указан')}",
                        f"Сумма: {data.get('amount', 'Не указана')}",
                        f"Описание проблемы: {data.get('description', 'Не указано')}"
                    ])
                
                elif category == "dispute":
                    data = ticket_data.data
                    description_parts.extend([
                        f"Номер заказа: {data.get('order_number', 'Не указан')}",
                        f"Видео приложено: {'Да' if data.get('video_file_id') else 'Нет'}",
                        f"Количество фото: {len(data.get('photos', []))}",
                        f"Описание проблемы: {data.get('description', 'Не указано')}"
                    ])
                
                elif category == "general":
                    data = ticket_data.data
                    description_parts.append(f"Вопрос: {data.get('question', 'Не указан')}")
                
                elif category == "employment":
                    data = ticket_data.data
                    description_parts.extend([
                        f"О себе: {data.get('about', 'Не указано')}",
                        f"Желаемая позиция: {data.get('position', 'Не указана')}",
                        f"Опыт работы: {data.get('experience', 'Не указан')}"
                    ])
                
                description = "\n".join(description_parts)
                
                # Создаем тикет
                new_ticket = ActiveTicket(
                    subject=category_names.get(category, "Новое обращение"),
                    category=category,
                    description=description,
                    status="open",
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
    
    async def save_ticket_message(self, ticket_id: int, user_id: int, message):
        """Сохранение сообщения тикета в БД"""
        try:
            from database import TicketMessage
            
            with self.session_maker() as session:
                # Определяем тип сообщения и контент
                message_type = "text"
                content = message.text or ""
                file_id = None
                
                if message.photo:
                    message_type = "photo"
                    file_id = message.photo[-1].file_id
                    content = message.caption or ""
                elif message.video:
                    message_type = "video"
                    file_id = message.video.file_id
                    content = message.caption or ""
                elif message.document:
                    message_type = "document"
                    file_id = message.document.file_id
                    content = message.caption or ""
                
                # Создаем запись о сообщении
                ticket_message = TicketMessage(
                    ticket_id=ticket_id,
                    telegram_user_id=str(user_id),
                    message_type=message_type,
                    content=content,
                    file_id=file_id,
                    is_from_admin=False
                )
                
                session.add(ticket_message)
                session.commit()
                
                logger.info(f"Сохранено сообщение для тикета #{ticket_id}")
                
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения тикета: {e}")

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