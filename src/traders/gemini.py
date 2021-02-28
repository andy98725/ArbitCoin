import time, base64, hashlib, hmac, json, requests, traceback, websocket, _thread, atexit, ssl
from traders.traderType import Frontend
from util import synchronized


class GeminiFrontend(Frontend):
    
    def __init__(self, coins, tradeGraph, filename=None):
        super().__init__("GM", 0.0035, tradeGraph, coins)
        
        self.domain = "https://api.gemini.com" 
        self.publicPath = "/v1/" 
        self.privatePath = "/v1/" 
        
        self.tradeDict = self.__getTradeDict(coins)
        self.websocketClient = GeminiWebsocket(self, list(self.tradeDict.keys()))
        
        if filename:
            with open(filename, 'r') as file:
                self.publicKey = file.readline().strip()
                self.privateKey = file.readline().strip().encode()
    
    def __getTradeDict(self, coins):
        symbols = self.__publicQuery("symbols")
        ret = dict()
        # Since gemini symbols follow a pattern, generate from list:
        for s1 in coins:
            for s2 in coins:
                sym = s1 + s2
                if sym.lower() in symbols:
                    ret[sym] = (s1, s2)
                    
#         # To hard check each symbol:
#         for s in symbols:
#             info = self.__publicQuery("symbols/details/{}".format(s))
#             if info.get('base_currency') in coins and info.get('quote_currency') in coins:
#                 ret.append(s)
        return ret
    
    def verifyAuth(self):
        self.__privateQuery("balances")
#         print(self.__privateQuery("mytrades", {'symbol' : 'btcusd'}))
        return True
    
    def __privateQuery(self, queryMethod, queryMap={}):
        payload = {"request": self.privatePath + queryMethod, "nonce": nonce(), }
        payload.update(queryMap)
        b64 = base64.b64encode(json.dumps(payload).encode())
        request_headers = {
            'Content-Type': "text/plain",
            'Content-Length': "0",
            'X-GEMINI-APIKEY': self.publicKey,
            'X-GEMINI-PAYLOAD': b64,
            'X-GEMINI-SIGNATURE': hmac.new(self.privateKey, b64, hashlib.sha384).hexdigest(),
            'Cache-Control': "no-cache"
        }
          
        req = self.domain + self.privatePath + queryMethod
        response = requests.post(req, headers=request_headers).json()
        
        if response is dict and response.get('result') == 'error':
            raise Exception("{}\nOn Query:\n{}".format(response, req))
        return response
        
    def __publicQuery(self, queryMethod):
        req = self.domain + self.publicPath + queryMethod
        response = requests.get(req).json()
        
        if response is dict and response.get('result') == 'error':
            raise Exception("{}\nOn Query:\n{}".format(response, req))
        return response


class GeminiWebsocket:

    def __init__(self, parent, targets):
        self.parent = parent
        self.targets = targets
        
        _thread.start_new_thread(self.__wsInit, ())
        atexit.register(self.appClose)
        
    def __wsInit(self):
        self.ws = websocket.WebSocketApp("wss://api.gemini.com/v2/marketdata", on_open=self.on_open, on_message=self.on_message)
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def on_open(self, ws):
        try:
            subscr = {"type": "subscribe",
                      "subscriptions": [{"name":"l2",
                                    "symbols": self.targets}]
                      }
    
            ws.send(json.dumps(subscr))
            print("Gemini Websocket Online.", flush=True)
        except:
            traceback.print_exc()
        
    def appClose(self):
        self.ws.close()

    # https://docs.gemini.com/websocket-api/#market-data-version-2
    @synchronized
    def on_message(self, ws, msg):
        try:
            msg = json.loads(msg)
            if type(msg) is dict:
                if msg.get('type') == 'l2_updates':
                    self.__processTrade(msg)
                    return
                if msg.get('type') == 'heartbeat':
                    return
                if msg.get('type') == 'trade':
                    return  # TODO needed? 
            
            print("Unidentified Gemini Message: ", msg)
        except:
            traceback.print_exc()
        
    def __snapshotInit(self, msg):
        [_, trades, _, pid] = msg
        
        for t in trades.get('as'):
            price = float(t[0])
            size = float(t[1])
            self.parent.addAskOption(pid, price, size)
            
        for t in trades.get('bs'):
            price = float(t[0])
            size = float(t[1])
            self.parent.addBidOption(pid, price, size)
        
    def __processTrade(self, msg):
        pid = msg['symbol']
        for change in msg['changes']:
            price = float(change[1])
            size = float(change[2])
            
            if change[0] == 'buy':  # buy = bid
                if size > 0:
                    self.parent.addBidOption(pid, price, size)
                else:
                    self.parent.removeBidOption(pid, price)
            else:  # sell = ask
                if size > 0:
                    self.parent.addAskOption(pid, price, size)
                else:
                    self.parent.removeAskOption(pid, price)
#         pid = msg[-1]
#         trades = msg[1]
#         if type(msg[2]) is dict:
#             trades.update(msg[2])
#         
#         if trades.get('a'):
#             for t in trades.get('a'):
#                 price = float(t[0])
#                 size = float(t[1])
#                 if size > 0:
#                     self.parent.addAskOption(pid, price, size)
#                 else:
#                     self.parent.removeAskOption(pid, price)
#         
#         if trades.get('b'):
#             for t in trades.get('b'):
#                 price = float(t[0])
#                 size = float(t[1])
#                 if size > 0:
#                     self.parent.addBidOption(pid, price, size)
#                 else:
#                     self.parent.removeBidOption(pid, price)


def nonce():
    return str(int(time.time() * 1000))       
