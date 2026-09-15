from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from bot.core.config import settings

token = settings.BOT_TOKEN
bot = Bot(token=token, default=DefaultBotProperties())

dp = Dispatcher()