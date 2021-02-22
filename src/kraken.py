import time, base64, hashlib, hmac, json
#import requests
import urllib.request as urllib2


class KrakenFrontend:

    def __init__(self, filename):
        self.domain = "https://api.kraken.com"
        self.privatePath = "/0/private/"
        self.publicPath = "/0/public/"
        
        with open(filename, 'r') as file:
            self.publicKey = file.readline().strip()
            self.privateKey = base64.b64decode(file.readline().strip())
            
        self.name = "KR"
        self.taxRate = 0.0026
        self.coinDict = {'ZUSD': 'USD', 'XXBT': 'BTC', 'XETH': 'ETH', 'XLTC': 'LTC', 'LINK': 'LINK'}
    
    def verifyAuth(self):
        self.__privateQuery("Balance")
        return True
    
    def getTradeRates(self, coins):
        bestTrades = [[None for _ in range(len(coins))] for _ in range(len(coins))]
        products = self.__publicQuery("AssetPairs")
        for name, traits in products.items():
            # Avoid direct trades, which incur a higher fee
            if traits.get('fees')[0][1] / 100 > self.taxRate:
                continue
            c1 = self.coinDict.get(traits.get('base'))
            c2 = self.coinDict.get(traits.get('quote'))
            if c1 in coins and c2 in coins:
                c1 = coins.index(c1)
                c2 = coins.index(c2)
                bid, ask = self.__price(name)
                
                if bid != None:
                    bid = self.__tax(bid)
                    if bestTrades[c1][c2] == None or bestTrades[c1][c2] < bid:
                        bestTrades[c1][c2] = bid
                  
                if ask != None:
                    ask = self.__tax(1 / ask)
                    if bestTrades[c2][c1] == None or bestTrades[c2][c1] < ask:
                        bestTrades[c2][c1] = ask
        return bestTrades
    
    def __price(self, coin):
        book = self.__publicQuery("Depth", "&pair={}&count={}".format(coin, 12)).get(coin)
        bidTot = 0
        bidCount = 0
        for t in book.get('bids'):
            price = float(t[0])
            qty = float(t[1])
            bidTot = bidTot + price * qty 
            bidCount = bidCount + qty

        askTot = 0
        askCount = 0
        for t in book.get('asks'):
            price = float(t[0])
            qty = float(t[1])
            askTot = askTot + price * qty 
            askCount = askCount + qty
        
        if bidCount == 0:
#             raise Exception("No KR Bid orders found")
            bidTot = None
        else:
            bidTot = bidTot / bidCount
        if askCount == 0:
#             raise Exception("No KR Ask orders found")
            askTot = None
        else:
            askTot = askTot / askCount
            
        return bidTot, askTot
        
#     def __privateQuery(self, queryMethod, queryData=""):
#         n = nonce()
#         queryData = (queryData + "&nonce=" + n).encode('utf-8')
#         
#         sha256 = hashlib.sha256(n.encode('utf-8') + queryData).digest()
#         encode = (self.privatePath + queryMethod).encode('utf-8') + sha256
#         hmacsha512 = hmac.new(self.privateKey, encode, hashlib.sha512)
#         
#         request_headers = {
#             'API-Key': self.publicKey,
#             'API_Sign':base64.b64encode(hmacsha512.digest()),
#             'User-Agent':"ArbitCoin"
#         }
#           
#         req = self.domain + self.privatePath + queryMethod
#         response = requests.post(req, headers=request_headers).json()
#         
#         if response.get('error'):
#             raise Exception("ERR: {}\nOn Query:\n{}".format(response.get('error'), req))
#         return response.get('result')
#     
#     def __publicQuery(self, queryMethod, queryData=""):
#         req = self.domain + self.publicPath + queryMethod + '?' + queryData
#         response = requests.get(req).json()
#         
#         if response.get('error'):
#             raise Exception("ERR: {}\nOn Query:\n{}".format(response.get('error'), req))
#         return response.get('result')
        
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
    
    def __tax(self, val):
        return val / (1 + self.taxRate)


def getPrice(bid):
    if bid == None:
        return None
    else:
        return bid[0]


def nonce():
    return str(int(time.time() * 1000))        
