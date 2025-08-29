from datetime import datetime

class State:
    def __init__(self):
        self.last_low_balance_alert_date = None
        self.last_dg_value = None
        self.last_eb_value = None
        self.last_balance_value = None
        self.last_updated_timestamp = None
        self.is_dg_on = False
        self.dg_state_changed_at = None
        self.dg_unchanged_counter = 0
        self.recent_loads = []