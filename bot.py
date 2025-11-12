import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, List
import pytz # <-- Импортируем pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os # <-- Импортируем os для доступа к переменным окружения

# ========================
# КОНФИГУРАЦИЯ (из переменных окружения)
# ========================
# Получаем токен и ID из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("Ошибка: Переменная окружения BOT_TOKEN не установлена.")
    exit(1)

try:
    YOUR_CHAT_ID = int(os.getenv("YOUR_CHAT_ID", 0)) # Преобразуем в int, если есть, иначе 0
    if YOUR_CHAT_ID == 0:
        print("Ошибка: Переменная окружения YOUR_CHAT_ID не установлена или равна 0.")
        exit(1)
except ValueError:
    print("Ошибка: YOUR_CHAT_ID должен быть числом.")
    exit(1)


# Список вопросов (10 шт)
QUESTIONS = [
    "Сколько раз ты улыбался?",
    "Сколько улыбок видел вокруг?",
    "Были ли негативные мысли?",
    "Сколько раз ты солгал, даже в самой что ни на есть мелочи — себе или другим?",
    "Какая осанка у тебя прямо сейчас? И да – на окружающих тоже глянь, ради интереса.",
    "Видел ли счастливых людей?",
    "В каком настроении ты провёл этот час?",
    "Сколько минут в прошедшем часе тебе было хорошо и спокойно?",
    "За прошедший час: благодарил ли ты кого-нибудь искренне, от души? Благодарили ли тебя?",
    "Читал ли, видел ли, слышал ли за прошедший час негативные новости или сплетни?"
]

# Список ссылок на цитаты (из файла)
try:
    with open('цитаты в картинках_ссылки.txt', 'r', encoding='utf-8') as f:
        QUOTE_IMAGES = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print("Файл 'цитаты в картинках_ссылки.txt' не найден. Убедитесь, что он находится в той же папке, что и bot.py.")
    exit(1)

# ========================
# ХРАНИЛИЩЕ ДАННЫХ (в памяти, для старта с ноутбука)
# ========================
# Словарь для хранения информации о пользователях
users = {}  # {user_id: {start_hour, end_hour, used_quotes_today, last_action_day, message_count}}

# ========================
# ИНИЦИАЛИЗАЦИЯ
# ========================
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=session, parse_mode=ParseMode.HTML)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# ========================
# (Весь остальной код остается без изменений, только используем pytz везде, как в предыдущем ответе)
# Примеры изменений для pytz:

# В process_hours:
# Попробуем отправить первое сообщение, если сейчас подходящее время (по МСК)
now_msk = datetime.now(pytz.timezone("Europe/Moscow"))
current_hour_msk = now_msk.hour
if start_hour <= current_hour_msk < end_hour:
    await send_hourly_message(user_id)

# В schedule_hourly_messages:
now_msk = datetime.now(pytz.timezone("Europe/Moscow"))
current_hour_msk = now_msk.hour
for user_id, data in list(users.items()):
    if data['start_hour'] <= current_hour_msk < data['end_hour']:
        await send_hourly_message(user_id)

# В send_hourly_message (проверка последнего часа):
now_msk = datetime.now(pytz.timezone("Europe/Moscow"))
if now_msk.hour == user_data['end_hour'] - 1:
    # ... отправка сообщения ...

# В send_log_to_owner:
now_msk = datetime.now(pytz.timezone("Europe/Moscow"))
await bot.send_message(
    chat_id=YOUR_CHAT_ID,
    text=f"📊 Лог бота-наблюдателя:\n"
         f"Всего активных: {total_users}\n"
         f"Время: {now_msk.strftime('%Y-%m-%d %H:%M')} МСК"
)

# В handle_text (обновление last_action_day):
users[user_id]['last_action_day'] = datetime.now(pytz.timezone("Europe/Moscow")).date()

# В process_hours (установка last_action_day):
users[user_id]['last_action_day'] = datetime.now(pytz.timezone("Europe/Moscow")).date()

# (И так везде, где используется datetime.now())
# ========================

# ... (остальной код, как в предыдущем ответе, но с pytz и os.getenv) ...

async def main():
    # Запуск планировщика
    # Отправка лога каждый час в 10 минут
    scheduler.add_job(send_log_to_owner, CronTrigger(minute=10))
    # Отправка сообщений каждый час в 05 минут
    scheduler.add_job(schedule_hourly_messages, CronTrigger(minute=5))
    # Сброс цитат в полночь (по МСК)
    scheduler.add_job(reset_daily_quotes, CronTrigger(hour=0, minute=0))

    scheduler.start()
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
