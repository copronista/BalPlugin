import re
import json
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING,Sequence,List

import dns
import threading
import math
from dns.exception import DNSException

from electrum import bitcoin,dnssec,descriptor,constants
from electrum.util import read_json_file, write_json_file, to_string,bfh,trigger_callback
from electrum.logging import Logger, get_logger
from electrum.transaction import PartialTxInput, PartialTxOutput,TxOutpoint,PartialTransaction,TxOutput
import datetime
import urllib.request
import urllib.parse
from .bal import BalPlugin
from .util import Util
from .willexecutors import Willexecutors
if TYPE_CHECKING:
    from .wallet_db import WalletDB
    from .simple_config import SimpleConfig


_logger = get_logger(__name__)

HEIR_ADDRESS = 0
HEIR_AMOUNT = 1
HEIR_LOCKTIME = 2
HEIR_REAL_AMOUNT = 3
TRANSACTION_LABEL = "inheritance transaction"
class AliasNotFoundException(Exception):
    pass


def reduce_outputs(in_amount, out_amount, fee, outputs):
    if in_amount < out_amount:
        for output in outputs:
            print("reduce_amount",output.value)
            output.value = math.floor((in_amount-fee)/out_amount * output.value)

#TODO: put this method inside wallet.db to replace or complete get_locktime_for_new_transaction
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





def prepare_transactions(locktimes, available_utxos, fees, wallet):
    print("prepare succhiacazzi")
    available_utxos=sorted(available_utxos, key=lambda x:"{}:{}:{}".format(x.value_sats(),x.prevout.txid,x.prevout.out_idx))
    total_used_utxos = []
    txsout={}
    locktime,_=Util.get_lowest_locktimes(locktimes)
    if not locktime:
        print("not locktime diocane",locktimes)
        return
    #print(locktime)
    locktime=locktime[0]

    heirs = locktimes[locktime]
    #for locktime,heirs in locktimes.items():
    vero=True
    while vero:
        print("PREPARE TRANSACTIONS:",heirs,locktimes)
        vero=False
        fee=fees.get(locktime,0) 
        out_amount = fee
        description = ""
        print("out_amount_start",out_amount,fee)
        for name,heir in heirs.items():

            try:
                out_amount += math.floor(heir[HEIR_REAL_AMOUNT])
                print("out_amount",heir,out_amount)
                description += f"{name}\n"
            except Exception as e:
                print("ERROR, PREPARE TRANSACTIONS",e)
                pass

        in_amount = 0.0
        used_utxos = []
        try:
            while utxo := available_utxos.pop():
                value = utxo.value_sats()
                print("utxo value",value,in_amount,out_amount)
                in_amount += value
                used_utxos.append(utxo)
                if in_amount > out_amount:
                    break

        except IndexError:
            pass
        if int(in_amount) < int(out_amount):
            print(f"in_amount{in_amount}<out_amount{out_amount}")
            break
            #for heir in heirs:
            #    heir[3] = int(in_amount/out_amount*float(heir[3]))
            #raise Exception(f"error building heirs transactions in_amount < out_amount ({in_amount}<{out_amount}) not enought funds")
            ####TODO: costruire le transazioni
        outputs = []
        for name,heir in heirs.items():

            try:
                outputs.append(PartialTxOutput.from_address_and_value(heir[HEIR_ADDRESS], math.floor(heir[HEIR_REAL_AMOUNT])))

            except Exception as e:
                e.heir=heir
                e.heirname=name
                print("impossible to append output abort")
                raise e

        
        #tx = wallet.make_unsigned_transaction(
        #    coins=used_utxos,
        #    outputs=outputs,
        #    fee=1000,
        #    is_sweep=False)
        heirsvalue=out_amount
        


        change = get_change_output(wallet, in_amount, out_amount, fee)
        if change:
            print("change")
            outputs.append(change)

        #reduce_outputs(in_amount,out_amount,fees[locktime],outputs)

        tx = PartialTransaction.from_io(used_utxos, outputs, locktime=Util.parse_locktime_string(locktime,wallet), version=2)
        if len(description)>0: tx.description = description[:-1]
        else: tx.description = ""
        tx.heirsvalue = heirsvalue
        tx.set_rbf(True) 
        tx.remove_signatures()
        #wallet.sign_transaction(tx, "a" )
        txid = tx.txid()
        if txid is None:
            raise Exception("txid is none",tx)
        
        tx.heirs = heirs
        tx.my_locktime = locktime
        txsout[txid]=tx
         
            #print_var(change,"CHANGE")
        if change:
            change_idx=tx.get_output_idxs_from_address(change.address)
            prevout = TxOutpoint(txid=bfh(tx.txid()), out_idx=change_idx.pop())
            txin = PartialTxInput(prevout=prevout)
            txin._trusted_value_sats = change.value
            txin.script_descriptor = change.script_descriptor
            txin.is_mine=True
            txin._TxInput__address=change.address
            txin._TxInput__scriptpubkey = change.scriptpubkey
            txin._TxInput__value_sats = change.value
            txin.utxo = tx
            #print_utxo(txin,"TXIN")
            available_utxos.append(txin)
            #to_be_exploded.append(txin)
        txsout[txid].available_utxos = available_utxos[:]
    return txsout


def get_utxos_from_inputs(tx_inputs,tx,utxos):
    for tx_input in tx_inputs:
        prevoutstr=tx_input.prevout.to_str()
        utxos[prevoutstr] =utxos.get(prevoutstr,{'input':tx_input,'txs':[]})
        utxos[prevoutstr]['txs'].append(tx)
    return utxos

#TODO calculate de minimum inputs to be invalidated 
def invalidate_inheritance_transactions(wallet):
    listids = []
    utxos = {}
    dtxs = {}
    for k,v in wallet.get_all_labels().items():
        print("____TX____")
        print(k)
        tx = None
        if TRANSACTION_LABEL == v:
            tx=wallet.adb.get_transaction(k)
        print("tx:",tx)
        if tx:
            dtxs[tx.txid()]=tx
            get_utxos_from_inputs(tx.inputs(),tx,utxos)

    for key,utxo in utxos.items():
        txid=key.split(":")[0]
        if txid in dtxs:
            for tx in utxo['txs']:
                txid =tx.txid()
                del dtxs[txid]
            
    utxos = {}
    for txid,tx in dtxs.items():
        get_utxos_from_inputs(tx.inputs(),tx,utxos)

    utxos = sorted(utxos.items(), key = lambda item: len(item[1]))


    remaining={}
    invalidated = []
    for key,value in utxos:
        for tx in value['txs']:
            txid = tx.txid()
            if not txid in invalidated:
                invalidated.append(tx.txid())
                remaining[key] = value

def completed_willitem(will):
    for txid,willitem in will.items():
        if willitem['tx'].is_complete():
            yield willitem
        else:
            print(f"tx:{txid} is not complete")

def print_transaction(heirs,tx,locktimes,tx_fees):
    jtx=tx.to_json()
    print(f"TX: {tx.txid()}\t-\tLocktime: {jtx['locktime']}")
    print(f"---")
    for inp in jtx["inputs"]:
        print(f"{inp['address']}: {inp['value_sats']}")
    print(f"---")
    for out in jtx["outputs"]:
        heirname=""
        for key in heirs.keys():
            heir=heirs[key]
            if heir[HEIR_ADDRESS] == out['address'] and str(heir[HEIR_LOCKTIME]) == str(jtx['locktime']):
                heirname=key
        print(f"{heirname}\t{out['address']}: {out['value_sats']}")

    print()
    size = tx.estimated_size()
    print("fee: {}\texpected: {}\tsize: {}".format(tx.input_value()-tx.output_value(), size*tx_fees, size))

    print()
    try:
        print(tx.serialize_to_network())
    except:
        print("impossible to serialize")
    print()

def get_change_output(wallet,in_amount,out_amount,fee):
    change_amount = int(in_amount - out_amount - fee)
    if change_amount > wallet.dust_threshold():
        change_addresses = wallet.get_change_addresses_for_new_transaction()
        out = PartialTxOutput.from_address_and_value(change_addresses[0], change_amount)
        out.is_change = True
        return out
    
class Heirs(dict, Logger):

    def __init__(self, db: 'WalletDB'):
        Logger.__init__(self)
        self.db = db
        d = self.db.get('heirs', {})
        try:
            self.update(d)
        except e as Exception:
            print("exception init heirs",e)
            return
        # backward compatibility
        #for k, v in self.items():
        #    _type, n = v
        #    if _type == 'address' and bitcoin.is_address(n):
        #        self.pop(k)
        #        self[n] = ('address', k)
    def invalidate_transactions(self,wallet):
        invalidate_inheritance_transactions(wallet)

    def save(self):
        self.db.put('heirs', dict(self))

    def import_file(self, path):
        data = read_json_file(path)
        data = Heirs._validate(data)
        self.update(data)
        self.save()

    def export_file(self, path):
        write_json_file(path, self)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.save()

    def pop(self, key):
        if key in self.keys():
            res = dict.pop(self, key)
            self.save()
            return res

    def get_locktimes(self,from_locktime):
        locktimes = {}
        for key in self.keys():
            locktime = Util.parse_locktime_string(self[key][HEIR_LOCKTIME])
            if locktime > from_locktime:
                locktimes[int(locktime)]=None
        return locktimes.keys()

    def check_locktime(self):
        return False

    def normalize_perc(self, heir_list, total_balance, relative_balance,wallet):
        amount = 0
        for key,value in heir_list.items():
            try:
                value = math.floor(total_balance/relative_balance*self.amount_to_float(value[HEIR_AMOUNT]))
                if value > wallet.dust_threshold():
                    heir_list[key].insert(HEIR_REAL_AMOUNT, value)
                    amount += value

            except Exception as e:
                print("error getting heirs",e,key,heir_list[key],total_balance,relative_balance)
        return amount

    def amount_to_float(self,amount):
        try:
            return float(amount)
        except:
            try:
                return float(amount[:-1])
            except:
                print("error parsing amount",amount)
                return 0.0


    def prepare_lists(self, balance, total_fees, wallet, willexecutor = False, from_locktime = 0):
        fixed_amount = 0
        percent_amount = 0.0
        willexecutors_amount = 0 
        fixed_heirs = {}
        percent_heirs = {}
        willexecutors = {}
        heir_list = {}
        onlyfixed = False
        newbalance = balance - total_fees
        print(f"inizio: balance: {balance}\tnewbalance: {newbalance}\ttotal_fees:{total_fees}")
        locktimes = self.get_locktimes(from_locktime);
        if willexecutor:
            for locktime in locktimes:
                if Util.int_locktime(locktime) > from_locktime:
                    try:
                        base_fee = int(willexecutor['base_fee'])
                        willexecutors_amount += base_fee
                        h = [None] * 4
                        h[HEIR_AMOUNT] = base_fee
                        h[HEIR_REAL_AMOUNT] = base_fee
                        h[HEIR_LOCKTIME] = locktime
                        h[HEIR_ADDRESS] = willexecutor['address']
                        willexecutors["w!ll3x3c\""+willexecutor['url']+"\""+str(locktime)] = h
                    except Exception as e:
                        print(willexecutor)
                        print("error willexecutor:",e)
                        return [],False
            heir_list.update(willexecutors)
            newbalance -= willexecutors_amount
        print(f"after we: balance: {balance}\tnewbalance: {newbalance}\ttotal_fees:{total_fees}")
        for key in self.keys():
            print(key)
            try:
                if not Util.parse_locktime_string(self[key][HEIR_LOCKTIME]) > from_locktime:
                    print("excluded heir",self[key])
                    continue
                else:
                    print("todo bien")
                if Util.is_perc(self[key][HEIR_AMOUNT]):
                    print("is perc")
                    percent_amount += float(self[key][HEIR_AMOUNT][:-1])
                    percent_heirs[key] =list(self[key])
                else:
                    print("is fixed")
                    heir_amount = int(float(self[key][HEIR_AMOUNT]))
                    if heir_amount>wallet.dust_threshold():
                        print("good")
                        fixed_amount += heir_amount
                        print("fixed_amount:", fixed_amount)
                        fixed_heirs[key] = list(self[key])
                        fixed_heirs[key].insert(HEIR_REAL_AMOUNT,heir_amount)
                        #find_regex += self[key]
                    else:
                        print(f"heir({key}) amount({heir_amount})<dust threshold({wallet.dust_threshold()})",) 
            except Exception as e: 
                print("Error getting heir info",e)
        if fixed_amount > newbalance:
            print(f"warning fixed_amount({fixed_amount}) > balance-fee({newbalance})")
            fixed_amount = self.normalize_perc(fixed_heirs,newbalance,fixed_amount,wallet)

            onlyfixed = True

        heir_list.update(fixed_heirs)
        
        newbalance -= fixed_amount
        print(f"after fixed balance: {balance}\tnewbalance: {newbalance}\ttotal_fees:{total_fees}")
        #print("newbalance",newbalance)   
        if newbalance > 0:
            print("calculate_percentage_amount")
            perc_amount = self.normalize_perc(percent_heirs,newbalance,percent_amount,wallet)
            newbalance -= perc_amount
            heir_list.update(percent_heirs)

        print(f"after perc balance: {balance}\tnewbalance: {newbalance}\ttotal_fees:{total_fees}")
        if newbalance > 0:
            print("percentage amount not enought to fill all utxos, retrying with fixed heirs:",newbalance)
            newbalance += fixed_amount
            fixed_amount = self.normalize_perc(fixed_heirs,newbalance,fixed_amount,wallet)
            newbalance -= fixed_amount
            print(fixed_heirs)
            heir_list.update(fixed_heirs)
        print(f"after fixed22 balance: {balance}\tnewbalance: {newbalance}\ttotal_fees:{total_fees}")
        
        heir_list = sorted(heir_list.items(), key = lambda item: Util.parse_locktime_string(item[1][HEIR_LOCKTIME],wallet))
    

        locktimes = {}
        for key, value in heir_list:
            print("heir keyvalue:",key,value)
            locktime=Util.parse_locktime_string(value[HEIR_LOCKTIME])
            if not locktime in  locktimes: locktimes[locktime]={key:value}
            else: locktimes[locktime][key]=value

        return locktimes, onlyfixed
    def is_perc(self,key):
        return Util.is_perc(self[key][HEIR_AMOUNT])

    def buildTransactions(self,bal_plugin,wallet,tx_fees = None, utxos=None,from_locktime=0):
        print("------FROM LOCKTIME",from_locktime)
        Heirs._validate(self)
        if len(self)<=0:
            return
        balance = 0.0
        len_utxo_set = 0
        available_utxos = []
        if not utxos:
            utxos = wallet.get_utxos()
        willexecutors = Willexecutors.get_willexecutors(bal_plugin) or {}
        #tx_fees = bal_plugin.config_get(BalPlugin.TX_FEES)
        print("txFEES:",tx_fees)
        self.decimal_point=bal_plugin.config.get_decimal_point()
        no_willexecutors = bal_plugin.config_get(BalPlugin.NO_WILLEXECUTOR)
        for utxo in utxos:
            if utxo.value_sats()> 0*tx_fees:
                balance += utxo.value_sats()
                len_utxo_set += 1
                available_utxos.append(utxo)
        print("len utxos",len(utxos))
        print("len available utxos",len(available_utxos))
        if len_utxo_set==0: return
        j=-2
        willexecutorsitems = list(willexecutors.items())
        willexecutorslen = len(willexecutorsitems)
        alltxs = {}
        #print(willexecutorsitems)
        while True:
            j+=1
            if j >= willexecutorslen:
                #print("j> willexecutorslen")
                break
            elif 0 <= j:
                #print("hello",j,willexecutorslen,willexecutorsitems[j])
                url, willexecutor = willexecutorsitems[j]
                if not Willexecutors.is_selected(willexecutor):
                    continue
            elif j == -1:
                if not no_willexecutors:
                    continue
                url = willexecutor = False
            else:
                break
            fees = {}
            i=0
            while True:
                txs = {}
                redo = False
                i+=1
                total_fees=0
                for fee in fees:
                    total_fees += int(fees[fee])
                    print("total_feesaaaaa:",total_fees)
                #print("total_fees",total_fees)
                newbalance = balance 
                locktimes, onlyfixed = self.prepare_lists(balance, total_fees, wallet, willexecutor, from_locktime)
                #print("locktimes",locktimes)
                print("fees",fees)
                try:
                    txs = prepare_transactions(locktimes, available_utxos[:], fees, wallet)
                    if not txs:
                        return {}
                    #for tx in txsfirs:
                    #    if reusable_input
                except Exception as e:
                    try:
                        print(e,e.heirname,url)
                        if "w!ll3x3c" in e.heirname:
                            Willexecutors.is_selected(willexecutors[w],False)
                            break
                    except:
                        raise e
                total_fees = 0
                total_fees_real = 0
                total_in = 0
                print("produced TXS",len(txs))
                for txid,tx in txs.items():
                    print(txid,tx.to_json())
                    tx.willexecutor = willexecutor
                    fee = tx.estimated_size() * tx_fees    
                    txs[txid].tx_fees= tx_fees
                    total_fees += fee
                    total_fees_real += tx.get_fee()
                    total_in += tx.input_value()
                    rfee= tx.input_value()-tx.output_value()
                    if rfee < fee or rfee > fee + wallet.dust_threshold():
                        print("tx_fees",tx_fees,"rfee",rfee,"fee",fee,"dust",wallet.dust_threshold())
                        redo = True
                    oldfees= fees.get(tx.my_locktime,0)
                    fees[tx.my_locktime]=fee


                if  balance - total_in > wallet.dust_threshold():
                    print("some utxo was not used",balance - total_in) 
                    redo = True
                if not redo:
                    break
                if i>=10:
                    break
            alltxs.update(txs)
            
        return alltxs
    def get_transactions(self,bal_plugin,wallet,tx_fees,utxos=None,from_locktime=0):
        print("get_transactions")
        txs=self.buildTransactions(bal_plugin,wallet,tx_fees,utxos,from_locktime)
        if txs:
            temp_txs = {}
            for txid in txs:
                if txs[txid].available_utxos:
                    print("change:",txs[txid].available_utxos)
                    Util.print_var(txs[txid].available_utxos)
                    temp_txs.update(self.get_transactions(bal_plugin,wallet,tx_fees,txs[txid].available_utxos,txs[txid].locktime))
            txs.update(temp_txs)
        return txs

        

    def resolve(self, k):
        if bitcoin.is_address(k):
            return {
                'address': k,
                'type': 'address'
            }
        if k in self.keys():
            _type, addr = self[k]
            if _type == 'address':
                return {
                    'address': addr,
                    'type': 'heir'
                }
        if openalias := self.resolve_openalias(k):
            return openalias
        raise AliasNotFoundException("Invalid Bitcoin address or alias", k)

    @classmethod
    def resolve_openalias(cls, url: str) -> Dict[str, Any]:
        out = cls._resolve_openalias(url)
        if out:
            address, name, validated = out
            return {
                'address': address,
                'name': name,
                'type': 'openalias',
                'validated': validated
            }
        return {}

    def by_name(self, name):
        for k in self.keys():
            _type, addr = self[k]
            if addr.casefold() == name.casefold():
                return {
                    'name': addr,
                    'type': _type,
                    'address': k
                }
        return None

    def fetch_openalias(self, config: 'SimpleConfig'):
        self.alias_info = None
        alias = config.OPENALIAS_ID
        if alias:
            alias = str(alias)
            def f():
                self.alias_info = self._resolve_openalias(alias)
                trigger_callback('alias_received')
            t = threading.Thread(target=f)
            t.daemon = True
            t.start()

    @classmethod
    def _resolve_openalias(cls, url: str) -> Optional[Tuple[str, str, bool]]:
        # support email-style addresses, per the OA standard
        url = url.replace('@', '.')
        try:
            records, validated = dnssec.query(url, dns.rdatatype.TXT)
        except DNSException as e:
            _logger.info(f'Error resolving openalias: {repr(e)}')
            return None
        prefix = 'btc'
        for record in records:
            string = to_string(record.strings[0], 'utf8')
            if string.startswith('oa1:' + prefix):
                address = cls.find_regex(string, r'recipient_address=([A-Za-z0-9]+)')
                name = cls.find_regex(string, r'recipient_name=([^;]+)')
                if not name:
                    name = address
                if not address:
                    continue
                return address, name, validated

    @staticmethod
    def find_regex(haystack, needle):
        regex = re.compile(needle)
        try:
            return regex.search(haystack).groups()[0]
        except AttributeError:
            return None

                
    def validate_address(address):
        if not bitcoin.is_address(address):
            print("notandaddress")
            raise NotAnAddress(f"not an address,{address}")
        return address

    def validate_amount(amount):
        try:
            if Util.is_perc(amount):
                famount = float(amount[:-1])
            else:
                famount = float(amount)
            if famount <= 0.00000001:
                raise AmountNotValid(f"amount have to be positive {famount} < 0")
        except Exception as e:
            print("amountnotvalid")
            raise AmountNotValid(f"amount not properly formatted, {e}")
        return amount

    def validate_locktime(locktime):
        try:
            flocktime = Util.parse_locktime_string(locktime,None)
        except Exception as e:
            print("locktimenotvalid")
            raise LocktimeNotValid(f"locktime string not properly formatted, {e}")
        return locktime

    def validate_heir(k,v):     
        address = Heirs.validate_address(v[HEIR_ADDRESS])
        amount = Heirs.validate_amount(v[HEIR_AMOUNT])
        locktime = Heirs.validate_locktime(v[HEIR_LOCKTIME])
        return (address,amount,locktime)

    def _validate(data):
        for k, v in list(data.items()):
            if k == 'heirs':
                return Heirs._validate(v)
                       #data.pop(k)
            try:
                Heirs.validate_heir(k,v)
            except Exception as e:
                print(e)
                data.pop(k)
        return data

class NotAnAddress(ValueError):
    pass
class AmountNotValid(ValueError):
    pass
class LocktimeNotValid(ValueError):
    pass
