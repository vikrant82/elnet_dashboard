from flask import Blueprint, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

def get_recent_recharges(database_path, limit=5):
    """Fetch recent recharge records from database"""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()
        
        # Query for recent recharges (where recharge_amount > 0)
        c.execute('''
            SELECT timestamp, recharge_amount
            FROM power_usage
            WHERE recharge_amount > 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        records = c.fetchall()
        return [{'timestamp': record[0], 'amount': float(record[1])} for record in records]
            
    except sqlite3.Error as e:
        logger.error(f"Database error fetching recharges: {e}")
        return []
    finally:
        if conn:
            conn.close()

def create_dashboard_bp(api_client, config, state=None):
    dashboard_bp = Blueprint('dashboard', __name__)

    @dashboard_bp.route('/dash_data')
    def dashboard():
        try:
            conn = sqlite3.connect(config.DATABASE)
            c = conn.cursor()
            
            try:
                interval_hours = min(int(request.args.get('interval', 24)), 720)
                group_minutes = min(int(request.args.get('group', 30)), 1440)
            except ValueError:
                return jsonify({'error': 'Invalid interval or group parameter'}), 400
                
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            interval_start_utc = now_utc - timedelta(hours=interval_hours)
            
            logger.debug(f"Interval hours: {interval_hours}")
            logger.debug(f"Interval start time (UTC): {interval_start_utc}")
            
            query = '''
                SELECT
                    strftime('%Y-%m-%d %H:%M', timestamp, '-' ||
                        (strftime('%M', timestamp) % ?) || ' minutes') AS bucket,
                    SUM(amount_used) AS total_amount_used
                FROM power_usage
                WHERE timestamp >= ?
                GROUP BY bucket
                ORDER BY bucket
            '''
            
            c.execute(query, (group_minutes, interval_start_utc.replace(tzinfo=None)))
            records = c.fetchall()
            
            data = []
            for record in records:
                try:
                    bucket_time = datetime.strptime(record[0], '%Y-%m-%d %H:%M')
                    bucket_utc = pytz.utc.localize(bucket_time)
                    
                    data.append({
                        'timestamp': bucket_utc.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                        'amount_used': float(record[1])
                    })
                except (ValueError, TypeError) as e:
                    logger.error(f"Bucket parsing error: {e}")
                    continue
            
            return jsonify(data)
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
        finally:
            if conn:
                conn.close()

    @dashboard_bp.route('/')
    def index():
        home_data = api_client.fetch_home_data()
        recent_recharges = get_recent_recharges(config.DATABASE)
        
        # Prepare DG status data
        dg_status = {
            'is_dg_on': False,
            'duration': ''
        }
        
        if state:
            dg_status['is_dg_on'] = state.is_dg_on
            if state.is_dg_on and state.dg_state_changed_at:
                # Calculate duration
                duration = datetime.now() - state.dg_state_changed_at
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                if hours > 0:
                    dg_status['duration'] = f"{hours}h {minutes}m"
                else:
                    dg_status['duration'] = f"{minutes}m"
            elif not state.is_dg_on and state.dg_state_changed_at:
                # Show how long we've been on EB
                duration = datetime.now() - state.dg_state_changed_at
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                if hours > 0:
                    dg_status['duration'] = f"{hours}h {minutes}m"
                else:
                    dg_status['duration'] = f"{minutes}m"
        
        if home_data and home_data.get('Data'):
            data = home_data['Data']
            now = datetime.now()
            
            # Daily Average
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            hours_since_sod = (now - start_of_day).total_seconds() / 3600
            if hours_since_sod > 0:
                data['daily_avg_eb'] = (float(data.get('CurrentDay_EB', 0)) / hours_since_sod / 8.33) * 1000
                data['daily_avg_dg'] = (float(data.get('CurrentDay_DG', 0)) / hours_since_sod / 8.33) * 1000
            else:
                data['daily_avg_eb'] = 0
                data['daily_avg_dg'] = 0

            # Monthly Average
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            hours_since_som = (now - start_of_month).total_seconds() / 3600
            if hours_since_som > 0:
                data['monthly_avg_eb'] = (float(data.get('CurrentMonth_EB', 0)) / hours_since_som / 8.33) * 1000
                data['monthly_avg_dg'] = (float(data.get('CurrentMonth_DG', 0)) / hours_since_som / 8.33) * 1000
            else:
                data['monthly_avg_eb'] = 0
                data['monthly_avg_dg'] = 0

        return render_template('dashboard.html',
                             home_data=home_data.get('Data') if home_data else None,
                             recent_recharges=recent_recharges,
                             dg_status=dg_status)

    return dashboard_bp
