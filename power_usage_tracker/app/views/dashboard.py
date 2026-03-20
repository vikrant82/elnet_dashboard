from flask import Blueprint, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)


def format_duration(delta):
    """Format a timedelta as a compact hours/minutes string."""
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def build_dg_status(state):
    """Build DG/EB status dictionary for dashboard rendering and APIs."""
    dg_status = {"is_dg_on": False, "duration": ""}

    if not state:
        return dg_status

    dg_status["is_dg_on"] = state.is_dg_on

    if state.dg_state_changed_at:
        duration = datetime.now() - state.dg_state_changed_at
        dg_status["duration"] = format_duration(duration)

    return dg_status


def get_recent_recharges(database_path, limit=5):
    """Fetch recent recharge records from database"""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()

        # Query for recent recharges (where recharge_amount > 0)
        c.execute(
            """
            SELECT timestamp, recharge_amount
            FROM power_usage
            WHERE recharge_amount > 0
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        records = c.fetchall()
        return [
            {"timestamp": record[0], "amount": float(record[1])} for record in records
        ]

    except sqlite3.Error as e:
        logger.error(f"Database error fetching recharges: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_latest_power_snapshot(database_path):
    """Fetch latest power row from DB for lightweight live UI updates."""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()
        c.execute("""
            SELECT timestamp, present_load, balance
            FROM power_usage
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        record = c.fetchone()
        if not record:
            return None

        timestamp_utc = datetime.fromisoformat(record[0]).replace(tzinfo=pytz.utc)
        return {
            "timestamp": timestamp_utc,
            "present_load": float(record[1]),
            "balance": float(record[2]),
        }
    except (sqlite3.Error, TypeError, ValueError) as e:
        logger.error(f"Database error fetching latest power snapshot: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_recent_present_loads(database_path, minutes=15, limit=180):
    """Fetch recent present-load values for the live sparkline."""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()

        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        window_start_utc = now_utc - timedelta(minutes=minutes)

        c.execute(
            """
            SELECT timestamp, present_load
            FROM power_usage
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (window_start_utc.replace(tzinfo=None), limit),
        )
        records = c.fetchall()

        points = []
        for timestamp_str, present_load in records:
            try:
                timestamp_utc = datetime.fromisoformat(timestamp_str).replace(
                    tzinfo=pytz.utc
                )
                points.append(
                    {
                        "timestamp": timestamp_utc.isoformat(),
                        "present_load_kw": float(present_load),
                    }
                )
            except (TypeError, ValueError):
                continue

        return points
    except sqlite3.Error as e:
        logger.error(f"Database error fetching recent present loads: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_bucketed_amount_usage(
    database_path, interval_start_utc, interval_end_utc, group_minutes
):
    """Fetch grouped amount-used rows for a UTC interval."""
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        c = conn.cursor()
        c.execute(
            """
            SELECT
                strftime('%Y-%m-%d %H:%M', timestamp, '-' ||
                    (strftime('%M', timestamp) % ?) || ' minutes') AS bucket,
                SUM(amount_used) AS total_amount_used
            FROM power_usage
            WHERE timestamp >= ?
              AND timestamp <= ?
            GROUP BY bucket
            ORDER BY bucket
            """,
            (
                group_minutes,
                interval_start_utc.replace(tzinfo=None),
                interval_end_utc.replace(tzinfo=None),
            ),
        )

        records = c.fetchall()
        parsed_records = []

        for bucket_str, total_amount_used in records:
            try:
                bucket_time = datetime.strptime(bucket_str, "%Y-%m-%d %H:%M")
                parsed_records.append((bucket_time, float(total_amount_used or 0)))
            except (TypeError, ValueError):
                continue

        return parsed_records
    except sqlite3.Error as e:
        logger.error(f"Database error fetching bucketed amount usage: {e}")
        return []
    finally:
        if conn:
            conn.close()


def serialize_bucket_amount_rows(rows):
    """Serialize bucketed rows into dashboard chart JSON format."""
    data = []
    for bucket_time, amount_used in rows:
        bucket_utc = pytz.utc.localize(bucket_time)
        data.append(
            {
                "timestamp": bucket_utc.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "amount_used": float(amount_used),
            }
        )
    return data


def create_dashboard_bp(api_client, config, state=None):
    dashboard_bp = Blueprint("dashboard", __name__)

    @dashboard_bp.route("/dash_data")
    def dashboard():
        try:
            try:
                interval_hours = min(max(int(request.args.get("interval", 24)), 1), 720)
                group_minutes = min(max(int(request.args.get("group", 30)), 1), 1440)
            except ValueError:
                return jsonify({"error": "Invalid interval or group parameter"}), 400

            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            interval_start_utc = now_utc - timedelta(hours=interval_hours)

            logger.debug(f"Interval hours: {interval_hours}")
            logger.debug(f"Interval start time (UTC): {interval_start_utc}")

            rows = get_bucketed_amount_usage(
                config.DATABASE,
                interval_start_utc,
                now_utc,
                group_minutes,
            )

            return jsonify(serialize_bucket_amount_rows(rows))

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @dashboard_bp.route("/dash_compare")
    def dash_compare():
        """Return historical averaged comparison series for chart overlay."""
        try:
            try:
                interval_hours = min(max(int(request.args.get("interval", 24)), 1), 720)
                group_minutes = min(max(int(request.args.get("group", 30)), 1), 1440)
                compare_days = min(max(int(request.args.get("days", 7)), 1), 30)
            except ValueError:
                return (
                    jsonify({"error": "Invalid interval, group, or days parameter"}),
                    400,
                )

            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            interval_start_utc = now_utc - timedelta(hours=interval_hours)

            current_rows = get_bucketed_amount_usage(
                config.DATABASE,
                interval_start_utc,
                now_utc,
                group_minutes,
            )

            historical_rows = get_bucketed_amount_usage(
                config.DATABASE,
                interval_start_utc - timedelta(days=compare_days),
                now_utc - timedelta(days=1),
                group_minutes,
            )
            historical_map = {
                bucket_time: amount for bucket_time, amount in historical_rows
            }

            points = []
            day_offsets_with_data = set()

            for bucket_time, _ in current_rows:
                historical_values = []
                for day_offset in range(1, compare_days + 1):
                    shifted_bucket = bucket_time - timedelta(days=day_offset)
                    amount = historical_map.get(shifted_bucket)
                    if amount is None:
                        continue
                    historical_values.append(amount)
                    day_offsets_with_data.add(day_offset)

                avg_amount_used = None
                if historical_values:
                    avg_amount_used = sum(historical_values) / len(historical_values)

                points.append(
                    {
                        "timestamp": pytz.utc.localize(bucket_time).strftime(
                            "%a, %d %b %Y %H:%M:%S GMT"
                        ),
                        "avg_amount_used": avg_amount_used,
                        "sample_count": len(historical_values),
                    }
                )

            return jsonify(
                {
                    "days_requested": compare_days,
                    "days_available": len(day_offsets_with_data),
                    "points": points,
                }
            )
        except Exception as e:
            logger.error(f"Unexpected error in dash_compare: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @dashboard_bp.route("/live_status")
    def live_status():
        """Return latest data for live widgets (dial and source badge)."""
        latest = get_latest_power_snapshot(config.DATABASE)
        dg_status = build_dg_status(state)

        if not latest:
            return jsonify(
                {
                    "present_load_kw": 0,
                    "balance": None,
                    "timestamp": None,
                    "last_successful_fetch": None,
                    "health": "unavailable",
                    "is_stale": True,
                    "age_seconds": None,
                    "is_dg_on": dg_status["is_dg_on"],
                    "duration": dg_status["duration"],
                }
            )

        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        age_seconds = int((now_utc - latest["timestamp"]).total_seconds())
        is_stale = age_seconds > 300

        return jsonify(
            {
                "present_load_kw": latest["present_load"],
                "balance": latest["balance"],
                "timestamp": latest["timestamp"].isoformat(),
                "last_successful_fetch": latest["timestamp"].isoformat(),
                "health": "stale" if is_stale else "healthy",
                "is_stale": is_stale,
                "age_seconds": age_seconds,
                "is_dg_on": dg_status["is_dg_on"],
                "duration": dg_status["duration"],
            }
        )

    @dashboard_bp.route("/live_trend")
    def live_trend():
        """Return short-window present load data for sparkline rendering."""
        try:
            window_minutes = int(request.args.get("minutes", 15))
        except ValueError:
            return jsonify({"error": "Invalid minutes parameter"}), 400

        window_minutes = min(max(window_minutes, 5), 120)
        points = get_recent_present_loads(config.DATABASE, minutes=window_minutes)

        return jsonify(
            {
                "window_minutes": window_minutes,
                "points": points,
            }
        )

    @dashboard_bp.route("/")
    def index():
        home_data = api_client.fetch_home_data()
        recent_recharges = get_recent_recharges(config.DATABASE)
        dg_status = build_dg_status(state)

        if home_data and home_data.get("Data"):
            data = home_data["Data"]
            now = datetime.now()

            # Daily Average
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            hours_since_sod = (now - start_of_day).total_seconds() / 3600
            if hours_since_sod > 0:
                data["daily_avg_eb"] = (
                    float(data.get("CurrentDay_EB", 0)) / hours_since_sod / 8.33
                ) * 1000
                data["daily_avg_dg"] = (
                    float(data.get("CurrentDay_DG", 0)) / hours_since_sod / 8.33
                ) * 1000
            else:
                data["daily_avg_eb"] = 0
                data["daily_avg_dg"] = 0

            # Monthly Average
            start_of_month = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            hours_since_som = (now - start_of_month).total_seconds() / 3600
            if hours_since_som > 0:
                data["monthly_avg_eb"] = (
                    float(data.get("CurrentMonth_EB", 0)) / hours_since_som / 8.33
                ) * 1000
                data["monthly_avg_dg"] = (
                    float(data.get("CurrentMonth_DG", 0)) / hours_since_som / 8.33
                ) * 1000
            else:
                data["monthly_avg_eb"] = 0
                data["monthly_avg_dg"] = 0

        return render_template(
            "dashboard.html",
            home_data=home_data.get("Data") if home_data else None,
            recent_recharges=recent_recharges,
            dg_status=dg_status,
        )

    return dashboard_bp
