from .willexecutors import Willexecutors
from .util import Util
from .bal import BalPlugin
from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any,PartialTransaction,PartialTxOutput,Transaction
from electrum.util import bfh, decimal_point_to_base_unit_name
from electrum.util import write_json_file,read_json_file,FileImportFailed
import copy

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
                if not 'father' in will[child[0]]: will[child[0]]['father'] = willid


    #this method return a list of will sorted by locktime
    def get_sorted_will(will):
        return sorted(will.items(),key = lambda x: x[1]['tx'].locktime)
                    
    
    def only_valid(will):
        for k,v in will.items():
            if v[BalPlugin.STATUS_VALID]:
                yield k
            #if not BalPlugin.STATUS_REPLACED in v['status']:
            #    if not BalPlugin.STATUS_INVALIDATED in v['status']:
            #        if not BalPlugin.STATUS_ANTICIPATED in v['status']:
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
            will[wid]['tx'] = Will.get_tx_from_any(will[wid])
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

    def normalize_will(will,wallet = None):
        to_delete = []
        to_add = []
        for wid in will:
            Will.add_info_from_will(will,wid,wallet)

        all_input = Will.get_all_inputs(will)
        for wid in Will.only_valid(will):
            w=will[wid]
            for i in w['tx'].inputs():
                prevout_str = i.prevout.to_str()
                if prevout_str in all_input:
                    nws=all_input[prevout_str]
                    nws_locktime = min(nws,key=lambda x:x[1]['tx'].locktime)[1]['tx'].locktime
                    if w['tx'].locktime > nws_locktime:
                        will[wid][BalPlugin.STATUS_VALID]=False
                        will[wid][BalPlugin.STATUS_INVALIDATED]=True
                        will[wid]['status']+=BalPlugin.STATUS_INVALIDATED
                    
                        #new_will[wid]['status']+=alPlugin.STATUS_ANTICIPATED
                        #new_will[wid]['tx'].locktime = nws_locktime
        for wid in will:

            txid = will[wid]['tx'].txid()
            if txid is None:
                print("##########")
                print(wid)
                print(will[wid])
                print(will[wid]['tx'].to_json())
                print("txid is none")
                will[wid]['status']+="ERROR!"
                continue
                #raise Exception("txid is none should not")
            if txid != wid:
                to_delete.append(wid)
                to_add.append([txid,will[wid]])
                outputs = will[wid]['tx'].outputs()
                for i in range(0,len(outputs)):
                    Will.change_input(will,wid,txid,i,outputs[i])
        for warr in to_add:
            #print("warr0:",warr[0])
            #print("war1:",warr[1])
            warr[1][BalPlugin.STATUS_REPLACED]=True
            warr[1][BalPlugin.STATUS_VALID]=False
            will[warr[0]] = copy.deepcopy(warr[1])
            Will.reset_status(will[warr[0]])
        for wid in to_delete:
            if wid in will:
                print(f"delete will {wid}")
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
                outputs = wtx.outputs()
                found = False
                old_txid = wtx.txid()
                ntx = None
                for i in range(0,len(inputs)):
                    if inputs[i].prevout.txid.hex() == otxid and inputs[i].prevout.out_idx == idx:
                        if isinstance(wtx,Transaction):
                            will[wid]['tx']=PartialTransaction.from_tx(wtx)
                            will[wid]['tx'].set_rbf(True)
                        will[wid]['tx']._inputs[i]=Will.new_input(ntxid,idx,change)
                        found = True
                if found == True:
                    pass
                    #ntx = PartialTransaction.from_io(inputs,outputs,locktime=wtx.locktime,version=2)
                    #ntx.set_rbf(True)
                    #ntx.remove_signatures()
                    #will[wid]['tx'] = ntx
                    #Will.reset_status(will,wid)

                new_txid = will[wid]['tx'].txid()
                if old_txid != new_txid:
                    outputs = will[wid]['tx'].outputs()
                    for i in range(0,len(outputs)):
                        Will.change_input(will,old_txid,new_txid, i, outputs[i])





            
    def get_all_inputs(will,only_valid = False):
        all_inputs = {}
        for w in will:
            if will[w][BalPlugin.STATUS_VALID]:
                inputs = will[w]['tx'].inputs()
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

    def cmp_will(ow,nw):
        print("old heirs:",ow['heirs'])
        print("new heirs:",nw['heirs'])
        if Util.cmp_heirs(ow['heirs'],nw['heirs']):
            print("same heirs")
            if Util.cmp_willexecutor(ow['willexecutor'],nw['willexecutor']):
                print("same willexecutor")
                return True
        return False

    def replace_heir(ow,nw):
        ow['heirs'] = nw['heirs']
        ow['status'] +=BalPlugin.STATUS_RESTORED
        #ow[BalPlugin.STATUS_VALID] = True
        ow[BalPlugin.STATUS_REPLACED] = False
        ow[BalPlugin.STATUS_INVALIDATED] = False
        return ow

    def update_will(old_will,new_will):
        #write_json_file("/home/steal/Documents/old_will",old_will)
        #write_json_file("/home/steal/Documents/new_will",new_will)
        all_old_inputs = Will.get_all_inputs(old_will)
        all_inputs_min_locktime = Will.get_all_inputs_min_locktime(all_old_inputs)
        all_new_inputs = Will.get_all_inputs(new_will)
        print("_______________UPDATE WILL______________") 
        for nid in new_will:
            print("nid",nid)
            #if nid in old_will:
            #    print("already present")
            #new_will[nid]=Will.replace_heir(old_will[nid],new_will[nid])
            #    continue
            nw=new_will[nid]
            print("heirs",nw['heirs'])
            print("locktime",nw['tx'].locktime)
            ntx=nw['tx']
            for inp in ntx.inputs():
                prevout_str = inp.prevout.to_str()
                if prevout_str in all_inputs_min_locktime:
                    ows = all_inputs_min_locktime[prevout_str]
                    anticipate = ntx.locktime
                    found = False
                    for ow in ows:
                        otx = ow[1]['tx']
                        anticipate = Util.anticipate_locktime(otx.locktime,days=1)
                        print(nw['tx'].locktime,otx.locktime)
                        if ntx.locktime > anticipate:
                            nw['tx'].locktime = otx.locktime
                            print("ntx locktime >=anticipate")
                            if Util.cmp_outputs(otx.outputs(),ntx.outputs()):
                                print("keeping old tx") 
                                new_will[nid]['tx'].locktime = ow[1]['tx'].locktime
                                found = True

                            """
                            if Util.cmp_heirs(ow[1]['heirs'],nw['heirs']):
                                if Util.cmp_willexecutor(ow[1]['willexecutor'],nw['willexecutor']):
                                    print("equals!!!")
                                    if Util.cmp_txs(otx,ntx):
                                        print("keeping old tx") 
                                        new_will[nid]['tx'].locktime = ow[1]['tx'].locktime
                                        found = True
                            """
                    if not found:
                        print("actually anticipate outputs are different")
                        new_will[nid]['tx'].locktime = int(anticipate)
                        new_will[nid][BalPlugin.STATUS_ANTICIPATED]=True

        new_input_min_locktime=Will.get_all_inputs(new_will)
        for wid,w in new_will.items():
            print(wid,w['heirs'])
            for i in w['tx'].inputs():
                prevout_str = i.prevout.to_str()
                print("prevout_str:",prevout_str)
                if prevout_str in new_input_min_locktime:
                    nws=new_input_min_locktime[prevout_str]
                    nws_locktime = min(nws,key=lambda x:x[1]['tx'].locktime)[1]['tx'].locktime
                    print(f"nws_locktime = {nws_locktime},{w['tx'].locktime}",nws)
                    if w['tx'].locktime > nws_locktime:
                        print(f"{nws_locktime} < {w['tx'].locktime}")
                        new_will[wid]['status']+=BalPlugin.STATUS_ANTICIPATED
                        new_will[wid]['tx'].locktime = nws_locktime


        try:
            Will.normalize_will(new_will)
        except Exception as e:
            raise e
                            

        for oid in Will.only_valid(old_will):
            if oid in new_will:
                new_heirs = new_will[oid]['heirs']
                new_we = new_will[oid]['willexecutor']

                new_will[oid]=old_will[oid]
                new_will[oid]['heirs']=new_heirs
                new_will[oid]['willexecutor']= new_we

                #new_will[oid]=Will.replace_heir(old_will[oid],new_will[oid])
                continue
            """
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
                    old_will[oid][BalPlugin.STATUS_REPLACED] = True
                    old_will[oid][BalPlugin.STATUS_VALID] = False
                    for i in otx.inputs():
                        prevout_str = i.prevout.to_str()
                        if prevout_str not in all_new_inputs:
                            old_will[oid]['status'] += BalPlugin.STATUS_INVALIDATED
                            old_will[oid][BalPlugin.STATUS_INVALIDATED]=True
                            old_will[oid][BalPlugin.STATUS_VALID] = False
            """

    def reset_status(w):
                    #w['status'] = BalPlugin.STATUS_NEW
                    w[BalPlugin.STATUS_NEW] = True
                    w[BalPlugin.STATUS_VALID] = True
                    w[BalPlugin.STATUS_REPLACED] = False
                    w[BalPlugin.STATUS_INVALIDATED] = False
                    w[BalPlugin.STATUS_EXPORTED] = False
                    w[BalPlugin.STATUS_BROADCASTED] = False
                    w[BalPlugin.STATUS_RESTORED] = False
                    w[BalPlugin.STATUS_COMPLETE] = False
                    w[BalPlugin.STATUS_PUSHED] = False
                    w[BalPlugin.STATUS_ANTICIPATED] = False

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



    def is_new(will):
        for wid in will:
            if will[wid]['status'] == BalPlugin.STATUS_NEW:
                return True

    def is_will_valid(will, block_to_check, timestamp_to_check, all_utxos,heirs={},willexecutors={},callback_not_valid_tx=None):
        spent_utxos = []
        spent_utxos_tx = []
        all_inputs=Will.get_all_inputs(will,only_valid = True)
        all_inputs_min_locktime = Will.get_all_inputs_min_locktime(all_inputs)
        if heirs:
            if not Will.check_heirs_are_present(will,heirs,timestamp_to_check):
                raise NotCompleteWillException("Heirs are changed")
        if willexecutors:
            if not Will.check_willexecutors(will,willexecutors):
                raise NotCompleteWillException("Willexecutors are changed")
        #check that all utxo in wallet ar e spent
        for prevout_str, wid in all_inputs_min_locktime.items():
            #print("prevout_str",prevout_str)
            #print("wid:",wid)
            for w in wid: 
                if w[1][BalPlugin.STATUS_VALID]:
                    locktime = wid[0][1]['tx'].locktime
                    if locktime< timestamp_to_check:
                        raise WillExpiredException(f"WillExpired {wid}: {locktime}<{timestamp_to_check}")
        print('check all utxo in wallet are spent')
        for utxo in all_utxos:
            if not Util.in_utxo(utxo,all_inputs.keys()):
                    print("utxo is not spent",utxo.to_json())
                    raise NotCompleteWillException("Some utxo in the wallet is not included")
        #check that all spent uxtos are in wallet
        print('check all spent utxos are in wallet')
        for inp,ws in all_inputs.items():
            for w in ws:
                print(w)
                if w[1][BalPlugin.STATUS_VALID]:
                    if not w[2].prevout.txid.hex() in Will.only_valid_list(will):
                        if not Util.in_utxo(inp,all_utxos):
                            if callback_not_valid_tx:
                                print(f"trying to invalidate {w[0]}")
                                callback_not_valid_tx(w[0],w[2])
                    #return False
        print('tutto ok')
        return True
    
    def only_valid_list(will):
        out=[]
        for wid,w in will.items():
            if w[BalPlugin.STATUS_VALID]:
                out.append(wid)
        return out
    def check_heirs_are_present(will,heirs,timestamp_to_check):
        for heir in heirs:
            found = False
            if Util.parse_locktime_string(heirs[heir][2]) >= timestamp_to_check:
                for wid in Will.only_valid(will):
                    for wheir in will[wid]['heirs']:
                        if heir == wheir and heirs[heir][0] == will[wid]['heirs'][wheir][0] and heirs[heir][1] == will[wid]['heirs'][wheir][1]:
                            found = True
                            break
                    if found == True:
                        break
                if not found:
                    return False
        return True

    def check_willexecutors(will,willexecutors):
        print("check willexecutor")
        for url,we in willexecutors.items():
            print("WEEEE",url,we)
            if Willexecutors.is_selected(we):
                found = False
                for wid in Will.only_valid(will):
                    w=will[wid]
                    if willexecutor:=w.get("willexecutor",None):
                        print(willexecutor)
                        if Util.cmp_willexecutor(we,willexecutor):
                            print("WE FOUNDDDD",we)
                            print("WE 2",willexecutor)
                            found = True
                            break
                if not found:
                    print("we not found:",url,we)
                    return False
        return True

class WillExpiredException(Exception):
    pass
class NotCompleteWillException(Exception):
    pass
