from random import choice
from typing import cast

import numpy as np
import telebot
from loguru import logger
from media_content import get_gpt_response
from messages import messages
from models import Chat, Task, User
from numpy.typing import NDArray
from peewee import SqliteDatabase
from telebot.formatting import escape_markdown, mbold


def create_task_list(db: SqliteDatabase, chat_id: str) -> str:
    with db:
        tasks = Chat.get(Chat.chat_id == chat_id).tasks.where(
            Task.is_finished == False  # noqa: E712
        )
        if not tasks:
            return str(messages['no_tasks'])
        task_list = 'Активные задачи:\n\n'
        for task in tasks:
            task_list += f'{mbold(escape_markdown(task.text))}\n'
            if task.executor:
                task_list += f'Исполнитель: @{task.executor.username}\n\n'
            else:
                task_list += '\n'
        return task_list


def create_stat_list(db: SqliteDatabase, chat_id: str) -> str:
    with db:
        try:
            chat = Chat.get(Chat.chat_id == chat_id)

            stat_list = 'Статистика:\n\n'
            for user in chat.users:
                task_count = chat.tasks.where(Task.executor == user.id).count()
                completed_task_count = chat.tasks.where(
                    Task.executor == user.id,
                    Task.is_finished == True,  # noqa: E712
                ).count()
                stat_list += f'{mbold(escape_markdown(user.username))}\n'
                stat_list += f'Количество задач: {task_count}\n'
                stat_list += (
                    f'Количество выполненных задач: {completed_task_count}\n\n'
                )
            return stat_list
        except Exception:
            logger.exception('Error while creating stat list')
            return 'Статистики нет'


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
    generated_text = get_gpt_response(prompt=prompt)
    if generated_text:
        generated_text = generated_text.replace('…', '').replace('»', '')
        payload = f'{preprompt}{generated_text}'
    else:
        payload = ''
    return (
        f'\#task от @{task.creator.username}\n\n'  # noqa: W605
        f'{mbold(task.text)}\n\n'
        f'{escape_markdown(payload) or ""}'
    )


def choose_executor(
    db: SqliteDatabase, users: list[User], chat_id: int
) -> User | None:
    def softmax(x: NDArray[np.float32]) -> NDArray[np.float32]:
        e_x = np.exp(x - np.max(x))
        return cast(NDArray[np.float32], e_x / e_x.sum())

    with db:
        if not users:
            return None
        # chat task counts for each user in the chat
        task_counts_list = [
            Task.select()
            .where(
                Task.chat == Chat.get(Chat.chat_id == chat_id).id,
                Task.executor == user.id,
            )
            .count()
            for user in users
        ]
        task_counts = np.array(
            task_counts_list,
            dtype=float,
        )
        probabilities = softmax(-task_counts)
        return cast(User, np.random.choice(users, p=probabilities))
