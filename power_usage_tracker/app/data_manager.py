import sqlite3
from datetime import datetime, timedelta
import pytz
import logging
import statistics
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
            eb_value = float(data['Data']['EB'])
            timestamp = datetime.strptime(data['Data']['UpdatedOn'], '%d-%m-%Y %H:%M:%S')
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data validation error: {e}")
            return

        # === START: Data Validation and Anomaly Checks ===

        # 1. Check for stale data from the API
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        now_kolkata = datetime.now(kolkata_tz)
        timestamp_kolkata = kolkata_tz.localize(timestamp)

        if (now_kolkata - timestamp_kolkata) > timedelta(minutes=5):
            logger.warning(f"Stale data from API. Timestamp is older than 5 minutes: {timestamp_kolkata}. Skipping.")
            return

        # 2. Check for anomalous zero-value data
        if balance == 0 and eb_value == 0 and dg_value == 0:
            logger.warning(f"Received anomalous zero-value data for timestamp {timestamp}. Skipping storage.")
            return

        # === END: Data Validation and Anomaly Checks ===

        # Low Balance Alert
        if config.LOW_BALANCE_THRESHOLD and balance < float(config.LOW_BALANCE_THRESHOLD):
            today = datetime.now().date()
            if state.last_low_balance_alert_date != today:
                send_telegram_message(f"Low balance alert: Your meter balance is ₹{balance:.2f}.", config)
                state.last_low_balance_alert_date = today
        
        # DG Alert and Data Inconsistency Logic
        if state.last_updated_timestamp and timestamp != state.last_updated_timestamp:
            is_balance_changed = state.last_balance_value != balance
            is_dg_changed = state.last_dg_value != dg_value
            is_eb_changed = state.last_eb_value != eb_value
            
            logger.info(f"DG Check: is_dg_on={state.is_dg_on}, dg_value={dg_value}, last_dg_value={state.last_dg_value}, is_dg_changed={is_dg_changed}")
            logger.info(f"EB Check: eb_value={eb_value}, last_eb_value={state.last_eb_value}, is_eb_changed={is_eb_changed}")
            logger.info(f"Balance Check: balance={balance}, last_balance_value={state.last_balance_value}, is_balance_changed={is_balance_changed}")

            # 3. Detect Inconsistent API Data (Balance changes but consumption doesn't)
            if is_balance_changed and not is_eb_changed and not is_dg_changed:
                logger.warning(f"Data inconsistency detected: Balance changed from {state.last_balance_value} to {balance}, but EB and DG readings are static.")

            # 4. Detect PresentLoad Spikes
            if len(state.recent_loads) > 5:  # Ensure we have enough data for a stable average
                average_load = statistics.mean(state.recent_loads)
                # A spike is an unusually high value compared to the recent average
                if present_load > (average_load * 3) and present_load > 2.0:
                    logger.warning(f"Anomalous spike in PresentLoad detected: {present_load:.2f} (recent average was {average_load:.2f})")
            
            # Maintain a rolling list of the last 10 load readings
            state.recent_loads.append(present_load)
            if len(state.recent_loads) > 10:
                state.recent_loads.pop(0)

            # Condition to detect switch TO DG:
            if not state.is_dg_on and is_dg_changed and is_balance_changed and not is_eb_changed:
                send_telegram_message(f"Power is now on DG. Current Balance: ₹{balance:.2f}", config)
                state.is_dg_on = True
                state.dg_state_changed_at = datetime.now()

            # Condition to detect switch FROM DG:
            elif state.is_dg_on and is_eb_changed and is_balance_changed and not is_dg_changed:
                send_telegram_message(f"Power is now off DG (Switched to EB). Current Balance: ₹{balance:.2f}", config)
                state.is_dg_on = False
                state.dg_state_changed_at = datetime.now()
        
        # Update state for next iteration
        state.last_dg_value = dg_value
        state.last_eb_value = eb_value
        state.last_balance_value = balance
        state.last_updated_timestamp = timestamp

        last_record = get_last_record(config.DATABASE)
        
        amount_used = 0
        recharge_amount = 0
        
        if last_record:
            previous_balance = last_record['balance']
            balance_change = previous_balance - balance
            
            if 0 < balance_change < 50: # Assuming usage in a 30-sec interval won't exceed Rs. 50
                amount_used = balance_change
            elif balance_change < 0:
                recharge_amount = abs(balance_change)
                send_telegram_message(f"Meter recharged: ₹{recharge_amount:.2f} added. Current balance: ₹{balance:.2f}", config)
        
        if not last_record or last_record['balance'] != balance:
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