from datetime import datetime
def locktime_to_str(locktime):
    try:
        locktime=int(locktime)
        print(locktime,locktime > 500000000)
        if locktime > 500000000:
            dt_object = datetime.fromtimestamp(locktime)
            return dt_object.strftime("%d/%m/%Y %H:%M")

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
    dt_object = datetime.strptime(locktime, "%d/%m/%Y %H:%M")
    timestamp = dt_object.timestamp()
    return int(timestamp)

