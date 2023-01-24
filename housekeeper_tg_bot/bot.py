from collections import defaultdict

import telebot
from config import DATABASE_PATH, TELEGRAM_BOT_API_TOKEN
from loguru import logger
from messages import messages
from models import Chat, Task, User
from peewee import IntegrityError, SqliteDatabase
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from utils import (
    build_name,
    build_task_message,
    choose_executor,
    create_task_list,
)

db = SqliteDatabase(DATABASE_PATH, pragmas={'foreign_keys': 1})

bot = telebot.TeleBot(TELEGRAM_BOT_API_TOKEN)


@bot.message_handler(commands=['start'])   # type: ignore
def start_message(message: telebot.types.Message) -> None:
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        messages['start'],
    )
    with db:
        try:
            db.create_tables(
                [User, Task, Chat, Chat.users.get_through_model()]
            )
            Chat.create(chat_id=message.chat.id)
        except Exception:
            logger.exception(messages['unknown_error'])


@bot.message_handler(commands=['tasks'])   # type: ignore
def list_tasks(message: telebot.types.Message) -> None:
    response_message = create_task_list(db, message.chat.id)
    response_message += '\n\nУдалить это сообщение или оставить?'
    bot.send_message(
        message.chat.id,
        response_message,
        reply_markup=ok_markup(),
        parse_mode='MarkdownV2',
    )
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(commands=['add_me'])   # type: ignore
def add_user(message: telebot.types.Message) -> None:

    name = build_name(message.from_user)

    with db:
        try:
            user = User.create(username=message.from_user.username)
            Chat.get(chat_id=message.chat.id).users.add(user)
            response_message = messages['created_user'].format(name)
        except IntegrityError:
            response_message = messages['user_already_exists'].format(name)
            logger.exception(messages['unknown_error'])
        except Exception:
            response_message = messages['unknown_error']
            logger.exception(messages['unknown_error'])

    response_message += '\n\nУдалить это сообщение или оставить?'
    bot.send_message(
        message.chat.id,
        response_message,
        reply_markup=ok_markup(),
    )
    bot.delete_message(message.chat.id, message.message_id)


def ok_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Удали', callback_data='ok_remove'),
        InlineKeyboardButton('Оставь', callback_data='ok_stay'),
    )
    return markup


@bot.callback_query_handler(
    func=lambda c: (c.data == 'ok_remove')
)   # type: ignore
def ok_remove(call: telebot.types.CallbackQuery) -> None:
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


@bot.callback_query_handler(
    func=lambda c: (c.data == 'ok_stay')
)   # type: ignore
def ok_stay(call: telebot.types.CallbackQuery) -> None:
    text = call.message.text
    text = text[: text.rfind('\n\nУдалить это сообщение или оставить?')]
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
        )
    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


def extract_task_text(text: str) -> str:
    message_parts = list(filter(len, text.split('\n')))
    return message_parts[1]


@bot.callback_query_handler(func=lambda c: (c.data == 'done'))   # type: ignore
def done(call: telebot.types.CallbackQuery) -> None:
    task = list(
        filter(
            lambda task: task.message_id == call.message.id,
            Chat.get(Chat.chat_id == call.message.chat.id).tasks,
        )
    )[0]

    task.is_finished = True
    task.executor = User.get(User.username == call.from_user.username)
    task.save()

    text = (
        call.message.text.replace('#', '')
        + f'\n\n✅ @{call.from_user.username} сделал задачу!'
    )
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
        )
    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


@bot.callback_query_handler(
    func=lambda c: (c.data == 'cancel')
)   # type: ignore
def cancel(call: telebot.types.CallbackQuery) -> None:
    task = list(
        filter(
            lambda task: task.message_id == call.message.id,
            Chat.get(Chat.chat_id == call.message.chat.id).tasks,
        )
    )[0]
    task.delete_instance()
    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id,
        )

    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


def offer_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Ок', callback_data='offer_yes'),
        InlineKeyboardButton('Не могу', callback_data='offer_no'),
    )
    return markup


def db_set_task_executor(chat_id: int, message_id: int, username: str) -> None:
    with db:
        task = list(
            filter(
                lambda task: task.message_id == message_id,
                Chat.get(Chat.chat_id == chat_id).tasks,
            )
        )[0]

        task.executor = User.get(User.username == username)
        task.save()


@bot.callback_query_handler(
    func=lambda c: (c.data == 'offer_yes')
)   # type: ignore
def offer_yes(call: telebot.types.CallbackQuery) -> None:
    db_set_task_executor(
        call.message.chat.id,
        call.message.reply_to_message.message_id,
        call.from_user.username,
    )

    text = (
        call.message.reply_to_message.text
        + f'\n\n⭐ @{call.from_user.username} вызвался сделать задачу!'
    )
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.reply_to_message.message_id,
            reply_markup=task_markup(),
        )
        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


@bot.callback_query_handler(
    func=lambda c: (c.data == 'offer_no')
)   # type: ignore
def offer_no(call: telebot.types.CallbackQuery) -> None:
    with db:
        candidates = Chat.get(chat_id=call.message.chat.id).users
        candidates = list(
            filter(
                lambda user: user.username != call.from_user.username,
                candidates,
            )
        )
        if not candidates:
            bot.answer_callback_query(
                call.id,
                'Нет кандидатов, кроме тебя, чтобы сделать задачу, увы.',
            )
            candidate = call.from_user
        else:
            candidate = choose_executor(db, candidates)
        text = (
            call.message.reply_to_message.text
            + f'\n\n⭐ Задачу делает @{candidate.username}!'
        )
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.reply_to_message.message_id,
            reply_markup=task_markup(),
        )

    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )
        return
    with db.atomic():
        task = list(
            filter(
                lambda task: task.message_id
                == call.message.reply_to_message.message_id,
                Chat.get(Chat.chat_id == call.message.chat.id).tasks,
            )
        )[0]

        task.executor = User.get(User.username == call.from_user.username)
        task.save()

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception:
        logger.exception(messages['unknown_error'])
        bot.answer_callback_query(
            call.id,
            messages['unknown_error'],
        )


def task_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton('Выполнить', callback_data='done'),
        InlineKeyboardButton('Отменить', callback_data='cancel'),
    )
    return markup


@bot.message_handler()   # type: ignore
def create_task(message: telebot.types.Message) -> None:
    task_text = message.text
    response_message = ''
    with db:
        try:
            task_message = bot.send_message(
                message.chat.id,
                messages['creating_task'],
            )
            task = Task.create(
                creator=User.get(User.username == message.from_user.username),
                text=task_text,
                chat=Chat.get(message.chat.id == Chat.chat_id),
                message_id=task_message.message_id,
            )
            response_message = build_task_message(task)
            bot.edit_message_text(
                response_message,
                message.chat.id,
                task_message.message_id,
                reply_markup=task_markup(),
                parse_mode='MarkdownV2',
            )

            bot.delete_message(message.chat.id, message.message_id)

            # Select all users with at least one task in this chat
            candidates = Chat.get(chat_id=message.chat.id).users
            candidates = list(candidates)
            candidate = choose_executor(db, candidates)
            if not candidate:
                bot.send_message(
                    message.chat.id,
                    messages['no_candidates'],
                    reply_markup=ok_markup(),
                )
                return

            bot.reply_to(
                task_message,
                messages['offer_being_executor'].format(candidate.username),
                reply_markup=offer_markup(),
                parse_mode=None,
            )
        except Exception:
            logger.exception('Failed to create task:')

            bot.send_message(
                message.chat.id,
                messages['unknown_error']
                + '\n\nУдалить это сообщение или оставить?',
                reply_markup=ok_markup(),
            )


bot.polling(none_stop=True)
