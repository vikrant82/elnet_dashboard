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
                amount_used REAL,
                recharge_amount REAL DEFAULT 0
            )
        ''')
        
        c.execute('CREATE INDEX IF NOT EXISTS timestamp_idx ON power_usage(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS recharge_amount_idx ON power_usage(recharge_amount)')
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
            # Handle both old records (4 columns) and new records (5 columns)
            return {
                'timestamp': record[1],
                'balance': record[2],
                'present_load': record[3],
                'amount_used': record[4],
                'recharge_amount': record[5] if len(record) > 5 else 0
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
        
        # DG Alert - Enhanced logic with timestamp validation to handle stale data
        if state.last_dg_value is not None and state.last_updated_timestamp is not None:
            # Only process DG changes if the data is fresh (timestamp has changed)
            if timestamp != state.last_updated_timestamp:
                # Data is fresh, check for DG state changes
                if dg_value != state.last_dg_value and not state.is_dg_on:
                    # DG is on
                    send_telegram_message("Power is now on DG.", config)
                    state.is_dg_on = True
                elif dg_value == state.last_dg_value and state.is_dg_on:
                    # DG is off (only if DG value is actually 0 or unchanged from a non-zero value)
                    send_telegram_message("Power is now off DG.", config)
                    state.is_dg_on = False
            # If timestamp is the same, data is stale - ignore DG state evaluation
        state.last_dg_value = dg_value
        state.last_updated_timestamp = timestamp

        last_record = get_last_record(config.DATABASE)
        
        amount_used = 0
        recharge_amount = 0
        
        if last_record:
            previous_balance = last_record['balance']
            balance_change = previous_balance - balance
            
            if balance_change > 0:
                # Normal usage - balance decreased
                amount_used = balance_change
            elif balance_change < 0:
                # Meter recharge - balance increased
                recharge_amount = abs(balance_change)
                # Send recharge alert
                send_telegram_message(f"Meter recharged: ₹{recharge_amount:.2f} added. Current balance: ₹{balance:.2f}", config)
            # If balance_change == 0, no change in balance
        # If no last_record, this is the first entry

        if not last_record or previous_balance != balance:
            timestamp_utc = pytz.timezone('Asia/Kolkata').localize(timestamp).astimezone(pytz.utc)
            c.execute('''
                INSERT INTO power_usage (timestamp, balance, present_load, amount_used, recharge_amount)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timestamp_utc.replace(tzinfo=None),
                balance,
                present_load,
                amount_used,
                recharge_amount
            ))
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if conn:
            conn.close()