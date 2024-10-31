import urllib.parse
import urllib.request
import json
from datetime import datetime

from electrum import constants
from electrum.gui.qt.util import WaitingDialog
from functools import partial
from electrum.i18n import _
from .balqt.baldialog import BalWaitingDialog



DEFAULT_TIMEOUT = 5
def get_willexecutors(bal_plugin, update = False,bal_window=False,force=False):
    willexecutors = bal_plugin.config_get(bal_plugin.WILLEXECUTORS)
    for w in willexecutors:
        initialize_willexecutor(willexecutors[w],w)

    bal=bal_plugin.DEFAULT_SETTINGS[bal_plugin.WILLEXECUTORS]
    for bal_url,bal_executor in bal.items():
        if not bal_url in willexecutors:
            print("replace bal")
            willexecutors[bal_url]=bal_executor
    if update:
        found = False
        for url,we in willexecutors.items():
            if is_selected(we):
                found = True
        if found or force:
            if bal_plugin.config_get(bal_plugin.PING_WILLEXECUTORS) or force:
                ping_willexecutors = True
                if bal_plugin.config_get(bal_plugin.ASK_PING_WILLEXECUTORS) and not force:
                    print(type(bal_window))
                    ping_willexecutors = bal_window.window.question(_("Contact willexecutors servers to update payment informations?"))
                if ping_willexecutors:
                    bal_window.ping_willexecutors(willexecutors)

    return willexecutors

def is_selected(willexecutor,value=None):
    if not value is None:
        willexecutor['selected']=value
    try:
        return willexecutor['selected']
    except:
        willexecutor['selected']=False
        return False


def push_transactions_to_willexecutors(will):
    willexecutors ={}
    for wid in will:
        willitem = will[wid]
        if willitem['Valid']:
            if willitem['Signed']:
                if not willitem['Pushed']:
                    if 'willexecutor' in willitem:
                        willexecutor=willitem['willexecutor']
                        if  willexecutor and is_selected(willexecutor):
                            url=willexecutor['url']
                            if not url in willexecutors:
                                willexecutor['txs']=""
                                willexecutor['txsids']=[]
                                willexecutors[url]=willexecutor
                            willexecutors[url]['txs']+=str(willitem['tx'])+"\n"
                            willexecutors[url]['txsids'].append(wid)
    #print(willexecutors)
    if not willexecutors:
        return
    for url in willexecutors:
        willexecutor = willexecutors[url]
        if is_selected(willexecutor):
            if 'txs' in willexecutor:
                if push_transactions_to_willexecutor(willexecutors[url]['txs'],url):
                    for wid in willexecutors[url]['txsids']:
                        will[wid]['Pushed']=True
                        will[wid]['status']+='.Pushed'
                del willexecutor['txs']

def push_transactions_to_willexecutor(strtxs,url):
    print(url,strtxs)
    try:
        req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/pushtxs", data=strtxs.encode('ascii'), method='POST')
        req.add_header('Content-Type', 'text/plain')
        with urllib.request.urlopen(req, timeout = DEFAULT_TIMEOUT) as response:
            response_data = response.read().decode('utf-8')
            if response.status != 200:
                print(f"error{response.status} pushing txs to: {url}")
            else:
                return True
            
    except Exception as e:
        print(f"error contacting {url} for pushing txs",e)

def ping_servers(willexecutors):
    for url,we in willexecutors.items():
        willexecutors[url]=get_info_task(url,we)


def get_info_task(url,willexecutor):
    w=None
    try:
        print("GETINFO_WILLEXECUTOR")
        print(url)
        req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/info",  method='GET')
        with urllib.request.urlopen(req,timeout=DEFAULT_TIMEOUT) as response:
            response_data=response.read().decode('utf-8')

            w = json.loads(response_data)
            print("response_data", w['address'])
            w['status']=response.status
            w['selected']=is_selected(willexecutor)
            w['url']=url
            if response.status != 200:
                print(f"error{response.status} pushing txs to: {url}")
    except Exception as e:
        print(f"error {e} contacting {url}")
        if w:
            w['status']="KO"
        else:
            willexecutor['status'] = "KO"
    if w:
        willexecutor=w
    willexecutor['last_update'] = datetime.now().timestamp()
    return willexecutor

def initialize_willexecutor(willexecutor,url,status=None,selected=None):
    willexecutor['url']=url
    if not status is None:
        willexecutor['status'] = status
    willexecutor['selected'] = is_selected(willexecutor,selected)

def get_willexecutors_list_from_json(bal_plugin):
    try:
        with open("willexecutors.json") as f:
            willexecutors = json.load(f)
            for w in willexecutors:
                willexecutor=willexecutors[w]
                willexecutors.initialize_willexecutor(willexecutor,w,'New',False)
            bal_plugin.config.set_key(bal_plugin.WILLEXECUTORS,willexecutors,save=True)
            return h
    except Exception as e:
        print("errore aprendo willexecutors.json:",e)
        return {}

def check_transaction(txid,url):
    print(f"url:txid")
    try:
        req = urllib.request.Request(url+"/searchtx", data=txid.encode('ascii'), method='POST')
        req.add_header('Content-Type', 'text/plain')
        with urllib.request.urlopen(req, timeout = DEFAULT_TIMEOUT) as response:
            if response.status != 200:
                print(f"error{response.status} checking txs to: {url}")
            else:
                response_data=response.read().decode('utf-8')
                print("response data",response_data)
                w = json.loads(response_data)

                return w
            
    except Exception as e:
        print(f"error contacting {url} for checking txs",e)
