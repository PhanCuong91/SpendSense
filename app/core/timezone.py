from datetime import datetime
from dateutil import tz
from app.core.config import settings

SGT = tz.gettz(settings.TZ)


def now_sgt():
    return datetime.now(tz=SGT)


def to_sgt(dt: datetime):
    if not dt:
        return None
    return dt.astimezone(SGT)