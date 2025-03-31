from venv import logger

from anyio.abc import value
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, \
    BotCommand, MenuButtonCommands, BotCommandScopeChat, MenuButtonDefault
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes


# конвертирует объект user в строку
def dialog_user_info_to_str(user_data) -> str:
    mapper = {'language_from': 'Язык оригинала', 'language_to': 'Язык перевода',
              'text_to_translate': 'Текст для перевода'}
    return '\n'.join(map(lambda k, v: (mapper[k], v), user_data.items()))


# посылает в чат текстовое сообщение
async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    text: str) -> Message:
    if text.count('_') % 2 != 0:
        message = f"Строка '{text}' является невалидной с точки зрения markdown. Воспользуйтесь методом send_html()"
        print(message)
        return await update.message.reply_text(message)

    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    return await context.bot.send_message(chat_id=update.effective_chat.id,
                                          text=text,
                                          parse_mode=ParseMode.MARKDOWN)


# посылает в чат html сообщение
async def send_html(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    text: str) -> Message:
    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    return await context.bot.send_message(chat_id=update.effective_chat.id,
                                          text=text, parse_mode=ParseMode.HTML)


# посылает в чат текстовое сообщение, и добавляет к нему кнопки
async def send_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            text: str, buttons: dict) -> Message:
    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    keyboard = []
    for key, value in buttons.items():
        button = InlineKeyboardButton(str(value), callback_data=str(key))
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    return await context.bot.send_message(
        update.effective_message.chat_id,
        text=text, reply_markup=reply_markup,
        message_thread_id=update.effective_message.message_thread_id)


# Функция для отправки изображения с опциональной подписью
async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     name: str, caption: str = None, reply_markup=None) -> Message:
    # Открываем изображение
    with open(f'res/img/{name}.png', 'rb') as image:
        return await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image,
            caption=caption,  # Подпись для изображения
            reply_markup=reply_markup  # Клавиатура с кнопками
        )


# отображает команду и главное меню
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, commands: dict):
    try:
        # Создаем кнопки из команд
        buttons = [
            [InlineKeyboardButton(value, callback_data=key)] for key, value in commands.items()
        ]

        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(buttons)

        # Отправляем клавиатуру с текстом
        await update.message.reply_text(text="Выберите команду:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при отправке меню: {e}")



# Удаляем команды для конкретного чата
async def hide_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_my_commands(
        scope=BotCommandScopeChat(chat_id=update.effective_chat.id))
    await context.bot.set_chat_menu_button(menu_button=MenuButtonDefault(),
                                           chat_id=update.effective_chat.id)


# загружает сообщение из папки  /res/msg/
def load_message(name):
    with open("res/msg/" + name + ".txt", "r",
              encoding="utf8") as file:
        return file.read()


# загружает промпт из папки  /res/messages/
def load_prompt(name):
    try:
        with open(f"res/prompts/{name}.txt", "r", encoding="utf8") as file:
            return file.read()
    except FileNotFoundError as e:
        logger.error(f"Файл {name}.txt не найден: {e}")
        return "Ошибка загрузки промпта."
    except Exception as e:
        logger.error(f"Ошибка при загрузке {name}.txt: {e}")
        return "Произошла ошибка."



async def default_callback_handler(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    query = update.callback_query.data
    await send_html(update, context, f'You have pressed button with {query} callback')


class Dialog:
    pass
