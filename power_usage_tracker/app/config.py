import os
import sys

class Config:
    def __init__(self):
        self.LIVE_UPDATES_API_URL = os.environ.get('LIVE_UPDATES_API_URL')
        self.HOME_DATA_API_URL = os.environ.get('HOME_DATA_API_URL')
        self.LOW_BALANCE_THRESHOLD = os.environ.get('LOW_BALANCE_THRESHOLD')
        self.BEARER_TOKEN = os.environ.get('POWER_USAGE_BEARER_TOKEN')
        self.DATABASE = os.environ.get('POWER_USAGE_DATABASE', 'power_usage_index.db')
        self.FETCH_INTERVAL_SECONDS = int(os.environ.get('POWER_USAGE_FETCH_INTERVAL_SECONDS', 30))
        self.TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

        if not all([self.LIVE_UPDATES_API_URL, self.HOME_DATA_API_URL, self.BEARER_TOKEN, self.LOW_BALANCE_THRESHOLD]):
            print(
                "Error: LIVE_UPDATES_API_URL, HOME_DATA_API_URL, LOW_BALANCE_THRESHOLD, and POWER_USAGE_BEARER_TOKEN must be set.",
                file=sys.stderr
            )
            sys.exit(1)

def load_config():
    return Config()
