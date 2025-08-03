import sqlite3
from datetime import datetime, timedelta
import pytz
import logging
from .telegram_notifier import send_telegram_message

logger = logging.getLogger(__name__)

def init_db(database_path):
    """Initialize database with proper indexing"""
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS power_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                balance REAL NOT NULL,
                present_load REAL NOT NULL,
                amount_used REAL
            )
        ''')
        
        c.execute('CREATE INDEX IF NOT EXISTS timestamp_idx ON power_usage(timestamp)')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

def get_last_record(database_path):
    """Retrieve last record with proper connection handling"""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()
        
        c.execute('SELECT * FROM power_usage ORDER BY timestamp DESC LIMIT 1')
        record = c.fetchone()
        
        if record:
            return {
                'timestamp': record[1],
                'balance': record[2],
                'present_load': record[3],
                'amount_used': record[4]
            }
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
    return None

def store_data(data, state, config):
    """Store API data with proper error handling and meter reset detection"""
    try:
        conn = sqlite3.connect(config.DATABASE)
        c = conn.cursor()
        
        try:
            balance = float(data['Data']['Balance'])
            present_load = float(data['Data']['PresentLoad'])
            dg_value = float(data['Data']['DG'])
            timestamp = datetime.strptime(data['Data']['UpdatedOn'], '%d-%m-%Y %H:%M:%S')
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data validation error: {e}")
            return

        # Low Balance Alert
        if config.LOW_BALANCE_THRESHOLD and balance < float(config.LOW_BALANCE_THRESHOLD):
            today = datetime.now().date()
            if state.last_low_balance_alert_date != today:
                send_telegram_message(f"Low balance alert: Your meter balance is ₹{balance:.2f}.", config)
                state.last_low_balance_alert_date = today
        
        # DG Alert
        if state.last_dg_value is not None:
            if dg_value != state.last_dg_value and not state.is_dg_on:
                # DG is on
                send_telegram_message("Power is now on DG.", config)
                state.is_dg_on = True
            elif dg_value == state.last_dg_value and state.is_dg_on:
                # DG is off
                send_telegram_message("Power is now off DG.", config)
                state.is_dg_on = False
        state.last_dg_value = dg_value

        last_record = get_last_record(config.DATABASE)
        
        if last_record:
            previous_balance = last_record['balance']
            amount_used = max(previous_balance - balance, 0)
        else:
            amount_used = 0

        if not last_record or previous_balance != balance:
            timestamp_utc = pytz.timezone('Asia/Kolkata').localize(timestamp).astimezone(pytz.utc)
            c.execute('''
                INSERT INTO power_usage (timestamp, balance, present_load, amount_used)
                VALUES (?, ?, ?, ?)
            ''', (
                timestamp_utc.replace(tzinfo=None),
                balance,
                present_load,
                amount_used
            ))
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if conn:
            conn.close()