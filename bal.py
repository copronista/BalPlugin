import random
import os
from hashlib import sha256
from typing import NamedTuple, Optional, Dict, Tuple

from electrum.plugin import BasePlugin
from electrum.util import to_bytes, bfh
from electrum import json_db
from electrum.transaction import tx_from_any

from .util import Util
json_db.register_dict('heirs', tuple, None)
json_db.register_dict('will', lambda x: get_will(x), None)

def get_will(x):
    try:
        x['tx']=tx_from_any(x['tx'])
    except Exception as e:
        Util.print_var(x)
        raise e

    return x


class BalPlugin(BasePlugin):
    LOCKTIME_TIME = "bal_locktime_time"
    LOCKTIME_BLOCKS = "bal_locktime_blocks"
    LOCKTIMEDELTA_TIME = "bal_locktimedelta_time"
    LOCKTIMEDELTA_BLOCKS = "bal_locktimedelta_blocks"
    TX_FEES = "bal_tx_fees"
    BROADCAST = "bal_broadcast"
    ASK_BROADCAST = "bal_ask_broadcast"
    INVALIDATE = "bal_invalidate"
    ASK_INVALIDATE = "bal_ask_invalidate"
    PREVIEW = "bal_preview"
    SAVE_TXS = "bal_save_txs"
    WILLEXECUTORS = "bal_willexecutors"
    SELECTED_WILLEXECUTORS = "bal_selected_willexecutors"



    DEFAULT_SETTINGS={
        LOCKTIME_TIME: 90,
        LOCKTIME_BLOCKS: 144*90,
        LOCKTIMEDELTA_TIME: 7,
        LOCKTIMEDELTA_BLOCKS:144*7,
        TX_FEES: 100,
        BROADCAST: True,
        ASK_BROADCAST: True,
        INVALIDATE: True,
        ASK_INVALIDATE: True,
        PREVIEW: True,
        SAVE_TXS: True,
        WILLEXECUTORS:  {
            'https://bitcoin-after.life/': {
                "base_fee": 100000,
                "status": 0,
                "info":"Bitcoin After Life Will Executor",
                "address":"bcrt1qa5cntu4hgadw8zd3n6sq2nzjy34sxdtd9u0gp7"
            }
        },
        SELECTED_WILLEXECUTORS:[],
    }

    STATUS_NEW = 'New'
    STATUS_COMPLETE = 'Complete'
    STATUS_BROADCASTED = 'Broadcasted'
    STATUS_PUSHED = 'Pushed'
    STATUS_EXPORTED = 'Exported'
    STATUS_REPLACED = 'Replaced'
    STATUS_INVALIDATED = 'Invalidated' 
    STATUS_ANTICIPATED = 'Anticipated'

    LATEST_VERSION = '1'
    KNOWN_VERSIONS = ('0', '1')
    assert LATEST_VERSION in KNOWN_VERSIONS

    SIZE = (159, 97)

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.base_dir = os.path.join(config.electrum_path(), 'bal')
        print(self.base_dir)
        self.parent = parent
        self.config = config
        self.name = name
        self.willexecutors = {}

    def config_get(self,key):
        v = self.config.get(key,None)
        if v is None:
            self.config.set_key(key,self.DEFAULT_SETTINGS[key],save=True)
            v = self.DEFAULT_SETTINGS[key]
        return v

    def will_not_replaced_nor_invalidated(self):
        for k,v in self.will.items():
            if not BalPlugin.STATUS_REPLACED in v['status']:
                if not BalPlugin.STATUS_INVALIDATED in v['status']:
                        yield k


    def is_will_valid(self,will, block_to_check, timestamp_to_check, all_utxos,callback_not_valid_tx=None):
        spent_utxos = []
        spent_utxos_tx = []
        locktimes_time,locktimes_blocks = Util.get_lowest_locktimes_from_will(will)
        for txid,willitem in will.items():
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
                print("locktime",locktimes_blocks[0],block_to_check,Util.chk_locktime(timestamp_to_check,block_to_check,locktimes_blocks[0]))
                print("locktime outdated",locktimes_time,locktimes_blocks,block_to_check,timestamp_to_check)
                print("will need to be invalidated")
                return False
        #check that all utxo in wallet ar e spent
        print('check all utxo in wallet are spent')
        for utxo in all_utxos:
            if not Util.in_utxo(utxo,spent_utxos):
                    print("utxo is not spent",utxo.to_json())
                    return False
        #check that all spent uxtos are in wallet
        print('check all spent utxos are in wallet')
        for txid,s_utxo in spent_utxos_tx:
            Util.print_var(s_utxo)
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

