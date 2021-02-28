import time, base64, hashlib, hmac, json, websocket, atexit, traceback, _thread

from traders.traderType import Frontend
import urllib.request as urllib2
from util import synchronized


class KrakenFrontend(Frontend):

    def __init__(self, coins, tradeGraph, filename=None):
        super().__init__("KR", 0.0026, tradeGraph, coins)
        
        self.domain = "https://api.kraken.com"
        self.privatePath = "/0/private/"
        self.publicPath = "/0/public/"

        self.tradeDict = self.__getTradeDict(coins)
        
        self.websocketClient = KrakenWebsocket(self, list(self.tradeDict.keys()))
#         self.websocketClient = KrakenWebsocket(self, ["BTC-USD"])
        
        if filename:
            with open(filename, 'r') as file:
                self.publicKey = file.readline().strip()
                self.privateKey = base64.b64decode(file.readline().strip())
    
    def __getTradeDict(self, coins):
        tradeDict = dict()
        # Map of Asset pair terms kraken terms to other kraken terms (why does this have to exist)
        krakenDict = {'ZUSD': 'USD',
                         'XXBT': 'XBT',
                         'XETH': 'ETH',
                         'XLTC': 'LTC',
                         'LINK': 'LINK',
                         'BCH': 'BCH',
                         'XZEC': 'ZEC',
                         'USDC': 'USDC',
                         'XXLM': 'XLM',
                         'AAVE': 'AAVE',
                         } 
        # Map of asset pair terms to local coin names
        coinDict = {'ZUSD': 'USD',
                         'XXBT': 'BTC',
                         'XETH': 'ETH',
                         'XLTC': 'LTC',
                         'LINK': 'LINK',
                         'BCH': 'BCH',
                         'XZEC': 'ZEC',
                         'USDC': 'USDC',
                         'XXLM': 'XLM',
                         'AAVE': 'AAVE',
                         } 
        
        products = self.__publicQuery("AssetPairs")
        for _, traits in products.items():
            # Avoid direct trades, which incur a higher fee
            if traits['fees'][0][1] / 100 > self.taxRate:
                continue
            n1 = traits['base']
            n2 = traits['quote']
            c1 = coinDict.get(n1)
            c2 = coinDict.get(n2)
            if c1 in coins and c2 in coins:
                tradeDict[krakenDict[n1] + '/' + krakenDict[n2]] = (c1, c2)
            elif c1 != None and c2 != None:
                print("UH OH! ", c1, c2)
        
        return tradeDict
    
    def verifyAuth(self):
        self.__privateQuery("Balance")
        return True

    def __privateQuery(self, queryMethod, queryData=""):
        n = nonce()
        queryData = queryData + "&nonce=" + n
        queryData = queryData.encode('utf-8')
         
        sha256 = hashlib.sha256(n.encode('utf-8') + queryData).digest()
        encode = self.privatePath.encode('utf-8') + queryMethod.encode('utf-8') + sha256
        hmacsha512 = hmac.new(self.privateKey, encode, hashlib.sha512)
         
        req = self.domain + self.privatePath + queryMethod
        urlRequest = urllib2.Request(req, queryData)
        urlRequest.add_header("API-Key", self.publicKey)
        urlRequest.add_header("API-Sign", base64.b64encode(hmacsha512.digest()))
        urlRequest.add_header("User-Agent", "ArbitCoin")
         
        response = json.loads(urllib2.urlopen(urlRequest).read().decode())
        if response.get('error'):
            raise Exception("ERR: {}\nOn Query:\n{}".format(response.get('error'), req))
        return response.get('result')
     
    def __publicQuery(self, queryMethod, queryData=""):
        req = self.domain + self.publicPath + queryMethod + '?' + queryData
        urlRequest = urllib2.Request(req)
         
        response = json.loads(urllib2.urlopen(urlRequest).read().decode())
        if response.get('error'):
            raise Exception("ERR: {}\nOn Query:\n{}".format(response.get('error'), req))
        return response.get('result')


class KrakenWebsocket:

    def __init__(self, parent, targets):
        self.parent = parent
        self.targets = targets
        _thread.start_new_thread(self.__wsInit, ())
        atexit.register(self.appClose)
        
    def __wsInit(self):
        self.ws = websocket.WebSocketApp("wss://ws.kraken.com/", on_open=self.on_open, on_message=self.on_message, on_error=self.on_error)
        self.ws.run_forever()

    def on_open(self, ws):
        try:
            subscr = {"event": "subscribe",
                      "subscription": {"name":"book"},
                      "pair": self.targets}
    
            ws.send(json.dumps(subscr))
            print("Kraken Websocket Online.", flush=True)
        except:
            traceback.print_exc()
        
    def appClose(self):
        self.ws.close()
        
    # https://docs.kraken.com/websockets/#message-trade
    @synchronized
    def on_message(self, ws, msg):
        try:
            msg = json.loads(msg)
            if type(msg) is dict:
                if msg.get('event') == 'heartbeat':
                    return
                if msg.get('event') == 'subscriptionStatus' and msg.get('status') == 'subscribed':
                    return
                if msg.get('event') == 'systemStatus' and msg.get('status') == 'online':
                    return
            elif type(msg) is list:
                if msg[1].get('as'):
                    self.__snapshotInit(msg)
                    return
                elif msg[1].get('a') or msg[1].get('b'):
                    self.__processTrade(msg)
                    return
            
            print("Unidentified Kraken Message: ", msg)
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
        pid = msg[-1]
        trades = msg[1]
        if type(msg[2]) is dict:
            trades.update(msg[2])
        
        if trades.get('a'):
            for t in trades.get('a'):
                price = float(t[0])
                size = float(t[1])
                if size > 0:
                    self.parent.addAskOption(pid, price, size)
                else:
                    self.parent.removeAskOption(pid, price)
        
        if trades.get('b'):
            for t in trades.get('b'):
                price = float(t[0])
                size = float(t[1])
                if size > 0:
                    self.parent.addBidOption(pid, price, size)
                else:
                    self.parent.removeBidOption(pid, price)
                    
    def on_error(self, ws, err):
        traceback.print_exc()
        

def nonce():
    return str(int(time.time() * 1000))        
