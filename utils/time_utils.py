from datetime import datetime, timedelta
import pytz

EST = pytz.timezone("US/Eastern")
UTC = pytz.UTC
PST = pytz.timezone("US/Pacific")
PH = pytz.timezone("Asia/Manila")

def get_est_day_range(date=None):
    if not date:
        date = datetime.now(EST).date()
    start = EST.localize(datetime.combine(date, datetime.min.time()))
    end = start + timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)

def get_now_est():
    return datetime.now(EST)

def get_now_pst():
    return datetime.now(PST)

def get_now_ph():
    return datetime.now(PH)