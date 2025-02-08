import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    MONGODB_URI = os.getenv('MONGODB_URI')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '471827125').split(',')]
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
    SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')