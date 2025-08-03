from flask import Flask
from dotenv import load_dotenv
import os
from .telegram_notifier import send_telegram_message
from .config import load_config
from .state import State
from .api_client import ApiClient
from .data_manager import init_db, store_data
from .views.dashboard import create_dashboard_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    config = load_config()
    state = State()
    api_client = ApiClient(config)
    
    init_db(config.DATABASE)
    
    dashboard_bp = create_dashboard_bp(api_client, config)
    app.register_blueprint(dashboard_bp, url_prefix='/')
    
    from apscheduler.schedulers.background import BackgroundScheduler
    
    scheduler = BackgroundScheduler()
    
    @scheduler.scheduled_job('interval', seconds=config.FETCH_INTERVAL_SECONDS)
    def scheduled_fetch_data():
        live_data = api_client.fetch_data()
        if live_data:
            store_data(live_data, state, config)
            
    @scheduler.scheduled_job('cron', hour=23, minute=59)
    def send_daily_summary():
        home_data = api_client.fetch_home_data()
        if home_data and home_data.get('Data'):
            data = home_data['Data']
            
            message = (
                f"*Daily Power Usage Summary*\n\n"
                f"Today's EB Usage: Rs *{data.get('CurrentDay_EB', 0)}\n"
                f"Today's DG Usage: Rs *{data.get('CurrentDay_DG', 0)}\n"
                f"Month's EB Usage: Rs *{data.get('CurrentMonth_EB', 0)}\n"
                f"Month's DG Usage: Rs *{data.get('CurrentMonth_DG', 0)}\n"
                f"Meter Balance: Rs *₹{data.get('MeterBal', 0)}*"
            )
            
            send_telegram_message(message, config)

    scheduler.start()
    
    return app
