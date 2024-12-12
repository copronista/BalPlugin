from datetime import datetime,timedelta
import bisect
from electrum.gui.qt.util import getSaveFileName
from electrum.i18n import _
from electrum.transaction import PartialTxOutput
import urllib.request
import urllib.parse
from electrum.util import write_json_file,FileImportFailed,FileExportFailed

LOCKTIME_THRESHOLD = 500000000
def locktime_to_str(locktime):
    try:
        locktime=int(locktime)
        if locktime > LOCKTIME_THRESHOLD:
            dt = datetime.fromtimestamp(locktime).isoformat()
            return dt

    except Exception as e:
        #print(e)
        pass
    return str(locktime)

def str_to_locktime(locktime):
    try:
        if locktime[-1] in ('y','d','b'):
          return locktime
        else: return int(locktime)
    except Exception as e:
        pass
        #print(e)
    dt_object = datetime.fromisoformat(locktime)
    timestamp = dt_object.timestamp()
    return int(timestamp)

def parse_locktime_string(locktime,w=None): 
    try: 
        return int(locktime) 
 
    except Exception as e: 
        pass
        #print("parse_locktime_string",e) 
    try: 
        now = datetime.now() 
        if locktime[-1] == 'y': 
            locktime = str(int(locktime[:-1])*365) + "d" 
        if locktime[-1] == 'd': 
            return int((now + timedelta(days = int(locktime[:-1]))).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()) 
        if locktime[-1] == 'b': 
            locktime = int(locktime[:-1]) 
            height = 0 
            if w: 
                height = get_current_height(w.network) 
            locktime+=int(height) 
        return int(locktime) 
    except Exception as e: 
        print("parse_locktime_string",e) 
        #raise e
    return 0


def int_locktime(seconds=0,minutes=0,hours=0, days=0, blocks = 0):
    return int(seconds + minutes*60 + hours*60*60 + days*60*60*24 + blocks * 600)

def encode_amount(amount, decimal_point):
    if is_perc(amount):
        return amount
    else:
        try:
            return int(float(amount)*pow(10,decimal_point))
        except:
            return 0

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

def cmp_array(heira,heirb):
    try:
        if not len(heira) == len(heirb):
            return False
        for h in range(0,len(heira)):
            if not heira[h] == heirb[h]:
                return False
        return True
    except:
        return False

def cmp_heir(heira,heirb):
    if heira[0] == heirb[0] and heira[1] == heirb[1]: 
        return True
    return False

def cmp_willexecutor(willexecutora,willexecutorb):
    if willexecutora == willexecutorb:
        return True
    try:
        if willexecutora['url']==willexecutorb['url'] and willexecutora['address'] == willexecutorb['address'] and willexecutora['base_fee']==willexecutorb['base_fee']:
            return True
    except:
        return False
    return False

def search_heir_by_values(heirs,heir,values):
    #print()
    for h,v in heirs.items():
        found = False
        for val in values:
            if val in v and v[val] != heir[val]:
                found = True

        if not found:
            return h
    return False

def cmp_heir_by_values(heira,heirb,values):
    for v in values:
        if heira[v] != heirb[v]:
            return False
    return True

def cmp_heirs_by_values(heirsa,heirsb,values,exclude_willexecutors=False,reverse = True):
    for heira in heirsa:
        if (exclude_willexecutors and not "w!ll3x3c\"" in heira) or not exclude_willexecutors:
            found = False
            for heirb in heirsb:
                if cmp_heir_by_values(heirsa[heira],heirsb[heirb],values):
                    found=True
            if not found:
                #print(f"not_found {heira}--{heirsa[heira]}")
                return False
    if reverse:
        return cmp_heirs_by_values(heirsb,heirsa,values,exclude_willexecutors=exclude_willexecutors,reverse=False)
    else:
        return True
    
def cmp_heirs(heirsa,heirsb,cmp_function = lambda x,y: x[0]==y[0] and x[3]==y[3],reverse=True):
    try:
        for heir in heirsa:
            if not "w!ll3x3c\"" in heir:
                if not heir in heirsb or not cmp_function(heirsa[heir],heirsb[heir]):
                    if not search_heir_by_values(heirsb,heirsa[heir],[0,3]):
                        return False
        if reverse:
            return cmp_heirs(heirsb,heirsa,cmp_function,False)
        else:
            return True
    except Exception as e:
        raise e
        return False

def cmp_inputs(inputsa,inputsb):
    if len(inputsa) != len(inputsb): 
        return False 
    for inputa in inputsa:
        if not in_utxo(inputa,inputsb):
            return False
    return True

def cmp_outputs(outputsa,outputsb,willexecutor_output = None):
    if len(outputsa) != len(outputsb): 
        return False 
    for outputa in outputsa: 
        if not cmp_output(outputa,willexecutor_output):
            if not in_output(outputa,outputsb): 
                return False
    return True

def cmp_txs(txa,txb):
    if not cmp_inputs(txa.inputs(),txb.inputs()):
        return False
    if not cmp_outputs(txa.outputs(),txb.outputs()):
        return False
    return True

def get_value_amount(txa,txb):
    outputsa=txa.outputs()
    outputsb=txb.outputs()
    value_amount = 0
    #if len(outputsa) != len(outputsb):
    #    print("outputlen is different")
    #    return False

    for outa in outputsa:
        same_amount,same_address = in_output(outa,txb.outputs())
        if not (same_amount or same_address):
            #print("outa notin txb", same_amount,same_address)
            return False
        if same_amount and same_address:
            value_amount+=outa.value
        if same_amount:
            pass
            #print("same amount")
        if same_address:
            pass
            #print("same address")

    return value_amount
    #not needed
    #for outb in outputsb:
    #    if not in_output(outb,txa.outputs()):
    #        print("outb notin txb")
    #        return False



def chk_locktime(timestamp_to_check,block_height_to_check,locktime):
    #TODO BUG:  WHAT HAPPEN AT THRESHOLD?
    locktime=int(locktime)
    if locktime > LOCKTIME_THRESHOLD and locktime > timestamp_to_check:
        return True
    elif locktime < LOCKTIME_THRESHOLD and locktime > block_height_to_check:
        return True
    else:
        return False

def anticipate_locktime(locktime,blocks=0,hours=0,days=0):
    locktime = int(locktime)
    out=0
    if locktime> LOCKTIME_THRESHOLD:
        seconds = blocks*600 + hours*3600 + days*86400
        dt = datetime.fromtimestamp(locktime)
        dt -= timedelta(seconds=seconds)
        out = dt.timestamp()
    else:
        blocks -= hours*6 + days*144
        out = locktime + blocks

    if out < 1:
        out = 1 
    return out

def cmp_locktime(locktimea,locktimeb):
    if locktimea==locktimeb:
        return 0
    strlocktime = str(locktimea)
    strlocktimeb = str(locktimeb)
    intlocktimea = str_to_locktime(strlocktimea)
    intlocktimeb = str_to_locktime(strlocktimeb)
    if locktimea[-1] in "ydb":
        if locktimeb[-1] == locktimea[-1]:
            return int(strlocktimea[-1])-int(strlocktimeb[-1])
        else:
            return int(locktimea)-(locktimeb)
    

def get_lowest_valid_tx(available_utxos,will):
    will = sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
    for txid,willitem in will.items():
        pass

def get_locktimes(will):
    locktimes = {}
    for txid,willitem in will.items():
        locktimes[willitem['tx'].locktime]=True
    return locktimes.keys()

def get_lowest_locktimes(locktimes):
    sorted_timestamp=[]
    sorted_block=[]
    for l in locktimes:
        #print("locktime:",parse_locktime_string(l))
        l=parse_locktime_string(l)
        if l < LOCKTIME_THRESHOLD:
            bisect.insort(sorted_block,l)
        else:
            bisect.insort(sorted_timestamp,l)

    return sorted(sorted_timestamp), sorted(sorted_block)

def get_lowest_locktimes_from_will(will):
    return get_lowest_locktimes(get_locktimes(will))

def search_willtx_per_io(will,tx):
    for wid, w in will.items():
        if cmp_txs(w['tx'],tx['tx']):
            return wid,w
    return None, None

def invalidate_will(will):
    raise Exception("not implemented")

def get_will_spent_utxos(will):
    utxos=[]
    for txid,willitem in will.items():
        utxos+=willitem['tx'].inputs()
        
    return utxos

def utxo_to_str(utxo):
    try: return utxo.to_str()
    except Exception as e: pass
    try: return utxo.prevout.to_str()
    except Exception as e: pass
    return str(utxo)

def cmp_utxo(utxoa,utxob):
    utxoa=utxo_to_str(utxoa)
    utxob=utxo_to_str(utxob)
    if utxoa == utxob:
    #if utxoa.prevout.txid==utxob.prevout.txid and utxoa.prevout.out_idx == utxob.prevout.out_idx:
        return True
    else:
        return False

def in_utxo(utxo, utxos):
    for s_u in utxos:
        if cmp_utxo(s_u,utxo):
            return True
    return False

def txid_in_utxo(txid,utxos):
    for s_u in utxos:
        if s_u.prevout.txid == txid:
            return True
    return False

def cmp_output(outputa,outputb):
    return outputa.address == outputb.address and outputa.value == outputb.value

def in_output(output,outputs):
    for s_o in outputs:
        if cmp_output(s_o,output):
            return True
    return False

#check all output with the same amount if none have the same address it can be a change
#return true true same address same amount 
#return true false same amount different address
#return false false different amount, different address not found


def din_output(out,outputs):
    same_amount=[]
    for s_o in outputs:
        if int(out.value) == int(s_o.value):
            same_amount.append(s_o)
            if out.address==s_o.address:
                #print("SAME_:",out.address,s_o.address)
                return True, True
            else:
                pass
                #print("NOT  SAME_:",out.address,s_o.address)

    if len(same_amount)>0:
        return True, False
    else:return False, False


def get_change_output(wallet,in_amount,out_amount,fee): 
    change_amount = int(in_amount - out_amount - fee) 
    if change_amount > wallet.dust_threshold(): 
        change_addresses = wallet.get_change_addresses_for_new_transaction() 
        out = PartialTxOutput.from_address_and_value(change_addresses[0], change_amount) 
        out.is_change = True 
        return out


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

def export_meta_gui(electrum_window: 'ElectrumWindow', title, exporter):
    filter_ = "All files (*)"
    filename = getSaveFileName(
        parent=electrum_window,
        title=_("Select file to save your {}").format(title),
        filename='BALplugin_{}'.format(title),
        filter=filter_,
        config=electrum_window.config,
    )
    if not filename:
        return
    try:
        exporter(filename)
    except FileExportFailed as e:
        electrum_window.show_critical(str(e))
    else:
        electrum_window.show_message(_("Your {0} were exported to '{1}'")
                                 .format(title, str(filename)))


