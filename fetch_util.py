import time
from googleapiclient.errors import HttpError
def call(req):
    for attempt in range(20):
        try:
            return req.execute()
        except HttpError as e:
            if e.resp.status not in (403, 429, 500, 503): raise
            time.sleep(min(60, 2 ** attempt))
        except (OSError, ConnectionError):
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError("demasiados reintentos")
