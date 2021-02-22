import time, base64, hashlib, hmac, json, requests


class GeminiFrontend:
    
    def __init__(self, filename, coins):
        self.domain = "https://api.gemini.com" 
        self.publicPath = "/v1/" 
        self.privatePath = "/v1/" 
        
        with open(filename, 'r') as file:
            self.publicKey = file.readline().strip()
            self.privateKey = file.readline().strip().encode()
            
        self.name = "GM"
        self.taxRate = 0.0035
        
        self.validSymbols = self.loadSymbols(coins)
    
    def verifyAuth(self):
        self.__privateQuery("balances")
#         print(self.__privateQuery("mytrades", {'symbol' : 'btcusd'}))
        return True
    
    def loadSymbols(self, coins):
        symbols = self.__publicQuery("symbols")
        ret = list()
        # Since gemini symbols follow a pattern, generate from list:
        for s1 in coins:
            for s2 in coins:
                sym = s1.lower() + s2.lower()
                if sym in symbols:
                    ret.append((sym, s1, s2))
                    
#         # To hard check each symbol:
#         for s in symbols:
#             info = self.__publicQuery("symbols/details/{}".format(s))
#             if info.get('base_currency') in coins and info.get('quote_currency') in coins:
#                 ret.append(s)
        return ret
    
    def getTradeRates(self, coins):
        bestTrades = [[None for _ in range(len(coins))] for _ in range(len(coins))]
        
        # Formatted as symbol = (symbol, coin1, coin2)
        for symbol in self.validSymbols:
            ticker = self.__publicQuery("pubticker/{}".format(symbol[0]))
            
            c1 = coins.index(symbol[1])
            c2 = coins.index(symbol[2])
            
            bid = self.__tax(float(ticker.get('bid')))
            if bestTrades[c1][c2] == None or bestTrades[c1][c2] < bid:
                bestTrades[c1][c2] = bid
          
            ask = self.__tax(1/float(ticker.get('ask')))
            if bestTrades[c2][c1] == None or bestTrades[c2][c1] < ask:
                bestTrades[c2][c1] = ask
                
        return bestTrades
    
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
    
    def __tax(self, val):
        return val / (1 + self.taxRate)
        

def nonce():
    return str(int(time.time() * 1000))       
