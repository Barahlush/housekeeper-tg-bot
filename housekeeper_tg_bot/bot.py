from random import choice

import telebot
from config import DATABASE_PATH, TELEGRAM_BOT_API_TOKEN
from gpt import get_gpt_response
from loguru import logger
from messages import messages
from models import Task, User
from peewee import IntegrityError, SqliteDatabase
from telebot.formatting import mbold
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot.util import quick_markup
import numpy as np

db = SqliteDatabase(DATABASE_PATH, pragmas={'foreign_keys': 1})

bot = telebot.TeleBot(TELEGRAM_BOT_API_TOKEN)


def create_task_list(chat_id: str, username: str) -> str:
    with db:
        tasks = User.get(User.tg_username == username).tasks.where(
            Task.tg_chat_id == chat_id, Task.is_finished == False
        )
        if not tasks:
            return str(messages['no_tasks'])

        task_list = f'Таски @{username}:\n\n'
        for task in tasks:
            task_list += f'{mbold(task.text)}\n\n'

        return task_list


def build_name(user: telebot.types.User) -> str:
    name = ''
    name += user.first_name or ''

    if name:
        name += ' '
    name += user.last_name or ''

    return name or user.username


def build_task_message(task: Task) -> str:
    preprompts = [
        'Важное примечание к этой задаче:',
        'Важное замечание к этой задаче:',
        'Важно помнить об этой задаче:',
    ]
    preprompt = choice(preprompts)
    prompt = f'Задание тебе - {task.text.lower()}. {preprompt}'
    generated_text = (
        get_gpt_response(prompt=prompt).replace('…', '').replace('»', '')
    )
    if generated_text:
        payload = f'{preprompt}{generated_text}'
    else:
        payload = None
    return (
        f'#task от @{task.creator.tg_username}\n\n'
        f'{mbold(task.text)}\n\n'
        f'{payload or ""}'
    )


def choose_executor(chat_id: str) -> User | None:
    def softmax(x: np.ndarray[float, float]) -> np.ndarray[float, float]:
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    with db:
        # Select all users with at least one task in this chat
        users = User.select().join(Task).where(Task.tg_chat_id == chat_id)
        users = list(users)
        if not users:
            return None
        task_counts = np.array(
            [user.tasks.count() for user in users], dtype=float
        )
        probabilities = softmax(-task_counts)
        return np.random.choice(users, p=probabilities)


@bot.message_handler(commands=['start'])   # type: ignore
def start_message(message: telebot.types.Message) -> None:
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        messages['start'],
    )
    with db:
        try:
            db.create_tables([User, Task])
        except Exception as e:
            logger.exception(messages['unknown_error'])


@bot.message_handler(commands=['tasks'])   # type: ignore
def list_tasks(message: telebot.types.Message) -> None:
    response_message = create_task_list(
        message.chat.id, message.from_user.username
    )
    response_message += '\n\nУдалить это сообщение или оставить?'
    bot.send_message(
        message.chat.id,
        response_message,
        reply_markup=ok_markup(),
        parse_mode='Markdown',
    )
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(commands=['add_me'])   # type: ignore
def add_user(message: telebot.types.Message) -> None:

    name = build_name(message.from_user)

    with db:
        try:
            User.create(name=name, tg_username=message.from_user.username)
            response_message = messages['created_user'].format(name)
        except IntegrityError:
            response_message = messages['user_already_exists'].format(name)
            logger.exception(messages['unknown_error'])
        except Exception:
            response_message = messages['unknown_error']
            logger.exception(messages['unknown_error'])

    response_message += '\n\nУдалить это сообщение или оставить?'
    bot.send_message(
        message.chat.id, response_message, reply_markup=ok_markup()
    )
    bot.delete_message(message.chat.id, message.message_id)


def ok_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Ок, удали', callback_data='ok_remove'),
        InlineKeyboardButton('Ок, оставь', callback_data='ok_stay'),
    )
    return markup


@bot.callback_query_handler(
    func=lambda c: (c.data == 'ok_remove')
)   # type: ignore
def ok_remove(call: telebot.types.CallbackQuery) -> None:
    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(
    func=lambda c: (c.data == 'ok_stay')
)   # type: ignore
def ok_stay(call: telebot.types.CallbackQuery) -> None:
    text = call.message.text
    text = text[: text.rfind('\n\nУдалить это сообщение или оставить?')]
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
    )


def extract_task_text(text: str) -> str:
    message_parts = list(filter(len, text.split('\n')))
    return message_parts[1]


@bot.callback_query_handler(func=lambda c: (c.data == 'done'))   # type: ignore
def done(call: telebot.types.CallbackQuery) -> None:
    task = Task.get(
        Task.tg_chat_id == call.message.chat.id,
        Task.text == extract_task_text(call.message.text),
    )

    task.is_finished = True
    task.executor = User.get(User.tg_username == call.from_user.username)
    task.save()

    text = (
        call.message.text.replace('#', '')
        + f'\n\n✅ @{call.from_user.username} сделал задачу! ✅'
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
    )


def offer_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Да', callback_data='offer_yes'),
        InlineKeyboardButton('Нет', callback_data='offer_no'),
    )
    return markup


@bot.callback_query_handler(
    func=lambda c: (c.data == 'offer_yes')
)   # type: ignore
def offer_yes(call: telebot.types.CallbackQuery) -> None:
    task = Task.get(
        Task.tg_chat_id == call.message.chat.id,
        Task.text == extract_task_text(call.message.reply_to_message.text),
    )

    task.executor = User.get(User.tg_username == call.from_user.username)
    task.save()

    text = (
        call.message.reply_to_message.text
        + f'\n\n⭐ @{call.from_user.username} вызвался сделать задачу! ⭐'
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.reply_to_message.message_id,
    )


@bot.callback_query_handler(
    func=lambda c: (c.data == 'offer_no')
)   # type: ignore
def offer_no(call: telebot.types.CallbackQuery) -> None:
    task = Task.get(
        Task.tg_chat_id == call.message.chat.id,
        Task.text == extract_task_text(call.message.reply_to_message.text),
    )

    task.executor = User.get(User.tg_username == call.from_user.username)
    task.save()

    text = (
        call.message.reply_to_message.text
        + f'\n\n⭐ @{call.from_user.username} вызвался сделать задачу! ⭐'
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.reply_to_message.message_id,
    )


@bot.message_handler()   # type: ignore
def process_text(message: telebot.types.Message) -> None:
    task_text = message.text
    response_message = ''
    markup = ok_markup()
    with db:
        try:
            task = Task.create(
                creator=User.get(
                    User.tg_username == message.from_user.username
                ),
                text=task_text,
                tg_chat_id=message.chat.id,
                tg_username=message.from_user.username,
            )
            response_message = build_task_message(task)
            markup = quick_markup({'Выполнить': {'callback_data': 'done'}})
        except Exception:
            logger.exception('Failed to create task:')
            response_message = messages['unknown_error']
    task_message = bot.send_message(
        message.chat.id,
        response_message,
        reply_markup=markup,
        parse_mode='Markdown',
    )
    task.tg_message_id = task_message.message_id
    task.save()

    bot.delete_message(message.chat.id, message.message_id)

    bot.reply_to(
        task_message,
        messages['offer_being_executor'].format(choose_executor().username),
        reply_markup=offer_markup(),
    )


bot.polling(none_stop=True)
