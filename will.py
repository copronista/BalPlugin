import copy

from . import willexecutors as Willexecutors
from . import util as Util

from electrum.i18n import _

from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any,PartialTransaction,PartialTxOutput,Transaction
from electrum.util import bfh, decimal_point_to_base_unit_name
from electrum.util import write_json_file,read_json_file,FileImportFailed
from electrum.logging import get_logger,Logger
from electrum.bitcoin import NLOCKTIME_BLOCKHEIGHT_MAX

MIN_LOCKTIME = 1
MIN_BLOCK = 1
_logger = get_logger(__name__)

#return an array with the list of children
def get_children(will,willid):
    out = []
    for _id in will:
        inputs = will[_id].tx.inputs()
        for idi in range(0,len(inputs)):
            _input = inputs[idi]
            if _input.prevout.txid.hex() == willid:
                out.append([_id,idi,_input.prevout.out_idx])
    return out

#build a tree with parent transactions
def add_willtree(will):
    for willid in will:
        will[willid].children = get_children(will,willid)
        for child in will[willid].children:
            if not will[child[0]].father: 
                will[child[0]].father = willid


#return a list of will sorted by locktime
def get_sorted_will(will):
    return sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
                

def only_valid(will):
    for k,v in will.items():
        if v.get_status('VALID'):
            yield k

def search_equal_tx(will,tx,wid):
    for w in will:
        if  w != wid and not tx.to_json() != will[w]['tx'].to_json():
            if will[w]['tx'].txid() != tx.txid():
                if Util.cmp_txs(will[w]['tx'],tx):
                    return will[w]['tx']
    return False

def get_tx_from_any(x):
    try:
        a=str(x)
        return tx_from_any(a)
        
    except Exception as e:
        raise e

    return x

def add_info_from_will(will,wid,wallet):
    if isinstance(will[wid].tx,str):
        will[wid].tx = get_tx_from_any(will[wid].tx)
    if wallet:
        will[wid].tx.add_info_from_wallet(wallet)
    for txin in will[wid].tx.inputs():
        txid = txin.prevout.txid.hex()
        if txid in will:
            change = will[txid].tx.outputs()[txin.prevout.out_idx]
            txin._trusted_value_sats = change.value
            try:
                txin.script_descriptor = change.script_descriptor
            except:
                pass
            txin.is_mine=True
            txin._TxInput__address=change.address
            txin._TxInput__scriptpubkey = change.scriptpubkey
            txin._TxInput__value_sats = change.value
            txin._trusted_value_sats = change.value

def normalize_will(will,wallet = None,others_inputs = {}):
    to_delete = []
    to_add = {}
    #add info from wallet
    for wid in will:
        add_info_from_will(will,wid,wallet)
    errors ={}
    for wid in will:

        txid = will[wid].tx.txid()

        if txid is None:
            _logger.error("##########")
            _logger.error(wid)
            _logger.error(will[wid])
            _logger.error(will[wid].tx.to_json())
            
            _logger.error("txid is none")
            will[wid].set_status('ERROR',True)
            errors[wid]=will[wid]
            continue

        if txid != wid:
            outputs = will[wid].tx.outputs()
            ow=will[wid]
            ow.normalize_locktime(others_inputs)
            will[wid]=ow.to_dict()

            for i in range(0,len(outputs)):
                change_input(will,wid,i,outputs[i],others_inputs,to_delete,to_add)

            to_delete.append(wid)
            to_add[ow.tx.txid()]=ow.to_dict()

    for eid,err in errors.items():
        new_txid = err.tx.txid()

    for k,w in to_add.items():
        will[k] = w

    for wid in to_delete:
        if wid in will:
            del will[wid]

def new_input(txid,idx,change):
    prevout = TxOutpoint(txid=bfh(txid), out_idx=idx)
    inp = PartialTxInput(prevout=prevout)
    inp._trusted_value_sats = change.value
    inp.is_mine=True
    inp._TxInput__address=change.address
    inp._TxInput__scriptpubkey = change.scriptpubkey
    inp._TxInput__value_sats = change.value
    return inp

def check_anticipate(ow:'WillItem',nw:'WillItem'):
    anticipate = Util.anticipate_locktime(ow.tx.locktime,days=1)
    if int(nw.tx.locktime) >= int(anticipate):
        if Util.cmp_heirs_by_values(ow.heirs,nw.heirs,[0,1],exclude_willexecutors = True):
            if nw.we and ow.we:
                if ow.we['url'] == nw.we['url']:
                    if int(ow.we['base_fee'])>int(nw.we['base_fee']):
                        return anticipate
                    else:
                        _logger.debug("ow,base fee > nw.base_fee")
                        ow.tx.locktime
                else:
                    _logger.debug("ow.we['url']({ow.we['url']}) == nw.we['url']({nw.we['url']})")
                    ow.tx.locktime
            else:
                if nw.we == ow.we:
                    if not Util.cmp_heirs_by_values(ow.heirs,nw.heirs,[0,3]):
                        return anticipate
                    else:
                        return ow.tx.locktime
                else:
                    return ow.tx.locktime
        else:
            return anticipate
    return  4294967295+1

     
def change_input(will, otxid, idx, change,others_inputs,to_delete,to_append):
    ow = will[otxid]
    ntxid = ow.tx.txid()
    if otxid != ntxid:
        for wid in will:
            w = will[wid]
            inputs = w.tx.inputs()
            outputs = w.tx.outputs()
            found = False
            old_txid = w.tx.txid()
            ntx = None
            for i in range(0,len(inputs)):
                if inputs[i].prevout.txid.hex() == otxid and inputs[i].prevout.out_idx == idx:
                    if isinstance(w.tx,Transaction):
                        will[wid].tx = PartialTransaction.from_tx(w.tx)
                        will[wid].tx.set_rbf(True)
                    will[wid].tx._inputs[i]=new_input(wid,idx,change)
                    found = True
            if found == True:
                pass

            new_txid = will[wid].tx.txid()
            if old_txid != new_txid:
                to_delete.append(old_txid)
                to_append[new_txid]=will[wid]
                outputs = will[wid].tx.outputs()
                for i in range(0,len(outputs)):
                    change_input(will, wid, i, outputs[i],others_inputs,to_delete,to_append)
                    
def get_all_inputs(will,only_valid = False):
    all_inputs = {}
    for w,wi in will.items():
        if not only_valid or wi.get_status('VALID'):
            inputs = wi.tx.inputs()
            for i in inputs:
                prevout_str = i.prevout.to_str()
                inp=[w,will[w],i]
                if not prevout_str in all_inputs:
                    all_inputs[prevout_str] = [inp]
                else:
                    all_inputs[prevout_str].append(inp)
    return all_inputs

def get_all_inputs_min_locktime(all_inputs):
    all_inputs_min_locktime = {}
    
    for i,values in all_inputs.items():
        min_locktime = min(values,key = lambda x:x[1].tx.locktime)[1].tx.locktime
        for w in values:
            if w[1].tx.locktime == min_locktime:
                if not i in all_inputs_min_locktime:
                    all_inputs_min_locktime[i]=[w]
                else:
                     all_inputs_min_locktime[i].append(w)

    return all_inputs_min_locktime


def search_anticipate_rec(will,old_inputs):
    redo = False
    to_delete = []
    to_append = {}
    new_inputs = get_all_inputs(will,only_valid = True)
    for nid,nwi in will.items():
        if nwi.search_anticipate(new_inputs) or nwi.search_anticipate(old_inputs):
            if nid != nwi.tx.txid():
                redo = True
                to_delete.append(nid)
                to_append[nwi.tx.txid()] = nwi
                outputs = nwi.tx.outputs()
                for i in range(0,len(outputs)):
                    change_input(will,nid,i,outputs[i],new_inputs,to_delete,to_append)
                    

    for w in to_delete:
        try:
            del will[w]
        except:
            pass
    for k,w in to_append.items():
        will[k]=w
    if redo:
        search_anticipate_rec(will,old_inputs)


def update_will(old_will,new_will):
    all_old_inputs = get_all_inputs(old_will,only_valid=True)
    all_inputs_min_locktime = get_all_inputs_min_locktime(all_old_inputs)
    all_new_inputs = get_all_inputs(new_will)
    #check if the new input is already spent by other transaction
    #if it is use the same locktime, or anticipate.
    search_anticipate_rec(new_will,all_old_inputs)

    other_inputs = get_all_inputs(old_will,{})
    try:
        normalize_will(new_will,others_inputs=other_inputs)
    except Exception as e:
        raise e
                        

    for oid in only_valid(old_will):
        if oid in new_will:
            new_heirs = new_will[oid].heirs
            new_we = new_will[oid].we

            new_will[oid]=old_will[oid]
            new_will[oid].heirs = new_heirs
            new_will[oid].we = new_we

            continue
        else:
            continue

def get_higher_input_for_tx(will):
    out = {}
    for wid in will:
        wtx = will[wid].tx
        found = False
        for inp in wtx.inputs():
            if inp.prevout.txid.hex() in will:
                found = True
                break
        if not found:
            out[inp.prevout.to_str()] = inp
    return out

def invalidate_will(will,wallet,fees_per_byte):
    will_only_valid = only_valid_list(will)
    inputs = get_all_inputs(will_only_valid)
    utxos = wallet.get_utxos()
    filtered_inputs = []
    prevout_to_spend = []
    for prevout_str,ws in inputs.items(): 
        for w in ws:
            if not w[0] in filtered_inputs: 
                filtered_inputs.append(w[0])
                if not prevout_str in prevout_to_spend:
                    prevout_to_spend.append(prevout_str)
    balance = 0
    utxo_to_spend = []
    for utxo in utxos:
        utxo_str=utxo.prevout.to_str()
        if utxo_str in prevout_to_spend:
            balance += inputs[utxo_str][0][2].value_sats()
            utxo_to_spend.append(utxo)

    if len(utxo_to_spend) > 0: 
        change_addresses = wallet.get_change_addresses_for_new_transaction()
        out = PartialTxOutput.from_address_and_value(change_addresses[0], balance)
        out.is_change = True
        locktime = Util.get_current_height(wallet.network)
        tx = PartialTransaction.from_io(utxo_to_spend, [out], locktime=locktime, version=2)
        tx.set_rbf(True)
        fee=tx.estimated_size()*fees_per_byte
        if balance -fee >0:
            out = PartialTxOutput.from_address_and_value(change_addresses[0],balance - fee)
            tx = PartialTransaction.from_io(utxo_to_spend,[out], locktime=locktime, version=2)
            tx.set_rbf(True)
            
            _logger.debug(f"invalidation tx: {tx}")
            return tx

        else:
            _logger.debug("balance - fee <=0")
            pass
    else:
        _logger.debug("len utxo_to_spend <=0")
        pass


def is_new(will):
    for wid,w in will.items():
        if w.get_status('VALID') and not w.get_status('COMPLETE'):
            return True

def search_rai (all_inputs,all_utxos,will,wallet,callback_not_valid_tx=None):
    will_only_valid = only_valid_or_replaced_list(will)
    for inp,ws in all_inputs.items():
        inutxo = Util.in_utxo(inp,all_utxos)
        for w in ws:
            wi=w[1]
            if wi.get_status('VALID') or wi.get_status('CONFIRMED') or wi.get_status('PENDING'):
                prevout_id=w[2].prevout.txid.hex()
                if not inutxo:
                    if prevout_id in will:
                        wo=will[prevout_id]
                        if wo.get_status('REPLACED'):
                            wi.set_status('REPLACED',True)
                        if wo.get_status("INVALIDATED"):
                            wi.set_status('INVALIDATED',True)
                        
                    else:
                        if wallet.db.get_transaction(wi._id):
                            wi.set_status('CONFIRMED',True)
                        else:
                            wi.set_status('INVALIDATED',True)
                else:
                    if prevout_id in will:
                        wo = will[prevout_id]
                        ttx= wallet.db.get_transaction(prevout_id)
                        if ttx:
                            _logger.error("transaction in wallet should be early detected")
                            #wi.set_status('CONFIRMED',True)
                    #else:
                    #    _logger.error("transaction not in will or utxo")
                    #    wi.set_status('INVALIDATED',True)
    
                for child in wi.search(all_inputs):
                    if child.tx.locktime < wi.tx.locktime:
                        _logger.debug("a child was found")
                        wi.set_status('REPLACED',True)
            else:
                pass

def utxos_strs(utxos):
    return [Util.utxo_to_str(u) for u in utxos]


def set_invalidate(wid,will=[]):
    will[wid].set_status("INVALIDATED",True)
    if will[wid].children:
        for c in self.children.items():
            set_invalidate(c[0],will)

def check_tx_height(tx, wallet):
    info=wallet.get_tx_info(tx)
    return info.tx_mined_status.height

#check if transactions are stil valid tecnically valid
def check_invalidated(willtree,utxos_list,wallet):
    for wid,w in willtree.items():
        if not w.father:
            for inp in w.tx.inputs():
                inp_str = Util.utxo_to_str(inp)
                #print(utxos_list)
                #print(inp_str)
                #print(inp_str in utxos_list)
                #print("notin: ",not inp_str in utxos_list)
                if not inp_str in utxos_list:
                    #print("quindi qua non ci arrivo?")
                    if wallet:
                        height= check_tx_height(w.tx,wallet)

                        if height < 0:
                            #_logger.debug(f"heigth {height}")
                            set_invalidate(wid,willtree)
                        elif height == 0:
                            w.set_status("PENDING",True)
                        else:
                            w.set_status('CONFIRMED',True)

def reflect_to_children(treeitem):
    if not treeitem.get_status("VALID"):
        _logger.debug(f"{tree:item._id} status not valid looking for children")
        for child in treeitem.children:
            wc = willtree[child]
            if wc.get_status("VALID"):
                if treeitem.get_status("INVALIDATED"):
                    wc.set_status("INVALIDATED",True)
                if treeitem.get_status("REPLACED"):
                    wc.set_status("REPLACED",True)
                    if wc.children:
                        reflect_to_children(wc)
                                
def is_will_valid(will, block_to_check, timestamp_to_check, tx_fees, all_utxos,heirs={},willexecutors={},self_willexecutor=False, wallet=False, callback_not_valid_tx=None):
    spent_utxos = []
    spent_utxos_tx = []
    add_willtree(will)
    utxos_list= utxos_strs(all_utxos)

    check_invalidated(will,utxos_list,wallet)
    #from pprint import pprint
    #for wid,w in will.items():
    #    pprint(w.to_dict())

    all_inputs=get_all_inputs(will,only_valid = True)

    all_inputs_min_locktime = get_all_inputs_min_locktime(all_inputs)

    check_will_expired(all_inputs_min_locktime,block_to_check,timestamp_to_check)

    all_inputs=get_all_inputs(will,only_valid = True)
     
    search_rai(all_inputs,all_utxos,will,wallet,callback_not_valid_tx= callback_not_valid_tx)

    if heirs:
        if not check_willexecutors_and_heirs(will,heirs,willexecutors,self_willexecutor,timestamp_to_check,tx_fees):
            raise NotCompleteWillException()


    _logger.info('check all utxo in wallet are spent')
    if all_inputs:
        for utxo in all_utxos:
            if utxo.value_sats() > 68 * tx_fees: 
                if not Util.in_utxo(utxo,all_inputs.keys()):
                        _logger.info("utxo is not spent",utxo.to_json())
                        _logger.debug(all_inputs.keys())
                        raise NotCompleteWillException("Some utxo in the wallet is not included")

    _logger.info('will ok')
    return True

def check_will_expired(all_inputs_min_locktime,block_to_check,timestamp_to_check):
    _logger.info("check if some transaction is expired")
    for prevout_str, wid in all_inputs_min_locktime.items():
        for w in wid: 
            if w[1].get_status('VALID'):
                locktime = int(wid[0][1].tx.locktime)
                if locktime <= NLOCKTIME_BLOCKHEIGHT_MAX:
                    if locktime < int(block_to_check):
                        raise WillExpiredException(f"Will Expired {wid[0][0]}: {locktime}<{block_to_check}")
                else:
                    if locktime < int(timestamp_to_check):
                        raise WillExpiredException(f"Will Expired {wid[0][0]}: {locktime}<{timestamp_to_check}")
 
def check_all_input_spent_are_in_wallet():
    _logger.info("check all input spent are in wallet or valid txs")
    for inp,ws in all_inputs.items():
        if not Util.in_utxo(inp,all_utxos):
            for w in ws:
                if w[1].get_status('VALID'):
                    prevout_id = w[2].prevout.txid.hex()
                    parentwill = will.get(prevout_id,False)
                    if not parentwill or not parentwill.get_status('VALID'):
                        w[1].set_status('INVALIDATED',True)


def only_valid_list(will):
    out={}
    for wid,w in will.items():
        if w.get_status('VALID'):
            out[wid]=w
    return out

def only_valid_or_replaced_list(will):
    out=[]
    for wid,w in will.items():
        wi = w
        if wi.get_status('VALID') or wi.get_status('REPLACED'):
            out.append(wid)
    return out

def check_willexecutors_and_heirs(will,heirs,willexecutors,self_willexecutor,check_date,tx_fees):
    _logger.debug("check willexecutors heirs")
    no_willexecutor = 0
    willexecutors_found = {}
    heirs_found = {}
    will_only_valid = only_valid_list(will)
    if len(will_only_valid)<1:
        return False
    for wid in only_valid_list(will):
        w = will[wid]
        if w.tx_fees != tx_fees:
            raise TxFeesChangedException(f"{tx_fees}:",w.tx_fees)
        for wheir in w.heirs:
            if not 'w!ll3x3c"' == wheir[:9]:
                their = will[wid].heirs[wheir]
                if heir := heirs.get(wheir,None):
            
                    if heir[0] == their[0] and heir[1] == their[1] and Util.parse_locktime_string(heir[2]) >= Util.parse_locktime_string(their[2]):
                        count = heirs_found.get(wheir,0)
                        heirs_found[wheir]=count + 1
                else:
                    _logger.debug("heir not present transaction is not valid:",wid,w)
                    continue
        if willexecutor := w.we:
            count = willexecutors_found.get(willexecutor['url'],0)
            if Util.cmp_willexecutor(willexecutor,willexecutors.get(willexecutor['url'],None)):
                willexecutors_found[willexecutor['url']]=count+1

        else:
            no_willexecutor += 1
    count_heirs = 0
    for h in heirs:
        if Util.parse_locktime_string(heirs[h][2])>=check_date:
            count_heirs +=1
            if not h in heirs_found:
                _logger.debug(f"heir: {h} not found")
                raise HeirNotFoundException(h)
    if not count_heirs:
        raise NoHeirsException("there are not valid heirs")
    if self_willexecutor and no_willexecutor ==0:
        raise NoWillExecutorNotPresent("Backup tx")

    for url,we in willexecutors.items():
        if Willexecutors.is_selected(we):
            if not url in willexecutors_found:
                _logger.debug(f"will-executor: {url} not fount")
                raise WillExecutorNotPresent(url)
    _logger.info("will is coherent with heirs and will-executors")
    return True


class WillItem(Logger): 

    STATUS_DEFAULT = {
        'ANTICIPATED':  ['Anticipated', False],
        'BROADCASTED':  ['Broadcasted', False],
        'CHECKED':      ['Checked',     False],
        'CHECK_FAIL':   ['Check Failed',False],
        'COMPLETE':     ['Signed',      False],
        'CONFIRMED':    ['Confirmed',   False],
        'ERROR':        ['Error',       False],
        'EXPIRED':      ['Expired',     False],
        'EXPORTED':     ['Exported',    False],
        'IMPORTED':     ['Imported',    False],
        'INVALIDATED':  ['Invalidated', False],
        'PENDING':      ['Pending',     False],
        'PUSH_FAIL':    ['Push failed', False],
        'PUSHED':       ['Pushed',      False],
        'REPLACED':     ['Replaced',    False],
        'RESTORED':     ['Restored',    False],
        'VALID':        ['Valid',       True],
    }
    def set_status(self,status,value=True):
        _logger.debug("set status {} - {} {} -> {}".format(self._id,status,self.STATUS[status][1],value))
        if self.STATUS[status][1] == bool(value):
            return None

        self.status += "." +("NOT " if not value else "" +  _(self.STATUS[status][0]))
        self.STATUS[status][1] = bool(value)
        if value:
            if status in ['INVALIDATED','REPLACED','CONFIRMED','PENDING']:
                self.STATUS['VALID'][1] = False

            if status in ['CONFIRMED','PENDING']:
                self.STATUS['INVALIDATED'][1] = False

            if status in ['PUSHED']:
                self.STATUS['PUSH_FAIL'][1] = False

            #if status in ['CHECK_FAIL']:
            #    self.STATUS['PUSHED'][1] = False

            if status in ['CHECKED']:
                self.STATUS['PUSHED'][1] = True
                self.STATUS['PUSH_FAIL'][1] = False

        return value

    def get_status(self,status):
        return self.STATUS[status][1]

    def __init__(self,w,_id=None,wallet=None): 
        if isinstance(w,WillItem,):
            self.__dict__ = w.__dict__.copy()
        else:
            self.tx = get_tx_from_any(w['tx'])
            self.heirs = w.get('heirs',None) 
            self.we = w.get('willexecutor',None) 
            self.status = w.get('status',None) 
            self.description = w.get('description',None) 
            self.time = w.get('time',None) 
            self.change = w.get('change',None) 
            self.tx_fees = w.get('tx_fees',0)
            self.father = w.get('Father',None)
            self.children = w.get('Children',None)
            self.STATUS = copy.deepcopy(WillItem.STATUS_DEFAULT)
            for s in self.STATUS:
                self.STATUS[s][1]=w.get(s,WillItem.STATUS_DEFAULT[s][1])
            if not _id:
                self._id = self.tx.txid()
            else:
                self._id = _id

            if not self._id:
                self.status+="ERROR!!!"
                self.valid = False

        if wallet:
            self.tx.add_info_from_wallet(wallet)



    def to_dict(self):
        out = {
            '_id':self._id,
            'tx':self.tx,
            'heirs':self.heirs,
            'willexecutor':self.we,
            'status':self.status,
            'description':self.description,
            'time':self.time,
            'change':self.change,
            'tx_fees':self.tx_fees
        }
        for key in self.STATUS:
            try:
                out[key]=self.STATUS[key][1]
            except Exception as e:
                _logger.error(f"{key},{self.STATUS[key]} {e}")

        return out

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self.to_dict())

    def set_anticipate(self, ow:'WillItem'):
        nl = min(ow.tx.locktime,check_anticipate(ow,self))
        if int(nl) < self.tx.locktime:
            _logger.debug("actually anticipating")
            self.tx.locktime = int(nl)
            return True
        else:
            _logger.debug("keeping the same locktime")
            return False


    def search_anticipate(self,all_inputs):
        anticipated = False
        for ow in self.search(all_inputs):
            if self.set_anticipate(ow):
                anticipated = True
        return anticipated

    def search(self,all_inputs):
        for inp in self.tx.inputs():
            prevout_str = inp.prevout.to_str()
            oinps = all_inputs.get(prevout_str,[])
            for oinp in oinps:
                ow=oinp[1]
                yield ow

    def normalize_locktime(self,all_inputs):
        outputs = self.tx.outputs()
        for idx in range(0,len(outputs)):
            inps = all_inputs.get(f"{self._id}:{idx}",[])
            _logger.debug("****check locktime***")
            for inp in inps:
                if inp[0]!= self._id:
                    iw = inp[1]
                    self.set_anticipate(iw)

    def check_willexecutor(self):
        try:
            if resp:=Willexecutors.check_transaction(self._id,self.we['url']):
                if resp['tx']==str(self.tx):
                    self.set_status('CHECKED')
                else:   
                    self.set_status('CHECK_FAIL')
                    self.set_status('PUSHED',False)
                return True
            else:
                self.set_status('CHECK_FAIL')
                self.set_status('PUSHED',False)
                return False
        except Exception as e:
            _logger.error("exception checking transaction",e)
            self.set_status('CHECK_FAIL')
    def get_color(self):
        if self.get_status("INVALIDATED"):
            return "#f87838"
        elif self.get_status("REPLACED"):
            return "#ff97e9"
        elif self.get_status("CONFIRMED"):
            return "#bfbfbf"
        elif self.get_status("PENDING"):
            return "#ffce30"
        elif self.get_status("CHECK_FAIL") and not self.get_status("CHECKED"):
            return "#e83845"
        elif self.get_status("CHECKED"):
            return "#8afa6c"
        elif self.get_status("PUSH_FAIL"):
            return "#e83845"
        elif self.get_status("PUSHED"):
            return "#73f3c8"
        elif self.get_status("COMPLETE"):
            return "#2bc8ed"
        else:
            return "#ffffff"


class WillExpiredException(Exception):
    pass
class NotCompleteWillException(Exception):
    pass
class HeirChangeException(NotCompleteWillException):
    pass
class TxFeesChangedException(NotCompleteWillException):
    pass
class HeirNotFoundException(NotCompleteWillException):
    pass
class WillexecutorChangeException(NotCompleteWillException):
    pass
class NoWillExecutorNotPresent(NotCompleteWillException):
    pass
class WillExecutorNotPresent(NotCompleteWillException):
    pass
class NoHeirsException(Exception):
    pass
