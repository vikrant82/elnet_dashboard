from datetime import datetime

class State:
    def __init__(self):
        self.last_low_balance_alert_date = None
        self.last_dg_value = None
        self.last_dg_alert_timestamp = None