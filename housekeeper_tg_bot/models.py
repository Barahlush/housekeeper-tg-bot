import datetime

from config import DATABASE_PATH
from peewee import (
    BooleanField,
    CharField,
    DateField,
    ForeignKeyField,
    IntegerField,
    ManyToManyField,
    Model,
    SqliteDatabase,
    TextField,
)

db = SqliteDatabase(DATABASE_PATH, pragmas={'foreign_keys': 1})


class BaseModel(Model):  # type: ignore
    creation_time = DateField(default=datetime.datetime.now)

    class Meta:
        database = db


class Chat(BaseModel):
    chat_id = IntegerField(unique=True)


class User(BaseModel):
    username = CharField(unique=True)
    chats = ManyToManyField(Chat, backref='users')


class Task(BaseModel):
    creator = ForeignKeyField(model=User, backref='tasks', on_delete='CASCADE')
    executor = ForeignKeyField(model=User, backref='finished_tasks', null=True)
    chat = ForeignKeyField(model=Chat, backref='tasks', on_delete='CASCADE')
    text = TextField()
    deadline = DateField(
        default=datetime.date.today() + datetime.timedelta(days=1)
    )
    is_finished = BooleanField(default=False)
    message_id = IntegerField()

    class Meta:
        database = db
