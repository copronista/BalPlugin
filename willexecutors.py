import urllib.parse
import urllib.request
import json
from datetime import datetime

from electrum import constants

class Willexecutors():
    def get_willexecutors(bal_plugin):
        willexecutors = bal_plugin.config_get(bal_plugin.WILLEXECUTORS)
        print("GET WILLEXECUTORS")
        for w in willexecutors:
            Willexecutors.initialize_willexecutor(willexecutors[w],w)
        print(willexecutors)

        bal=bal_plugin.DEFAULT_SETTINGS[bal_plugin.WILLEXECUTORS]
        for bal_url,bal_executor in bal.items():
            if not bal_url in willexecutors:
                print("replace bal")
                willexecutors[bal_url]=bal_executor
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
        strtxs=""
        for wid in will:
            willitem = will[wid]
            if 'willexecutor' in willitem:
                willexecutor=willitem['willexecutor']
                if  willexecutor and Willexecutors.is_selected(willexecutor):
                    url=Willexecutors.get_url(willexecutor)
                    if not url in willexecutors:
                        willexecutor['txs']=""
                        willexecutors[url]=willexecutor
                    willexecutors[url]['txs']+=str(willitem['tx'])+"\n"
        #print(willexecutors)
        if not willexecutors:
            return
        for url in willexecutors:
            willexecutor = willexecutors[url]
            if Willexecutors.is_selected(willexecutor):
                push_transactions_to_willexecutor(strtxs,url)


    def push_transactions_to_willexecutor(strtxs,url):
        print(url,strtxs)
        try:
            req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/pushtxs", data=strtxs.encode('ascii'), method='POST')
            req.add_header('Content-Type', 'text/plain')
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')
                if response.status != 200:
                    print(f"error{response.status} pushing txs to: {url}")
        except Exception as e:
            print(f"error contacting {url} for pushing txs",e)

    def ping_servers(willexecutors):
        for url in willexecutors:
            willexecutors[url]=Willexecutors.getinfo_willexecutor(url,willexecutors[url])

    def getinfo_willexecutor(url,willexecutor):
        w=None
        try:
            print("GETINFO_WILLEXECUTOR")
            print(url)
            req = urllib.request.Request(url+"/"+constants.net.NET_NAME+"/info", method='GET')
            with urllib.request.urlopen(req) as response:
                response_data=response.read().decode('utf-8')

                w = json.loads(response_data)
                print("response_data", w['address'])
                w['status']=response.status
                w['selected']=Willexecutors.is_selected(willexecutor)
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
        willexecutor['selected'] = Willexecutors.is_selected(willexecutor,selected)

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

