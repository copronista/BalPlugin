from . import willexecutors as Willexecutors
from . import util as Util
from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any,PartialTransaction,PartialTxOutput,Transaction
from electrum.util import bfh, decimal_point_to_base_unit_name
from electrum.util import write_json_file,read_json_file,FileImportFailed
import copy

MIN_LOCKTIME = 1
MIN_BLOCK = 1
#return an array with the list of children
def get_children(will,willid):
    out = []
    for _id in will:
        inputs = will[_id]['tx'].inputs()
        for idi in range(0,len(inputs)):
            _input = inputs[idi]
            #print(_input.prevout.txid.hex())
            if _input.prevout.txid.hex() == willid:
                out.append([_id,idi,_input.prevout.out_idx])
    return out
#this method should build a tree with parent transactions
def add_willtree(will):
    for willid in will:
        will[willid]['children'] = get_children(will,willid)
        for child in will[willid]['children']:
            if not 'father' in will[child[0]]: will[child[0]]['father'] = willid


#this method return a list of will sorted by locktime
def get_sorted_will(will):
    return sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
                

def only_valid(will):
    for k,v in will.items():
        if v[STATUS_VALID]:
            yield k
        #if not STATUS_REPLACED in v['status']:
        #    if not STATUS_INVALIDATED in v['status']:
        #        if not STATUS_ANTICIPATED in v['status']:
        #            yield k

def search_equal_tx(will,tx,wid):
    for w in will:
        if  w != wid and not tx.to_json() != will[w]['tx'].to_json():
            if will[w]['tx'].txid() != tx.txid():
                if Util.cmp_txs(will[w]['tx'],tx):
                    return will[w]['tx']
    return False

def get_tx_from_any(x):
    try:
        print(x['tx'])
        a=str(x['tx'])
        return tx_from_any(str(x['tx']))
        
    except Exception as e:
        Util.print_var(x)
        raise e

    return x['tx']

def add_info_from_will(will,wid,wallet):
    if isinstance(will[wid]['tx'],str):
        will[wid]['tx'] = get_tx_from_any(will[wid])
    if wallet:
        will[wid]['tx'].add_info_from_wallet(wallet)
    for txin in will[wid]['tx'].inputs():
        txid = txin.prevout.txid.hex()
        if txid in will:
            change = will[txid]['tx'].outputs()[txin.prevout.out_idx]
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
            print(txin.to_json())

            

def normalize_will(will,wallet = None,others_inputs = {}):
    to_delete = []
    to_add = {}
    #add info from wallet
    for wid in will:
        add_info_from_will(will,wid,wallet)
    errors ={}
    for wid in will:

        txid = will[wid]['tx'].txid()
        if txid is None:
            print("##########")
            print(wid)
            print(will[wid])
            print(will[wid]['tx'].to_json())
            print("txid is none")
            will[wid]['status']+="ERROR!"
            errors[wid]=will[wid]
            continue
            #raise Exception("txid is none should not")
        if txid != wid:
            print(f"{txid} is different than {wid}")
            outputs = will[wid]['tx'].outputs()
            ow=WillItem(will[wid])
            ow.normalize_locktime(others_inputs)
            #ow.search_anticipate(will)
            will[wid]=ow.to_dict()
            for i in range(0,len(outputs)):
                change_input(will,wid,i,outputs[i],others_inputs,to_delete,to_add)

            to_delete.append(wid)
            to_add[ow.tx.txid()]=ow.to_dict()
    for eid,err in errors.items():
        new_txid = err['tx'].txid()
        print("ERROR:",eid,new_txid)

    for k,w in to_add.items():
        print(f"to be addedd in normalize:{k}")
        will[k] = w
        #reset_status(will[warr[0]])
    for wid in to_delete:
        if wid in will:
            print(f"delete will {wid}")
            WillItem(will[wid]).print()
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
    print(nw.tx.locktime,ow.tx.locktime,anticipate)
    if int(nw.tx.locktime) >= int(anticipate):
        print("ntx locktime >anticipate")
        #nw.tx.locktime = min(ow.tx.locktime,nw.tx.locktime)
        if Util.cmp_heirs_by_values(ow.heirs,nw.heirs,[0,1],exclude_willexecutors = True):
            print("same heirs")
            if nw.we and ow.we:
                if ow.we['url'] == nw.we['url']:
                    print("same url")
                    if int(ow.we['base_fee'])>int(nw.we['base_fee']):
                        print("fee are lowered")
                        return anticipate
                    else:
                        print("old fees are not lower than new fees so replace with the same locktime",ow.we['base_fee'],nw.we['base_fee'],int(ow.we['base_fee'])>int(nw.we['base_fee']))
                        ow.tx.locktime
                else:
                    print("those fucking shit have different urls")
                    ow.tx.locktime
            else:
                print("some fucking willexecutor is none",nw.we,ow.we)
                if nw.we == ow.we:
                    if not Util.cmp_heirs_by_values(ow.heirs,nw.heirs,[0,3]):
                        print("heirs have a different calculated amount so I have to anticipate")
                        return anticipate
                    else:
                        print("fuck you")
                        print(ow.heirs,nw.heirs)
                        print(ow.we,nw.we)
                        return ow.tx.locktime
                else:
                    print("only the last willexecutor is none")
                    return ow.tx.locktime
        else:
            print("heirs are different:", anticipate)
            return anticipate
    return  4294967295+1

     
def change_input(will, otxid, idx, change,others_inputs,to_delete,to_append):
    ow = WillItem(will[otxid],otxid)
    ntxid = ow.tx.txid()
    if otxid != ntxid:
        for wid in will:
            w = WillItem(will[wid])
            inputs = w.tx.inputs()
            outputs = w.tx.outputs()
            found = False
            old_txid = w.tx.txid()
            ntx = None
            for i in range(0,len(inputs)):
                if inputs[i].prevout.txid.hex() == otxid and inputs[i].prevout.out_idx == idx:
                    print(f"{otxid}:{idx} output to be changed found: {old_txid}, {ntxid}")
                    if isinstance(w.tx,Transaction):
                        print("NEW TRANSACTION")
                        will[wid]['tx']=PartialTransaction.from_tx(w.tx)
                        will[wid]['tx'].set_rbf(True)
                    will[wid]['tx']._inputs[i]=new_input(wid,idx,change)
                    found = True
            if found == True:
                pass
                #ntx = PartialTransaction.from_io(inputs,outputs,locktime=wtx.locktime,version=2)
                #ntx.set_rbf(True)
                #ntx.remove_signatures()
                #will[wid]['tx'] = ntx
                #reset_status(will,wid)
            
            new_txid = will[wid]['tx'].txid()
            if old_txid != new_txid:
                to_delete.append(old_txid)
                to_append[new_txid]=will[wid]
                outputs = will[wid]['tx'].outputs()
                for i in range(0,len(outputs)):
                    print("chANGE INPUT:",wid, "-", old_txid)
                    #change_input(will,old_txid, i, outputs[i],others_inputs)
                    change_input(will, wid, i, outputs[i],others_inputs,to_delete,to_append)
                    




        
def get_all_inputs(will,only_valid = False):
    all_inputs = {}
    for w in will:
        wi = WillItem(will[w])
        if wi.valid:
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
        min_locktime = min(values,key = lambda x:x[1]['tx'].locktime)[1]['tx'].locktime
        for w in values:
            if w[1]['tx'].locktime == min_locktime:
                if not i in all_inputs_min_locktime:
                    all_inputs_min_locktime[i]=[w]
                else:
                     all_inputs_min_locktime[i].append(w)

    return all_inputs_min_locktime

def set_status(w,new_status):
    if new_status == STATUS_VALID:
        w['status']+=_(STATUS_VALID)
        w[STATUS_VALID] = True
    elif new_status == STATUS_REPLACED:
        w['status'] +=STATUS_REPLACED
        w[STATUS_REPLACED]=True
        w[STATUS_REPLACED]=False
    elif new_status == STATUS_INVALIDATED:
        w['status']+=STATUS_INVALIDATED
        w[STATUS_VALID]=True



def replace_heir(ow,nw):
    ow['heirs'] = nw['heirs']
    ow['status'] +=STATUS_RESTORED
    #ow[STATUS_VALID] = True
    ow[STATUS_REPLACED] = False
    ow[STATUS_INVALIDATED] = False
    return ow

def same_input_same_locktime(will,all_inputs_min_locktime=None):
    if not all_inputs_min_locktime:
        all_inputs_min_locktime = get_all_inputs(will)
    for wid,w in will.items():
        #print(wid,w['heirs'])
        for i in w['tx'].inputs():
            prevout_str = i.prevout.to_str()
            #print("prevout_str:",prevout_str)
            if nws := all_input_min_locktime.get(prevout_str,False):
                nws_locktime = min(nws,key=lambda x:x[1]['tx'].locktime)[1]['tx'].locktime
                #print(f"nws_locktime = {nws_locktime},{w['tx'].locktime}",nws)
                if w['tx'].locktime > nws_locktime:
                    #print(f"{nws_locktime} < {w['tx'].locktime}")
                    new_will[wid]['status']+=STATUS_ANTICIPATED
                    new_will[wid]['tx'].locktime = nws_locktime

def search_anticipate_rec(will,old_inputs):
    print("SEARC_ANTICIPATE_REC")
    redo = False
    to_delete = []
    to_append = {}
    new_inputs = get_all_inputs(will)
    for nid,nw in will.items():
        print("***************************NEW************")
        print(F"NID:{nid}")
        nwi = WillItem(nw)
        nwi.print()
        if nwi.search_anticipate(new_inputs) or nwi.search_anticipate(old_inputs):
            if nid != nwi.tx.txid():
                print(f"{nid} e' differente da:{nwi.tx.txid()}")
                redo = True
                to_delete.append(nid)
                to_append[nwi.tx.txid()] = nwi.to_dict()
                outputs = nwi.tx.outputs()
                for i in range(0,len(outputs)):
                    change_input(will,nid,i,outputs[i],new_inputs,to_delete,to_append)
                    

    for w in to_delete:
        print(f"I'm going to delete this transaction {w}")
        try:
            del will[w]
        except:
            print("already gone")
    for k,w in to_append.items():
        print(f"I'm going to append this transaction{k}")
        will[k]=w
    if redo:
        print("REDOOOOO")
        search_anticipate_rec(will,old_inputs)


def update_will(old_will,new_will):
    #write_json_file("/home/steal/Documents/old_will",old_will)
    #write_json_file("/home/steal/Documents/new_will",new_will)
    all_old_inputs = get_all_inputs(old_will)
    all_inputs_min_locktime = get_all_inputs_min_locktime(all_old_inputs)
    all_new_inputs = get_all_inputs(new_will)
    print("\n\n\n\n")
    print("_______________UPDATE WILL______________") 
    #check if the new input is already spent by other transaction
    #if it is use the same locktime, or anticipate.
    search_anticipate_rec(new_will,all_old_inputs)

    print()
   # print("looking if a transaction with the same input has a lower locktime")
   # all_new_inputs=get_all_inputs(new_will)
   # for wid,w in new_will.items():
   #     w = tem(w)
   #     w.search_anticipate(all_new_inputs)
   #     new_will[wid]=w.to_dict()

    other_inputs = get_all_inputs(old_will,{})
    try:
        normalize_will(new_will,others_inputs=other_inputs)
    except Exception as e:
        raise e
                        

    for oid in only_valid(old_will):
        print("update old will:",oid)
        if oid in new_will:
            new_heirs = new_will[oid]['heirs']
            new_we = new_will[oid]['willexecutor']

            new_will[oid]=old_will[oid]
            new_will[oid]['heirs']=new_heirs
            new_will[oid]['willexecutor']= new_we

            #new_will[oid]=replace_heir(old_will[oid],new_will[oid])
            continue
        else:
            continue
            #print("set status replaced")
            #old_will[oid]['status']+=STATUS_REPLACED
            #old_will[oid][STATUS_REPLACED]=True
            #old_will[oid][STATUS_VALID]=False
        """
        else:
            ow = old_will[oid]
            otx = ow['tx']
            new_will_found = False
            for nid in new_will:
                nw = new_will[nid]
                ntx = nw['tx']
                if cmp_will(ow,nw):
                    if Util.cmp_txs(otx,ntx):
                        new_will_found = True

            if not new_will_found:
                old_will[oid]['status'] += STATUS_REPLACED
                old_will[oid][STATUS_REPLACED] = True
                old_will[oid][STATUS_VALID] = False
                for i in otx.inputs():
                    prevout_str = i.prevout.to_str()
                    if prevout_str not in all_new_inputs:
                        old_will[oid]['status'] += STATUS_INVALIDATED
                        old_will[oid][STATUS_INVALIDATED]=True
                        old_will[oid][STATUS_VALID] = False
        """

def reset_status(w):
                #w['status'] = STATUS_NEW
                w[STATUS_NEW] = True
                w[STATUS_VALID] = True
                w[STATUS_REPLACED] = False
                w[STATUS_INVALIDATED] = False
                w[STATUS_EXPORTED] = False
                w[STATUS_BROADCASTED] = False
                w[STATUS_RESTORED] = False
                w[STATUS_COMPLETE] = False
                w[STATUS_PUSHED] = False
                w[STATUS_ANTICIPATED] = False

def get_higher_input_for_tx(will):
    out = {}
    for wid in will:
        wtx = will[wid]['tx']
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
    #inputs = sorted(inputs,key=lambda x:x[1][2].value,reverse=True)
    utxos = wallet.get_utxos()
    filtered_inputs = []
    prevout_to_spend = []
    for prevout_str,ws in inputs.items(): 
        for w in ws:
            print("wid = ",w[0])
            if not w[0] in filtered_inputs: 
                filtered_inputs.append(w[0])
                if not prevout_str in prevout_to_spend:
                    prevout_to_spend.append(prevout_str)
                break
    print("prevout to spends")
    print(prevout_to_spend)
    balance = 0
    utxo_to_spend = []
    for utxo in utxos:
        utxo_str=utxo.prevout.to_str()
        if utxo_str in prevout_to_spend:
            #Util.print_var(inputs[utxo_str],"INPUT")
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

            #Util.print_var(tx)
            return tx

        else:
            print("balance - fee:",balance - fee)
    else:
        print("no input")


def is_new(will):
    for wid in will:
        if will[wid]['status'] == STATUS_NEW:
            return True

#_transactions_replaced_anticipated_invalidated(all_inputs,all_utxos):
def search_rai (all_inputs,all_utxos,will,callback_not_valid_tx=None):
    will_only_valid = only_valid_or_replaced_list(will)
    for inp,ws in all_inputs.items():
        for w in ws:
            wi=WillItem(w[1])
            if wi.valid:
                if not Util.in_utxo(inp,all_utxos):
                    prevout_id=w[2].prevout.txid.hex()
                    if prevout_id in will:
                        wo=WillItem(will[prevout_id])
                        print("willitem will be replaced or invalidated:",wo._id,wo.replaced,wo.invalidated)
                        if wo.replaced:
                            wi.set_status_replaced()
                            will[wi._id]=wi.to_dict()
                        if wo.invalidated:
                            wi.set_status_invalidated()
                            will[wi._id]=wi.to_dict()
                        
                    else:
                        wi.set_status_invalidated()
                        will[wi._id]=wi.to_dict()
                        #print("utxo was replaced")
                        #wi.set_status_replaced()
                        #will[wi._id]=wi.to_dict()

                for child in wi.search(all_inputs):
                    if child.tx.locktime < wi.tx.locktime:
                        print(f"trying to replace {w[0]}")
                        if wi.set_status_replaced():
                            will[wi._id]=wi.to_dict()





def is_will_valid(will, block_to_check, timestamp_to_check, tx_fees, all_utxos,heirs={},willexecutors={},self_willexecutor=False, callback_not_valid_tx=None):
    spent_utxos = []
    spent_utxos_tx = []
    all_inputs=get_all_inputs(will,only_valid = True)
    all_inputs_min_locktime = get_all_inputs_min_locktime(all_inputs)
    search_rai(all_inputs,all_utxos,will,callback_not_valid_tx= callback_not_valid_tx)
    if heirs:
        if not check_willexecutors_and_heirs(will,heirs,willexecutors,self_willexecutor,timestamp_to_check,tx_fees):
            raise NotCompleteWillException("not complete")
    else:
        print("not heirs")
        return
    #check that all utxo in wallet ar e spent
    for prevout_str, wid in all_inputs_min_locktime.items():
        for w in wid: 
            if w[1][STATUS_VALID]:
                locktime = wid[0][1]['tx'].locktime
                if int(locktime) < int(timestamp_to_check):
                    raise WillExpiredException(f"Will Expired {wid[0][0]}: {locktime}<{timestamp_to_check}")
    print('check all utxo in wallet are spent')
    if all_inputs:
        for utxo in all_utxos:
            if utxo.value_sats() > 68 * tx_fees: 
                if not Util.in_utxo(utxo,all_inputs.keys()):
                        print("utxo is not spent",utxo.to_json())
                        print(all_inputs.keys())
                        raise NotCompleteWillException("Some utxo in the wallet is not included")
    """
    #check that all spent uxtos are in wallet
    print('check all spent utxos are in wallet')
    for inp,ws in all_inputs.items():
        for w in ws:
            print(w)
            if w[1][STATUS_VALID]:
                if not w[2].prevout.txid.hex() in only_valid_list(will):
                    if not Util.in_utxo(inp,all_utxos):
                        if callback_not_valid_tx:
                            print(f"trying to invalidate {w[0]}")
                            callback_not_valid_tx(w[0],w[2])
                #return False
    """
    print('tutto ok')
    return True

def only_valid_list(will):
    out={}
    for wid,w in will.items():
        if w[STATUS_VALID]:
            out[wid]=w
    return out

def only_valid_or_replaced_list(will):
    out=[]
    for wid,w in will.items():
        wi = WillItem(w)
        if wi.valid or wi.replaced:
            out.append(wid)
    return out

def check_willexecutors_and_heirs(will,heirs,willexecutors,self_willexecutor,check_date,tx_fees):
    print("check willexecutors heirs")
    no_willexecutor = 0
    willexecutors_found = {}
    heirs_found = {}
    will_only_valid = only_valid_list(will)
    if len(will_only_valid)<1:
        return False
    for wid in only_valid_list(will):
        w = will[wid]
        if w.get('tx_fees',0)!=tx_fees:
            print("TXFEESSSSSSSSS",w.get('tx_fees',0))
            wi=WillItem(will[wid])
            wi.print()
            raise TxFeesChangedException(f"{tx_fees}:",w.get('tx_fees',0))
        for wheir in w['heirs']:
            if not 'w!ll3x3c"' == wheir[:9]:
                their = will[wid]['heirs'][wheir]
                if heir := heirs.get(wheir,None):
            
                    #print(heir[0]==their[0],heir[1]==their[1], Util.parse_locktime_string(heir[2])>=Util.parse_locktime_string(their[2]))
                    if heir[0] == their[0] and heir[1] == their[1] and Util.parse_locktime_string(heir[2]) >= Util.parse_locktime_string(their[2]):
                        count = heirs_found.get(wheir,0)
                        heirs_found[wheir]=count + 1
                else:
                    print("heir not present transaction is not valid:",wid,w)
                    continue
        if willexecutor := w.get("willexecutor",None):
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
                print(f"heir: {h} not found")
                raise HeirNotFoundException(h)
    if not count_heirs:
        raise NoHeirsException("there are not valid heirs")
    if self_willexecutor and no_willexecutor > 0:
        for url,we in willexecutors.items():
            if Willexecutors.is_selected(we):
                if not url in willexecutors_found:
                    print(f"will-executor: {url} not fount")
                    raise WillExecutorNotPresent(url)
    elif self_willexecutor and no_willexecutor==0 and len(heirs_found)>0:
        print("no will-executor selected but not present")
        print(self_willexecutor,no_willexecutor)
        raise NoWillExecutorNotPresent("Backup tx")
    print("will is coherent with heirs and will-executors")
    return True

STATUS_NEW = 'New'
STATUS_COMPLETE = 'Signed'
STATUS_BROADCASTED = 'Broadcasted'
STATUS_PUSHED = 'Pushed'
STATUS_EXPORTED = 'Exported'
STATUS_REPLACED = 'Replaced'
STATUS_INVALIDATED = 'Invalidated'
STATUS_ANTICIPATED = 'Anticipated'
STATUS_RESTORED = 'Restored'
STATUS_VALID = 'Valid'

class WillItem: 
    def __init__(self,w,_id=None): 
        if isinstance(w,WillItem,):
            self = w
        else:
            self.tx = w.get('tx',None) 
            self.heirs = w.get('heirs',None) 
            self.we = w.get('willexecutor',None) 
            self.status = w.get('status',None) 
            self.description = w.get('description',None) 
            self.time = w.get('time',None) 
            self.change = w.get('change',None) 
            self.tx_fees = w.get('tx_fees',0)
            self.valid = w.get(STATUS_VALID,False) 
            self.replaced = w.get(STATUS_REPLACED,False) 
            self.invalidated = w.get(STATUS_INVALIDATED,False) 
            self.anticipated = w.get(STATUS_ANTICIPATED,False) 
            self.restored = w.get(STATUS_RESTORED,False) 
            self.new = w.get(STATUS_NEW,False) 
            self.broadcasted = w.get(STATUS_BROADCASTED,False) 
            self.exported = w.get(STATUS_EXPORTED,False) 
            self.complete = w.get(STATUS_COMPLETE,False) 
            self.pushed = w.get(STATUS_PUSHED,False) 
            if not _id:
                self._id = self.tx.txid()
            else:
                self._id = _id

            if not self._id:
                self.status+="ERROR!!!"
                self.valid = False


    def to_dict(self):
        return {
            'tx':self.tx,
            'heirs':self.heirs,
            'willexecutor':self.we,
            'status':self.status,
            'description':self.description,
            'time':self.time,
            'change':self.change,
            'tx_fees':self.tx_fees,
            STATUS_VALID: self.valid,
            STATUS_REPLACED: self.replaced,
            STATUS_INVALIDATED: self.invalidated,
            STATUS_ANTICIPATED: self.anticipated,
            STATUS_RESTORED: self.restored,
            STATUS_NEW: self.new,
            STATUS_EXPORTED: self.exported,
            STATUS_BROADCASTED: self.broadcasted,
            STATUS_COMPLETE: self.complete,
            STATUS_PUSHED: self.pushed,
        }

    def print(self):
        print("Tem:",self.tx.txid())
        print("Locktime:",Util.locktime_to_str(self.tx.locktime),self.tx.locktime)
        print("tx_fees:",self.tx_fees)
        print("Heirs:")
        print("WE:")
        print("status:",self.status)
        #print("description:",self.description)
        print("time:",self.time)
        #print("change:",self.change)
        #print("tx:",str(self.tx))

    def set_anticipate(self, ow:'WillItem'):
        nl = min(ow.tx.locktime,check_anticipate(ow,self))
        if int(nl) < self.tx.locktime:
            print("actually anticipating")
            self.tx.locktime = int(nl)
            return True
        else:
            print("keeping the same locktime")
            return False
            #self.status += STATUS_ANTICIPATED
            #self.anticipated = True


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
            #print("INPS:",len(oinps))
            for oinp in oinps:
                ow=WillItem(oinp[1])
                #ow.print()
                yield ow

    def normalize_locktime(self,all_inputs):
        outputs = self.tx.outputs()
        for idx in range(0,len(outputs)):
            inps = all_inputs.get(f"{self._id}:{idx}",[])
            print("****check locktime***")
            print(inps)
            for inp in inps:
                if inp[0]!= self._id:
                    iw = WillItem(inp[1])
                    self.set_anticipate(iw)

    def set_status_anticipated(self):
        print("actually anticipated")
        if not self.anticipated:
            self.status +="."+STATUS_ANTICIPATED
            self.anticipated = True
            return True

    def set_status_invalidated(self):
        print("actually invalidated")
        if not self.invalidated:
            self.status +="."+STATUS_INVALIDATED
            self.invalidated = True
            self.valid = False
            return True

    def set_status_replaced(self):
        print("actually_replaced")
        if not self.replaced:
            self.status += "."+STATUS_REPLACED
            self.replaced = True
            self.valid = False
            return True

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

