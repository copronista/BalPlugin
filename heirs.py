# Electrum - Lightweight Bitcoin Client
# Copyright (c) 2015 Thomas Voegtlin
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import re
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

import dns
import threading
from dns.exception import DNSException

from electrum.transaction import TxOutput
from electrum import bitcoin
from electrum import dnssec
from electrum.util import read_json_file, write_json_file, to_string,bfh
from electrum.logging import Logger, get_logger
from electrum.util import trigger_callback
from electrum import descriptor
from typing import Sequence,List
from electrum.transaction import PartialTxInput, PartialTxOutput,TxOutpoint,PartialTransaction
import datetime
import urllib.request
import urllib.parse
from electrum import constants
from .bal import BalPlugin
from decimal import Decimal

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
            output.value = int((in_amount-fee)/out_amount * output.value)

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



def parse_locktime_string(locktime,w):
    now = datetime.datetime.now()
    if locktime[-1] == 'y':
        locktime = str(int(locktime[:-1])*365) + "d"
    if locktime[-1] == 'd':
        return int((now + datetime.timedelta(days = int(locktime[:-1]))).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    if locktime[-1] == 'b':
        locktime = int(locktime[:-1])
        height = get_current_height(w.network)
        locktime+=int(height)

    return int(locktime)



def is_perc(value):
    return value[-1] == '%'

def prepare_transactions(locktimes, available_utxos, fees, wallet):

    total_used_utxos = []
    txsout={}
    for locktime,heirs in locktimes.items():

        fee=fees.get(locktime,0) 
        out_amount = 0.0
        description = ""
        for name,heir in heirs.items():

            try:
                out_amount += int(heir[HEIR_REAL_AMOUNT])

                description += f"{name}\n"
            except:
                pass

        in_amount = 0.0
        used_utxos = []
        try:
            while utxo := available_utxos.pop():
                    value = utxo.value_sats()
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
                outputs.append(PartialTxOutput.from_address_and_value(heir[HEIR_ADDRESS], int(heir[HEIR_REAL_AMOUNT])))

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
        have_change=False
        if change:
            have_change=True
            outputs.append(change)

        #reduce_outputs(in_amount,out_amount,fees[locktime],outputs)
        tx = PartialTransaction.from_io(used_utxos, outputs, locktime=parse_locktime_string(locktime,wallet), version=2)
        if len(description)>0: tx.description = description[:-1]
        else: tx.description = ""
        tx.heirsvalue = heirsvalue
        tx.set_rbf(True) 
#        tx.remove_signatures()
#        wallet.sign_transaction(tx, password, ignore_warnings=True)
        txid = tx.txid()
        if txid is None:
            raise Exception("txid is none",tx)
        
        tx.my_locktime = locktime
        txsout[txid]=tx
        
        changes= tx.get_change_outputs()
        for change in changes:
            change_idx=tx.get_output_idxs_from_address(change.address)
            prevout = TxOutpoint(txid=bfh(tx.txid()), out_idx=change_idx.pop())
            txin = PartialTxInput(prevout=prevout)
            txin._trusted_value_sats = change.value
            txin.script_descriptor = change.script_descriptor
            txin.is_mine=True
            txin._TxInput__address=change.address
            txin.script_sig = b''

            available_utxos.append(txin)
        
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
    from pprint import pprint
    pprint(remaining)


#TODO push transactions to willexecutors servers
def push_transactions_to_willexecutors(txs):
    willexecutors ={}
    for txid,tx in txs.items():
        if not tx.willexecutor: continue
        willexecutors[tx.willexecutor]=True
    willexecutors=willexecutors.keys()
    if not willexecutors:
        return
    strtxs = "\n".join(str(tx) for tx in txs.values())
    for url,willexecutor in willexecutors.items():
        push_transactions_to_willexecutor(txs,selected_willexecutors,url)

def push_transactions_to_willexecutor(txs,selected_willexecutors, url):
    if url in selected_willexecutors:
        try:
            req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/pushtxs", data=strtxs.encode('ascii'), method='POST')
            req.add_header('Content-Type', 'text/plain')
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')
                if response.status != 200:
                    print(f"error{response.status} pushing txs to: {url}")
        except:  
            print(f"error contacting {url} for pushing txs")
def getinfo_willexecutor(url,willexecutor):
    try:
        print("GETINFO_WILLEXECUTOR")
        print(url)
        req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/info", method='GET')
        with urllib.request.urlopen(req) as response:
            response_data=response.read().decode('utf-8')
            print("response_data", response_data)
            if response.status != 200:
                print(f"error{response.status} pushing txs to: {url}")
    except Exception as e:
        print(f"error {e} contacting {url}")
    w={}
    return {"address":w.get("address",willexecutor["address"]),"base_fee":w.get("base_fee",willexecutor["base_fee"])}
def print_transaction(heirs,tx,locktimes,tx_fees):
    jtx=tx.to_json()
    print(f"TX: {tx.txid()}\t-\tLocktime: {jtx['locktime']}")
    print(f"--------INPUTS: {len(jtx['inputs'])}\t{tx.input_value()}--------")
    for inp in jtx["inputs"]:
        print(f"{inp['address']}: {inp['value_sats']}")
    print(f"--------OUTPUTS: {len(jtx['outputs'])}\t{tx.output_value()}--------")
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
        print(dict(self))
        self.db.put('heirs', dict(self))

    def import_file(self, path):
        data = read_json_file(path)
        data = self._validate(data)
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

    def get_locktimes(self):
        locktimes = {}
        for key in self.keys():
            locktimes[self[key][HEIR_LOCKTIME]]=0
        return locktimes.keys()

    def check_locktime(self):
        return False

    def prepare_lists(self, balance, total_fees, wallet, willexecutor = False):
        fixed_amount = 0
        percent_amount = 0.0
        willexecutors_amount = 0 
        fixed_heirs = {}
        percent_heirs = {}
        willexecutors = {}
        heir_list = {}
        onlyfixed = False
        newbalance = balance - total_fees
        locktimes = self.get_locktimes();
        if willexecutor:
            for locktime in locktimes:
                base_fee = int(willexecutor['base_fee'])
                willexecutors_amount += base_fee
                h = [None] * 4
                h[HEIR_AMOUNT] = base_fee
                h[HEIR_REAL_AMOUNT] = base_fee
                h[HEIR_LOCKTIME] = locktime
                h[HEIR_ADDRESS] = willexecutor['address']
                willexecutors["w!ll3x3c\""+willexecutor['url']+"\""+str(locktime)] = h
            heir_list.update(willexecutors)
            newbalance -= willexecutors_amount

        for key in self.keys():
            print("mario",key)
            if is_perc(self[key][HEIR_AMOUNT]):
                percent_amount += float(self[key][HEIR_AMOUNT][:-1])
                percent_heirs[key] =list(self[key])
            else:
                heir_amount = int(Decimal(self[key][HEIR_AMOUNT])* pow(10,self.decimal_point))
                if heir_amount>wallet.dust_threshold():
                    fixed_amount += heir_amount
                    fixed_heirs[key] = list(self[key])
                    fixed_heirs[key].insert(HEIR_REAL_AMOUNT,heir_amount)
                    #find_regex += self[key]
                else:
                    print("heir amount<dust threshold",) 

        if fixed_amount > newbalance:
            print(f"warning fixed_amount({fixed_amount}) > balance-fee({newbalance})")
            amount = 0
            for key in fixed_heirs:
                value = int(newbalance/fixed_amount*float(fixed_heirs[key][HEIR_AMOUNT]))
                if value < wallet.dust_threshold():
                    value=0
                fixed_heirs[key].insert(HEIR_REAL_AMOUNT, value)
                amount += value
            fixed_amount=amount
            onlyfixed = True

        heir_list.update(fixed_heirs)
        
        newbalance -= fixed_amount
        print("newbalance",newbalance)   
        if newbalance > 0:
            perc_amount=0 
            for key,value in percent_heirs.items():
                value = int(newbalance/percent_amount*float(value[HEIR_AMOUNT][:-1]))
                if value > wallet.dust_threshold(): 
                    percent_heirs[key].insert(HEIR_REAL_AMOUNT, value)
                perc_amount += value
            newbalance -= perc_amount
            heir_list.update(percent_heirs)

        heir_list = sorted(heir_list.items(), key = lambda item: parse_locktime_string(item[1][HEIR_LOCKTIME],wallet))
        print("heir_list",heir_list)
    
        #TODO: ADD A WAY TO REMOVE DUST HEIRS

        locktimes = {}
        for key, value in heir_list:
            strlocktime=str(value[HEIR_LOCKTIME])
            if not strlocktime in  locktimes: locktimes[strlocktime]={key:value}
            else: locktimes[strlocktime][key]=value

        return locktimes, onlyfixed
    def is_perc(self,key):
        return is_perc(self[key][HEIR_AMOUNT])
    def buildTransactions(self,bal_plugin,wallet):
        balance = 0.0
        len_utxo_set = 0
        available_utxos = []
        utxos = wallet.get_utxos()
        willexecutors = bal_plugin.config_get(BalPlugin.WILLEXECUTORS) or {}
        selected_willexecutors = bal_plugin.config_get(BalPlugin.SELECTED_WILLEXECUTORS)
        tx_fees = bal_plugin.config_get(BalPlugin.TX_FEES)
        self.decimal_point=bal_plugin.config.get_decimal_point()

        for utxo in utxos:
            if utxo.value_sats()> 68*tx_fees:
                balance += utxo.value_sats()
                len_utxo_set += 1
                available_utxos.append(utxo)
        if len_utxo_set==0: return
        j=-2
        willexecutorsitems = list(willexecutors.items())
        willexecutorslen = len(willexecutorsitems)
        alltxs = {}
        print(willexecutorsitems)
        while True:
            j+=1
            if j >= willexecutorslen:
                print("j> willexecutorslen")
                break
            elif 0 <= j:
                print("hello",j,willexecutorslen,willexecutorsitems[j])
                url, willexecutor = willexecutorsitems[j]
                if not url in selected_willexecutors:
                    print(f"{url}is not in {selected_willexecutors}")
                    continue
                willexecutor["url"]=url
                willexecutor_info=getinfo_willexecutor(url,willexecutor)
                if not willexecutor_info["address"]:
                    print(f"{willexecutor_info} no address")
                    continue
                willexecutor["address"]=willexecutor_info["address"]
                willexecutor["base_fee"]=willexecutor_info["base_fee"]
            elif j == -1:
                url = willexecutor = False
            else:
                break
            fees = {}
            i=0
            while True:
                txs = []
                redo = False
                i+=1
                total_fees=0
                for fee in fees:
                    total_fees += int(fees[fee])
                print("total_fees",total_fees)
                newbalance = balance 
                locktimes, onlyfixed = self.prepare_lists(balance, total_fees, wallet, willexecutor)
                print("locktimes",locktimes)
                try:
                    txs = prepare_transactions(locktimes, available_utxos[:], fees, wallet)
                except Exception as e:
                    print(e,e.heirname,url,selected_willexecutors)
                    if "w!ll3x3c" in e.heirname:
                        selected_willexecutors.remove(url)
                        break 
                print("txs",txs)
                total_fees = 0
                total_fees_real = 0
                total_in = 0
                for txid,tx in txs.items():
                    tx.willexecutor = willexecutor
                    fee = tx.estimated_size() * tx_fees    
                    total_fees += fee
                    total_fees_real +=tx.get_fee()
                    total_in += tx.input_value()
                    rfee= tx.input_value()-tx.output_value()
                    if rfee < fee or rfee > fee+ wallet.dust_threshold():
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

    #TODO validate heirs json import file
    def _validate(self, data):
        #for k, v in list(data.items()):
        #    if k == 'heirs':
        #        return self._validate(v)
        #    if not bitcoin.is_address(k):
        #        data.pop(k)
        #    else:
        #        _type, _ = v
        #        if _type != 'address':
        #            data.pop(k)
        return data

