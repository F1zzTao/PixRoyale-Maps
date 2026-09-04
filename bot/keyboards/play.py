from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Game button
def play_button():
    """Кнопка для запуска игры"""
    button = InlineKeyboardButton(
        text="🎮 Играть в PixRoyale", url="https://t.me/PixRoyaleBot?startapp"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
