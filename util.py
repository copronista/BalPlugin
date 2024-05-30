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

def encode_amount(amount, decimal_point):
    if is_perc(amount):
        return amount
    else:
        return int(float(amount)*pow(10,decimal_point))

def decode_amount(amount,decimal_point):
    if is_perc(amount):
        return amount
    else:
        return str(float(amount)/pow(10,decimal_point))

def is_perc(value): 
        try:
            return value[-1] == '%'
        except:
            return False


def print_var(var):
    try:
        print("str:",str(var))
    except Exception as e:
        print(e)
    try:
        print("repr:",repr(var))
    except Exception as e: 
        print(e)
    try:
        print("dict:",dict(var))
    except Exception as e: 
        print(e)
    try:
        print("dir:",dir(var))
    except Exception as e:
        print(e)
    try:
        print("type:",type(var))
    except Exception as e:
        print(e)

