import logging
from pydoc_data.topics import topics

from pymsgbox import prompt
from selenium.webdriver.common.devtools.v85.runtime import await_promise
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, CommandHandler, MessageHandler, \
    filters, ConversationHandler
from dotenv import load_dotenv
import os
from chatgpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu,
                  default_callback_handler, load_prompt)

# Загружаем переменные из config.evn
dotenv_path = os.path.join(os.getcwd(), 'config.evn')

load_dotenv(dotenv_path=dotenv_path)

# Считываем токены из .env
CHATGPT_TOKEN = os.getenv("CHATGPT_API_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверяем, что токены не равны None
if not CHATGPT_TOKEN:
    print("CHATGPT_API_TOKEN не найден в .env")
if not TELEGRAM_TOKEN:
    print("TELEGRAM_BOT_TOKEN не найден в .env")

# Подключаем токены
chat_gpt = ChatGptService(CHATGPT_TOKEN)

# Создаем приложение Telegram
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Добавляем необходимые состояния
EDUCATION, EXPERIENCE, SKILLS = range(3)

# Хранилище данных пользователя
user_data = {}

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные о личностях и их promts
PERSONALITIES = {
    "Albert Einstein": "You are Albert Einstein. You speak like a physicist, always insightful and logical.",
    "Leonardo da Vinci": "You are Leonardo da Vinci. You speak like an artist and inventor, full of curiosity.",
    "Cleopatra": "You are Cleopatra. You speak like an ancient queen, wise and regal."
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)

    try:
        # Словарь команд
        commands = {
            'start': 'Главное меню',
            'random': 'Узнать случайный интересный факт 🧠',
            'gpt': 'Задать вопрос чату GPT 🤖',
            'talk': 'Поговорить с известной личностью 👤',
            'quiz': 'Поучаствовать в квизе ❓',
            'cv': 'Создай резюме'
        }

        # Отправляем меню с кнопками
        await show_main_menu(update, context, commands)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        await update.message.reply_text("Произошла ошибка при запуске бота. Попробуйте снова.")


# Функция для обработки команды /random
async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем готовый prompt
    prompt_fact = load_prompt("random_fact")
    # Получаем случайный факт с использованием GPT
    fact = await chat_gpt.send_question(prompt_fact, "")

    # Кнопки
    buttons = [
        [InlineKeyboardButton("Закончить", callback_data="start")],  # Кнопка для возвращения в меню
        [InlineKeyboardButton("Хочу ещё факт", callback_data="random")]  # Кнопка для получения ещё факта
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    # Отправляем факт с изображением и кнопками
    await send_image(update, context, 'random', caption=fact, reply_markup=keyboard)


# Обработчик команды /gpt
async def gpt_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Проверяем есть ли текст в сообщении
        if not update.message or not update.message.text:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Пожалуйста, отправьте ваш вопрос")
            return

        # Проверяем, вызвана ли команда /gpt или это просто сообщение
        if update.message.text.startswith("/gpt"):
            # Если это команда, извлекаем текст после сообщение
            user_text = update.message.text.replace("/gpt", "").strip()
            if not user_text:
                await update.message.reply_text("Пожалуйста задавайте ваш вопрос")
                return
        else:
            # Если это не команда, используем весь текст как вопрос
            user_text = update.message.text.strip()

        # Загружаем prompt
        prompt_gpt = load_prompt('gpt')

        # Отправляем картинку
        await send_image(update, context, 'gpt')

        # Отправляем запрос к ChatGPT
        answer = await chat_gpt.send_question(prompt_gpt, user_text)

        # Проверяем ответ от ChatGPT
        if not answer.strip():
            answer = "Извините, я не смог сформулировать ответ. Попробуйте задать вопрос по-другому."

        # Кнопки
        buttons = [
            [InlineKeyboardButton("Закончить", callback_data="start")],
            [InlineKeyboardButton("Задать еще вопрос", callback_data="gpt")]
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        # Отправляем ответ пользователю
        await update.message.reply_text(answer, reply_markup=keyboard)

    except Exception as e:
        # Логирование ошибки
        logger.error(f"Ошибка в gpt_question: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Произошло ошибка при обработке команды: {e}"
        )


# Функция для начала общения с выбранной личностью
async def talk_to_celebrity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Генерация кнопок для доступных личностей
    buttons = [[InlineKeyboardButton(name, callback_data=name)] for name in PERSONALITIES.keys()]
    keyboard = InlineKeyboardMarkup(buttons)

    # Отправка сообщения с кнопками выбора
    await send_image(update, context, 'talk', caption="Выберите личность для общения:", reply_markup=keyboard)


# Функция обработки выбора личности
async def personality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    try:
        # Логирование для отладки
        logger.info(f"Выбранная личность: {query.data}")

        # Проверяем, существует ли выбранная личность
        personality = query.data
        if personality not in PERSONALITIES:
            logger.error(f"Личность '{personality}' не найдена в словаре.")
            await query.message.reply_text("Произошла ошибка: выбранная личность не найдена.")
            return

        # Устанавливаем prompt для общения
        context.user_data['personality_prompt'] = PERSONALITIES[personality]

        # Отправляем новое сообщение вместо редактирования
        await query.message.reply_text(
            text=f"Вы выбрали {personality}. Теперь напишите что-нибудь, чтобы начать общение!"
        )
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
        await query.message.reply_text("Не удалось обработать ваш выбор. Попробуйте ещё раз.")


# Обработчик сообщений от пользователя
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text

    # Получаем prompt для выбранной личности
    personality_prompt = context.user_data.get('personality_prompt', "")
    if not personality_prompt:
        await update.message.reply_text("Сначала выберите личность для общения.")
        return

    # Загружаем общий prompt
    loaded_prompt = load_prompt("chatgpt_prompt")
    prompt = personality_prompt + "\n\n" + loaded_prompt + "\n\n" + user_message

    # Запрос к ChatGPT
    try:
        response = await chat_gpt.send_question(prompt, user_message)
        bot_reply = response.strip() or "Извините, я не смог сформулировать ответ. Попробуйте задать вопрос по-другому."

        # Отправляем ответ пользователю
        buttons = [[InlineKeyboardButton("Закончить", callback_data="start")]]
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(bot_reply, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего сообщения.")


# Функция для обработки команды /quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Проверяем, пришел ли запрос из callback_query
        message = update.message or update.callback_query.message

        # Генерация кнопок для выбора темы
        buttons = [
            [InlineKeyboardButton(topic, callback_data=f"quiz_{topic}")] for topic in
            ["Science", "History", "Literature"]
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        # Отправляем сообщение с кнопками выбора темы
        await message.reply_text("Выберите тему для квиза:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при старте квиза: {e}")
        # Обращаемся к тому же объекту message
        message = update.message or update.callback_query.message
        await message.reply_text("Произошла ошибка при начале квиза. Попробуйте снова.")


# Обработчик выбора темы квиза
async def quiz_topic_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        topic = query.data.split('_')[1]
        logger.info(f"Выбрана тема: {topic}")

        prompt = load_prompt('quiz')
        question = await chat_gpt.send_question(prompt, "")
        if not question.strip():
            question = "К сожалению, не удалось сформулировать вопрос. Попробуйте другую тему."

        context.user_data['quiz_topic'] = topic
        context.user_data['quiz_question'] = question

        buttons = [
            [InlineKeyboardButton("Ответить на вопрос", callback_data="quiz_answer")],
            [InlineKeyboardButton("Сменить тему", callback_data="quiz_change_topic")],
            [InlineKeyboardButton("Закончить квиз", callback_data="start")]
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await query.message.reply_text(f"Вопрос: {question}", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в обработке темы квиза: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте снова.")


# Обработчик ответа на вопрос квиза
async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()
    topic = context.user_data.get('quiz_topic', None)
    question = context.user_data.get('quiz_question', None)

    if not topic or not question:
        await update.message.reply_text("Пожалуйста, начните квиз с выбора темы.")
        return

    try:
        prompt = f"Проверь правильность ответа '{user_message}' на вопрос по теме '{topic}': {question}"
        answer = await chat_gpt.send_question(prompt, user_message)
        if not answer.strip():
            answer = "К сожалению, не удалось оценить ваш ответ. Попробуйте снова."

        buttons = [
            [InlineKeyboardButton("Задать другой вопрос", callback_data="quiz")],
            [InlineKeyboardButton("Сменить тему", callback_data="quiz_change_topic")],
            [InlineKeyboardButton("Закончить квиз", callback_data="start")]
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(f"Ваш ответ: {user_message}\n\nРезультат: {answer}", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в обработке ответа на квиз: {e}")
        await update.message.reply_text("Произошла ошибка при проверке ответа. Попробуйте снова.")


# Обработчик смены темы
async def quiz_change_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await quiz(update, context)


# Обработчик для команды /cv (начало процесса создания резюме)
async def start_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем callback_query, а не message
    callback_query = update.callback_query
    await callback_query.answer()  # Ответ на нажатие кнопки

    # Отправляем сообщение через callback_query.message
    await callback_query.message.reply_text('Привет! Я помогу тебе составить резюме. Начнем с твоего образования.')
    return EDUCATION

# Обработчик для ввода образования
async def education_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_education = update.message.text
    context.user_data['education'] = user_education
    await update.message.reply_text(f'Твое образование: {user_education}. Давай теперь поговорим о твоем опыте работы.')
    return EXPERIENCE

# Обработчик для ввода опыта работы
async def experience_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_experience = update.message.text
    context.user_data['experience'] = user_experience
    await update.message.reply_text(f'Твой опыт работы: {user_experience}. Теперь, давай обсудим твои навыки.')
    return SKILLS

# Обработчик для ввода навыков
async def skills_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_skills = update.message.text
    context.user_data['skills'] = user_skills
    await update.message.reply_text(f'Твои навыки: {user_skills}. Спасибо за информацию! Резюме готово.')

    # Формируем резюме
    resume = f"""
    Резюме:
    Образование: {context.user_data['education']}
    Опыт работы: {context.user_data['experience']}
    Навыки: {context.user_data['skills']}
    """

    # Отправляем резюме с кнопками
    buttons = [
        [InlineKeyboardButton("Создать еще", callback_data="cv")],  # Кнопка для создания нового резюме
        [InlineKeyboardButton("Закончить", callback_data="start")]  # Кнопка для завершения процесса
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(resume, reply_markup=keyboard)

    return ConversationHandler.END

# Функция для отмены процесса создания резюме
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Процесс создания резюме отменен.")
    return ConversationHandler.END

# Обновляем ConversationHandler
cv_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_resume, pattern="^cv$")],
    states={
        EDUCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, education_step)],
        EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience_step)],
        SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, skills_step)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],  # Убедитесь, что здесь правильная функция
)




# Обработчик нажатий на кнопки
async def buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Не забываем отвечать на запрос, иначе кнопки не работают.

    # Пропускаем обработку, если это выбор личности
    if query.data in PERSONALITIES.keys():
        # Если выбрана личность, начинаем общение
        await personality_choice(update, context)
        return

    if query.data == "start":
        # Если нажали на кнопку "Закончить" (callback_data="start"), показываем главное меню.
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Главное меню:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Главное меню", callback_data="start")],
                [InlineKeyboardButton("Узнать случайный интересный факт 🧠", callback_data="random")],
                [InlineKeyboardButton("Задать вопрос чату GPT 🤖", callback_data="gpt")],
                [InlineKeyboardButton("Поговорить с известной личностью 👤", callback_data="talk")],
                [InlineKeyboardButton("Поучаствовать в квизе ❓", callback_data="quiz")],
                [InlineKeyboardButton("Создай резюме", callback_data='cv')]
            ])
        )

    elif query.data == "random":
        await random_fact(update, context)


    elif query.data == "cv":
        # Запуск процесса создания резюме
        await start_resume(update, context)

    elif query.data == "gpt":
        await query.message.reply_text(
            "Вы выбрали GPT 🤖!\n"
            "Пожалуйста, задайте ваш вопрос, используя команду:\n\n"
            "Ваш вопрос",
            parse_mode="Markdown"
        )

    elif query.data == "talk":
        # Вызываем функцию для начала общения с личностью
        await talk_to_celebrity(update, context)

    elif query.data == "quiz":
        await query.message.reply_text("Вы выбрали квиз ❓!")
        await quiz(update, context)

    # Обработка выбора темы квиза
    elif query.data.startswith("quiz_"):
        await quiz_topic_choice(update, context)

    # Обработка ответа на вопрос квиза
    elif query.data == "quiz_answer":
        await quiz_answer(update, context)

    # Обработка смены темы
    elif query.data == "quiz_change_topic":
        await quiz_change_topic(update, context)


# Регистрируем обработчики
app.add_handler(CommandHandler("start", start))  # Обработчик команды /start
app.add_handler(CommandHandler("random", random_fact))  # Обработчик команды /random
app.add_handler(CommandHandler("gpt", gpt_question))  # Обработчик команды /gpt
app.add_handler(cv_conversation_handler)
app.add_handler(CommandHandler("quiz", quiz))  # Обработчик для квиза
app.add_handler(CallbackQueryHandler(quiz_topic_choice, pattern="^quiz_"))  # Выбор темы квиза
app.add_handler(CallbackQueryHandler(quiz_change_topic, pattern="quiz_change_topic"))  # Изменить тему квиза
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_answer))  # Обработка ответов на квиз
app.add_handler(CommandHandler("talk", talk_to_celebrity))  # Обработчик для команды /talk
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Общий обработчик сообщений
app.add_handler(CallbackQueryHandler(personality_choice,
                                     pattern="^(Albert Einstein|Leonardo da Vinci|Cleopatra)$"))  # Выбор персонажа
app.add_handler(CallbackQueryHandler(buttons_handler))  # Обработчик кнопок, если он не связан с резюме

# Запуск бота
app.run_polling()
