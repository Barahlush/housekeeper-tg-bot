import os

import dotenv

dotenv.load_dotenv('.env', verbose=True)
DATABASE_PATH = './db_files/main.db'
STATE_DATABASE_PATH = './db_files/state.db'
TELEGRAM_BOT_API_TOKEN = os.environ.get('TELEGRAM_BOT_API_TOKEN')
GIPHY_API_KEY = os.environ.get('GIPHY_API_KEY')
