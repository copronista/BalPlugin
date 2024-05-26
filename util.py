from datetime import datetime
def locktime_to_str(locktime):
    try:
        locktime=int(locktime)
        if locktime > 500000000:
            dt = datetime.fromtimestamp(locktime).isoformat()[:-3]
            return dt

    except Exception as e:
        print(e)
        pass
    return str(locktime)

def str_to_locktime(locktime):
    try:
        if locktime[-1] in ('y','d','b'):
          return locktime
        else: return int(locktime)
    except Exception as e:
        print(e)
    dt_object = datetime.fromisoformat(locktime)
    timestamp = dt_object.timestamp()
    return int(timestamp)
