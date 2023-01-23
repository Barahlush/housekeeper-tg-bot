import datetime

from config import DATABASE_PATH
from peewee import (
    CharField,
    DateField,
    ForeignKeyField,
    Model,
    SqliteDatabase,
    TextField,
    BooleanField,
)

db = SqliteDatabase(DATABASE_PATH, pragmas={'foreign_keys': 1})


class BaseModel(Model):  # type: ignore
    creation_time = DateField(default=datetime.datetime.now)

    class Meta:
        database = db


class User(BaseModel):
    tg_username = CharField(unique=True)


class Task(BaseModel):
    creator = ForeignKeyField(model=User, backref='tasks', on_delete='CASCADE')
    executor = ForeignKeyField(model=User, backref='finished_tasks', null=True)
    text = TextField()
    deadline = DateField(
        default=datetime.date.today() + datetime.timedelta(days=1)
    )
    is_finished = BooleanField(default=False)
    tg_chat_id = CharField()
    tg_message_id = CharField()

    class Meta:
        database = db
