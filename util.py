from datetime import datetime
import bisect
LOCKTIME_THRESHOLD = 500000000
def locktime_to_str(locktime):
    try:
        locktime=int(locktime)
        if locktime > LOCKTIME_THRESHOLD:
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

def cmp_txs(txa,txb):
    return txa.inputs() == txb.inputs() and txa.outputs == txb.outputs()

def chk_locktime(timestamp_to_check,block_height_to_check,locktime):
    #TODO BUG:  WHAT HAPPEN AT THRESHOLD?
    if locktime > LOCKTIME_THRESHOLD and locktime < timestamp_to_check:
        return True
    elif locktime <LOCKTIME_THRESHOLD and locktime < block_height_to_check:
        return True
    else:
        return False

def get_lowest_valid_tx(available_utxos,will):
    will = sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
    for txid,willitem in will.items():
        pass

def get_locktimes(will):
    locktimes = {}
    for txid,willitem in will.items():
        locktimes[willitem['tx'].locktime]=True

def get_lowest_locktimes(locktimes):
    sorted_timestamp=[]
    sorted_block=[]
    for l in locktimes:
        if l < LOCKTIME_THRESHOLD:
            bisect.insort(sorted_block,l)
        else:
            bisect.insort(sorted_timestamp,l)

    return sorted(sorted_blocks),sorted(sorted_timestamp)

def get_lowest_locktimes_from_will(will):
    return get_lowest_locktimes(get_locktimes(will))

def search_willtx_per_io(will,tx):
    for wid, w in will.items():
        if cmp_txs(w['tx'],tx):
            return wid,w
    return None, None

def invalidate_will(will):
    pass

def get_current_height(network:'Network'):
    #if no network or not up to date, just set locktime to zero
    if not network:
        return 0
    chain = network.blockchain()
    if chain.is_tip_stale():
        return 0
    # figure out current block height
    chain_height = chain.height()  # learnt from all connected servers, SPV-checked
    server_height = network.get_server_height()  # height claimed by main server, unverified
    # note: main server might be lagging (either is slow, is malicious, or there is an SPV-invisible-hard-fork)
    #       - if it's lagging too much, it is the network's job to switch away
    if server_height < chain_height - 10:
        # the diff is suspiciously large... give up and use something non-fingerprintable
        return 0
    # discourage "fee sniping"
    height = min(chain_height, server_height)
    return height


def print_var(var,name = "",veryverbose=False):
    print(f"---{name}---")
    if not var is None:
        try:
            print("doc:",doc(var))
        except: pass
        try:
            print("str:",str(var))
        except: pass
        try:
            print("repr",repr(var))
        except:pass
        try:
            print("dict",dict(var))
        except:pass
        try:
            print("dir",dir(var))
        except:pass
        try:
            print("type",type(var))
        except:pass
        try:
            print("to_json",var.to_json())
        except: pass
        try:
            print("__slotnames__",var.__slotnames__)
        except:pass

    print(f"---end {name}---")

def print_utxo(utxo, name = ""):
    print(f"---utxo-{name}---")
    print_var(utxo,name)
    print_prevout(utxo.prevout,name)
    print_var(utxo.script_sig,f"{name}-script-sig")
    print_var(utxo.witness,f"{name}-witness")
    #print("madonnamaiala_TXInput__scriptpubkey:",utxo._TXInput__scriptpubkey)
    print("_TxInput__address:",utxo._TxInput__address)
    print("_TxInput__scriptpubkey:",utxo._TxInput__scriptpubkey)
    print("_TxInput__value_sats:",utxo._TxInput__value_sats)
    print(f"---utxo-end {name}---")

def print_prevout(prevout, name = ""):
    print(f"---prevout-{name}---")
    print_var(prevout,f"{name}-prevout")
    print_var(prevout._asdict())
    print(f"---prevout-end {name}---")

