from datetime import datetime, timedelta, timezone

GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc,)

def gpsweek_tow_to_datetime(week: int, tow: float) -> datetime:
    return GPS_EPOCH + timedelta(weeks=week, seconds=tow)