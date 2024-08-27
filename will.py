from .util import Util
from .bal import BalPlugin
from electrum.transaction import TxOutpoint,PartialTxInput,tx_from_any
from electrum.util import bfh
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
                print(_input.prevout.txid.hex())
                if _input.prevout.txid.hex() == willid:
                    out.append([_id,idi,_input.prevout.out_idx])
        return out
    #this method should build a tree with parent transactions
    def add_willtree(will):
        for willid in will:
            will[willid]['children'] = Will.get_children(will,willid)
            for child in will[willid]['children']:
                if not 'father' in will[child]: will[child]['father'] = []
                will[child]['father'].append(willid)


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
            if  w != wid and not tx.to_json() == will[w]['tx'].to_json():
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

  
    #this method will substitute childrent transaction input with real father transaction id
    def normalize_will(will,wallet=None):
        print("normalize will")
        to_be_deleted = []
        to_be_addedd = []
        for willid in will:
            if wallet:
                if isinstance(will[willid]['tx'],str):
                    will[willid]['tx']=Will.get_will(will[willid]['tx'])
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
            outputs = will[willid]['tx'].outputs()
            children = Will.get_children(will, willid)
            for child in children:
                change=outputs[child[2]]
                tx = will[child[0]]['tx']
                if parent_txid != willid:
                    inputs = tx.inputs()
                    print("previous_input:",inputs[child[1]].to_json())
                    prevout = TxOutpoint(txid=bfh(parent_txid), out_idx=child[2])
                    inp = PartialTxInput(prevout=prevout)
                    inp._trusted_value_sats = change.value
                    #inp.script_descriptor = change.script_descriptor
                    inp.is_mine=True
                    inp._TxInput__address=change.address
                    inp._TxInput__scriptpubkey = change.scriptpubkey
                    inp._TxInput__value_sats = change.value

                    tx._inputs[child[1]]=inp

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

        for w in to_be_deleted:
            print(f"will {w} have to be deleted")
            txid=will[w]['tx'].txid()
            will[txid]=will[child[0]]
            del will[w]


            


    #situations:
    #change will settings by user, id heir
    #if same id take the old
    def update_will(old_will,new_will):
        ow_todelete=[]
        nw_todelete=[]
        for oid in Will.only_valid(old_will):
            print("-----------oid",oid)
            if oid in new_will:
                print("equals, continue")
                new_will[oid]=old_will[oid]
                continue

            ow = old_will[oid]
            willitemfound = False
            for nid in new_will:
                print(">>>nid",nid)
                nw = new_will[nid]
                print("oldheirs",ow['heirs'])
                print("newheirs",nw['heirs'])
                if Util.cmp_heirs(ow['heirs'], nw['heirs']):
                    print("oldwillexecutor",ow['willexecutor'])
                    print("newwillexecutor",nw['willexecutor'])
                    #check will_executor
                    if ow['willexecutor'] == nw ['willexecutor']:
                        willitemfound = True
                        print("oldlocktime",ow['tx'].locktime)
                        print("newlocktime",nw['tx'].locktime)
                        if nw['tx'].locktime >= ow['tx'].locktime:
                            nw['tx'].locktime = ow['tx'].locktime
                    else:   

                        pass
                else:
                    pass
            if not willitemfound: #have to be invalidated, replaced or anticipated
                print("willitemnotfound")
                ow['status']+=BalPlugin.STATUS_REPLACED
                txid=ow['tx'].txid()
                oinputs = ow['tx'].inputs()
                #check input anticipate or replace
                for nid in new_will:
                    if new_will[nid]['tx'].locktime >= old_will[oid]['tx'].locktime:
                        for _input in new_will[nid]['tx'].inputs():
                            if Util.in_utxo(_input,oinputs):
                                anticipate = Util.anticipate_locktime(old_will[oid]['tx'].locktime,days=1)
                                if anticipate > Will.MIN_LOCKTIME and anticipate < new_will[nid]['tx'].locktime:
                                    new_will[nid]['tx'].locktime = int(anticipate)

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
    def __init__(self,*args,**kwargs):
        Exception.__init__(*args,*kwargs)

class NotCompleteWillException(Exception):
    pass
