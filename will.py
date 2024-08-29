from .util import Util
from .bal import BalPlugin
from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any,PartialTransaction,PartialTxOutput
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
            #print("warr0:",warr[0])
            #print("war1:",warr[1])
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
                    if inputs[i].prevout.txid.hex() == otxid and inputs[i].prevout.out_idx == idx:
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
            min_locktime = min(values,key = lambda x:x[1]['tx'].locktime)[1]['tx'].locktime
            for w in values:
                if w[1]['tx'].locktime == min_locktime:
                    if not i in all_inputs_min_locktime:
                        all_inputs_min_locktime[i]=[w]
                    else:
                         all_inputs_min_locktime[i].append(w)

        return all_inputs_min_locktime

    def cmp_will(ow,nw):
        print("old heirs:",ow['heirs'])
        print("new heirs:",nw['heirs'])
        if Util.cmp_heirs(ow['heirs'],nw['heirs']):
            print("same heirs")
            if Util.cmp_willexecutor(ow['willexecutor'],nw['willexecutor']):
                print("same willexecutor")
                return True
        return False


    def update_will(old_will,new_will):
        #write_json_file("/home/steal/Documents/old_will",old_will)
        #write_json_file("/home/steal/Documents/new_will",new_will)
        all_old_inputs = Will.get_all_inputs(old_will)
        all_inputs_min_locktime = Will.get_all_inputs_min_locktime(all_old_inputs)
        all_new_inputs = Will.get_all_inputs(new_will)
        print("_______________UPDATE WILL______________") 
        for nid in new_will:
            print("nid",nid)
            if nid in old_will:
                print("already present")
                new_will[nid]=old_will[nid]
                continue
            nw=new_will[nid]
            print("heirs",nw['heirs'])
            print("locktime",nw['tx'].locktime)
            ntx=nw['tx']
            for inp in ntx.inputs():
                prevout_str = inp.prevout.to_str()
                if prevout_str in all_inputs_min_locktime:
                    ows = all_inputs_min_locktime[prevout_str]
                    for ow in ows:
                        otx = ow[1]['tx']
                        anticipate = Util.anticipate_locktime(otx.locktime,days=1)
                        found = False
                        print(nw['tx'].locktime,otx.locktime)
                        if ntx.locktime >= anticipate:
                            nw['tx'].locktime = otx.locktime
                            print("ntx locktime >=anticipate")
                            if Util.cmp_heirs(ow[1]['heirs'],nw['heirs']):
                                if Util.cmp_willexecutor(ow[1]['willexecutor'],nw['willexecutor']):
                                    print("equals!!!")
                                    if Util.cmp_txs(otx,ntx):
                                        print("keeping old tx") 
                                        new_will[nid]=ow[1]
                                        found = True
                        else:
                            print("actually anticipate")
                            new_will[nid]['tx'].locktime = int(anticipate)
        try:
            Will.normalize_will(new_will)
        except:
            pass
                            

        for oid in Will.only_valid(old_will):
            if oid in new_will:
                new_will[oid]=old_will[oid]
                continue
            else:
                ow = old_will[oid]
                otx = ow['tx']
                new_will_found = False
                for nid in new_will:
                    nw = new_will[nid]
                    ntx = nw['tx']
                    if Will.cmp_will(ow,nw):
                        if Util.cmp_txs(otx,ntx):
                            new_will_found = True

                if not new_will_found:
                    old_will[oid]['status'] += BalPlugin.STATUS_REPLACED
                    old_will[oid]['replaced'] = True
                    for i in otx.inputs():
                        prevout_str = i.prevout.to_str()
                        if prevout_str not in all_new_inputs:
                            old_will[oid]['invalidated']=True
                            old_will[oid]['status'] += BalPlugin.STATUS_INVALIDATED

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
        inputs = Will.get_higher_input_for_tx(will)
        filtered_inputs = []
        balance = 0
        utxos = wallet.get_utxos()
        for utxo in utxos:
            utxo_str=utxo.prevout.to_str()
            if utxo_str in inputs:
                filtered_inputs.append(inputs[utxo_str])
                balance += inputs[utxo_str]._TxInput__value_sats 
        
        change_addresses = wallet.get_change_addresses_for_new_transaction()
        out = PartialTxOutput.from_address_and_value(change_addresses[0], balance)
        out.is_change = True
        locktime = Util.get_current_height(wallet.network)
        tx = PartialTransaction.from_io(utxos, [out], locktime=locktime, version=2)
        fee=tx.estimated_size()*fees_per_byte
        out = PartialTxOutput.from_address_and_value(change_addresses[0],balance - fee)
        tx = PartialTransaction.from_io(utxos,[out], locktime=locktime, version=2)
        tx.set_rbf(True)
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
