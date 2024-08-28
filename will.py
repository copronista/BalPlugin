from .util import Util
from .bal import BalPlugin
from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any,PartialTransaction
from electrum.util import bfh
from electrum.util import write_json_file,read_json_file,FileImportFailed

class Will:
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
            will[willid]['children'] = Will.get_children(will,willid)
            for child in will[willid]['children']:
                if not 'father' in will[child[0]]: will[child[0]]['fathers'] = [willid]
                else: will[child[0]]['fathers'].append(willid)


    #this method return a list of will sorted by locktime
    def get_sorted_will(will):
        return sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
                    
    
    def only_valid(will):
        for k,v in will.items():
            if not BalPlugin.STATUS_REPLACED in v['status']:
                if not BalPlugin.STATUS_INVALIDATED in v['status']:
                    if not BalPlugin.STATUS_ANTICIPATED in v['status']:
                        yield k

    def search_equal_tx(will,tx,wid):
        for w in will:
            if  w != wid and not tx.to_json() != will[w]['tx'].to_json():
                if will[w]['tx'].txid() != tx.txid():
                    if Util.cmp_txs(will[w]['tx'],tx):
                        return will[w]['tx']
        return False

    def get_will(x):
        try:
            x['tx']=tx_from_any(x['tx'])
        except Exception as e:
            Util.print_var(x)
            raise e

        return x

    def normalize_will(will,wallet = None):
        to_delete = []
        to_add = []
        for wid in will:
            if isinstance(will[wid]['tx'],str):
                will[wid]['tx']=Will.get_will(will[wid])
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
 

            txid = will[wid]['tx'].txid()
            if txid is None:
                print("##########")
                print(wid)
                print(will[wid])
                print(will[wid]['tx'].to_json())
                print("txid is none")
                will[wid]['status']+="ERROR!"
                continue
                #raise Exception("txid is none")
            if txid != wid:
                to_delete.append(wid)
                to_add.append([txid,will[wid]])
                outputs = will[wid]['tx'].outputs()
                for i in range(0,len(outputs)):
                    Will.change_input(will,wid,txid,i,outputs[i])
        for warr in to_add:
            print("warr0:",warr[0])
            print("war1:",warr[1])
            will[warr[0]] = warr[1]
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


    def change_input(will, otxid, ntxid, idx, change):
        if otxid != ntxid:
            for wid in will:
                wtx=will[wid]['tx']
                inputs = wtx.inputs()
                found = False
                old_txid = wtx.txid()
                for i in range(0,len(inputs)):
                    if inputs[i].prevout.txid.hex() == otxid:
                        will[wid]['tx']._inputs[i]=Will.new_input(ntxid,idx,change)
                        found = True
                if found:
                    will[wid]['tx'].set_rbf(True)
                    will[wid]['tx'].remove_signatures()

                new_txid = will[wid]['tx'].txid()
                if old_txid != new_txid:
                    outputs = will[wid]['tx'].outputs()
                    for i in range(0,len(outputs)):
                        Will.change_input(will,old_txid,new_txid, i, outputs[i])





    #this method will substitute childrent transaction input with real father transaction id
    def normalize_will_old(will,wallet=None):
        print("normalize will")
        to_be_deleted = []
        to_be_addedd = []
        for willid in will:
            if isinstance(will[willid]['tx'],str):
                will[willid]['tx']=Will.get_will(will[willid])
            if wallet:
                print("type",type(will[willid]['tx']),)
                will[willid]['tx'].add_info_from_wallet(wallet)
            parent_txid = will[willid]['tx'].txid()
             
            print("willid:",willid)
            print("parent_txid:",parent_txid)
           
            print()
            print(will[willid])
            print()
            print(will[willid]['tx'].to_json())
            print()
            if parent_txid and willid != parent_txid:
                outputs = will[willid]['tx'].outputs()
                children = Will.get_children(will, willid)
                for child in children:
                    print("CHILD:",child)
                    print("OUTPUTS:",outputs)
                    for out in outputs:
                        print(out.to_json())
                    try:
                        change=outputs[child[2]]
                    except:
                        print("ERROR NO CHANGE OUTPUTS")
                        will[child[0]]['status']+="ERROR"
                        continue
                        
                    tx = will[child[0]]['tx']
                    inputs = tx.inputs()
                    print("previous_input:",inputs[child[1]].to_json())
                    try:
                        prevout = TxOutpoint(txid=bfh(parent_txid), out_idx=child[2])
                    except Exception as e:
                        print("prevout is none:",e)
                        continue
                    inp = PartialTxInput(prevout=prevout)
                    inp._trusted_value_sats = change.value
                    #inp.script_descriptor = change.script_descriptor
                    inp.is_mine=True
                    inp._TxInput__address=change.address
                    inp._TxInput__scriptpubkey = change.scriptpubkey
                    inp._TxInput__value_sats = change.value
                    tx._inputs[child[1]]=inp
                    tx.remove_signatures()
                    equal_tx=Will.search_equal_tx(will,tx,willid)
                    restored = ""
                    if equal_tx and equal_tx.locktime >= tx.locktime:
                        print("normalize equals",child[0],equal_tx.txid())
                        to_be_deleted.append(child[0])
                        print("to_be_deleted",will[child[0]])
                        tx = equal_tx
                        restored = "restored"
                    will[child[0]]['tx'] = tx
                    will[child[0]]['status'] += restored
                to_be_addedd.append([will[willid],parent_txid])
                to_be_deleted.append(willid)

        for w in to_be_addedd:
            will[w[1]]=w[0]
        for w in to_be_deleted:
            try:
                txid=will[w]['tx'].txid()
                print(f"will {w} will be substituted with {txid}")
                will[txid]=will[child[0]]
                del will[w]
            except: pass

            
    def get_all_inputs(will):
        all_inputs = {}
        for w in will:
            inputs = will[w]['tx'].inputs()
            for i in inputs:
                prevout_str = i.prevout.to_str()
                inp=[w,will[w]]
                if not prevout_str in all_inputs:
                    all_inputs[prevout_str] = [inp]
                else:
                    all_inputs[prevout_str].append(inp)
        return all_inputs

    def get_all_inputs_min_locktime(all_inputs):
        all_inputs_min_locktime = {}
        
        for i,values in all_inputs.items():
            all_inputs_min_locktime[i]=min(values,key = lambda x:x[1]['tx'].locktime)

        return all_inputs_min_locktime

    def cmp_will(ow,nw):
        if Util.cmp_heirs(ow['heirs'],nw['heirs']):
            if Util.cmp_willexecutor(ow['willexecutor'],nw['willexecutor']):
                if Util.cmp_inputs(ow['tx'].inputs(),nw['tx'].inputs()):
                    return True
        return False


    def update_will(old_will,new_will):
        #write_json_file("/home/steal/Documents/old_will",old_will)
        #write_json_file("/home/steal/Documents/new_will",new_will)
        all_inputs_min_locktime = Will.get_all_inputs_min_locktime(Will.get_all_inputs(old_will))
        all_new_inputs = Will.get_all_inputs(new_will)
        
        for nid in new_will:
            if nid in old_will:
                new_will[nid]=old_will[nid]
                continue
            nw=new_will[nid]
            ntx=nw['tx']
            for inp in ntx.inputs():
                prevout_str = inp.prevout.to_str()
                if prevout_str in all_inputs_min_locktime:
                    ow = all_inputs_min_locktime[prevout_str][1]
                    otx = ow['tx']
                    anticipate = Util.anticipate_locktime(otx.locktime,days=1)
                    if ntx.locktime >= anticipate:
                        if Will.cmp_will(ow,nw):
                            new_will[nid]=ow
                        else:
                            new_will[nid]['tx'].locktime = int(anticipate)
        try:
            Will.normalize_will(new_will)
        except:
            pass
                            

        for oid in Will.only_valid(old_will):
            if not oid in new_will:
                ow = old_will[oid]
                otx = ow['tx']
                new_will_found = False
                for nid in new_will:
                    nw = new_will[nid]
                    ntx = nw['tx']
                    if Will.cmp_will(ow,nw):
                        new_will_found = True

                if not new_will_found:
                    old_will[oid]['status'] += BalPlugin.STATUS_REPLACED
                    old_will[oid]['replaced'] = True
                    for i in otx.inputs():
                        prevout_str = i.prevout.to_str()
                        if prevout_str not in all_new_inputs:
                            old_will[oid]['invalidated']=True
                            old_will[oid]['status'] += BalPlugin.STATUS_INVALIDATED

    #situations:
    #change will settings by user, id heir
    #if same id take the old
    def update_will_old(old_will,new_will):
        ow_todelete=[]
        nw_todelete=[]
        for oid in Will.only_valid(old_will):
            print("-----------oid",oid)
            if oid in new_will:
                print("equals, continue")
                new_will[oid]=old_will[oid]
                continue

            ow = old_will[oid]
            print("oldheirs",ow['heirs'])
            print("oldstatus",ow['status'])
            o_inputs = ow['tx'].inputs()
            willitemfound = False
            for nid in new_will:
                print(">>>nid",nid)
                nw = new_will[nid]
                print("newheirs",nw['heirs'])
                n_inputs = nw['tx'].inputs()
                if nw['tx'].locktime >= ow['tx'].locktime:
                    if Util.cmp_txs(nw['tx'],ow['tx']):
                        new_will[nid]=ow
                        print("replaced with the old")
                    else:
                        for n_i in n_inputs:
                            if Util.in_utxo(n_i,o_inputs):
                                anticipate = Util.anticipate_locktime(ow['tx'].locktime,days=1)
                                if anticipate > Will.MIN_LOCKTIME and anticipate < nw['tx'].locktime:
                                    temp = nw['tx'].locktime 
                                    new_will[nid]['tx'].locktime = int(anticipate)
                                    new_will[nid]['tx'].remove_signatures()
                                    new_will[nid]['status']+=BalPlugin.STATUS_ANTICIPATED
                                    print("anticipated", nid,temp,new_will[nid]['tx'].locktime,new_will[nid])
                                    break

    def invalidate_will(will,wallet):
        utxos = []
        for wid in Will.only_valid(will):
            children = Will.get_children(will,wid)
            if not children:
                inputs = sort(will(wid)['tx'].inputs(), key = lambda i:i._TxInput__value_sats,reverse=True)
                utxos.append(inputs[0])
        balance = 0
            
        change_addresses = wallet.get_change_addresses_for_new_transaction()
        out = PartialTxOutput.from_address_and_value(change_addresses[0], balance)
        out.is_change = True

        tx = PartialTransaction.from_io(utxos, out, locktime=Util.get_current_height(wallet.network), version=2)
        Util.print_var(tx)
        return tx




    def is_will_valid(will, block_to_check, timestamp_to_check, all_utxos,callback_not_valid_tx=None):
        spent_utxos = []
        spent_utxos_tx = []
        locktimes_time,locktimes_blocks = Util.get_lowest_locktimes_from_will(will)
        for txid in Will.only_valid(will):
            willitem=will[txid]
            for in_ in willitem['tx'].inputs():
                spent_utxos_tx.append((txid,in_))
            spent_utxos +=willitem['tx'].inputs()
            chk_block=True
            chk_time=True
            if len(locktimes_blocks)>0:
                chk_block =  Util.chk_locktime(block_to_check,timestamp_to_check,locktimes_blocks[0])

            if len(locktimes_time)>0:
                chk_time =  Util.chk_locktime(block_to_check,timestamp_to_check,locktimes_time[0])

            if not (chk_block or chk_time):
                print("locktime",locktimes_time[0],timestamp_to_check,Util.chk_locktime(timestamp_to_check,block_to_check,locktimes_time[0]))
                print("blocktime",locktimes_blocks[0],block_to_check,Util.chk_locktime(timestamp_to_check,block_to_check,locktimes_blocks[0]))
                print("locktime outdated",locktimes_time,locktimes_blocks,block_to_check,timestamp_to_check)
                print("will need to be invalidated")
                raise WillExpiredException("expired")

        #check that all utxo in wallet ar e spent
        print('check all utxo in wallet are spent')
        for utxo in all_utxos:
            if not Util.in_utxo(utxo,spent_utxos):
                    print("utxo is not spent",utxo.to_json())
                    raise NotCompleteWillException("not complete")
        #check that all spent uxtos are in wallet
        print('check all spent utxos are in wallet')
        for txid,s_utxo in spent_utxos_tx: 
            if not Util.in_utxo(s_utxo,all_utxos):
                print("not all utxos")
                prevout=s_utxo.prevout.to_json()

                if not prevout[0] in will.keys():
                    print("utxo is not in wallet",s_utxo.to_json(),s_utxo.prevout.to_json(),will.keys(),prevout[0])
                    if callback_not_valid_tx:
                        print(f"trying to invalidate {txid}")
                        callback_not_valid_tx(txid,s_utxo)
                    #return False
        print('tutto ok')
        return True



class WillExpiredException(Exception):
    pass
class NotCompleteWillException(Exception):
    pass
