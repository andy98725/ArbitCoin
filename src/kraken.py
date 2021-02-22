import time, base64, hashlib, hmac
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
        self.taxRate = 0.001
        self.coinDict = {'btc': 'XXBTZUSD', 'eth' : 'XETHZUSD', 'ltc' : 'XLTCZUSD', 'link' : 'LINKUSD'}
    
    def verifyAuth(self):
        balance =  self.__privateQuery("Balance")
#         print(self.__publicQuery("AssetPairs"))
        
        if type(balance) is dict and balance.get('error'):
            print("Authentication returned: ", balance.get('error'))
            return False
            
        return True
    
    
    def price(self, coin):
        coin = self.coinDict.get(coin)
        book = self.__publicQuery("Depth", "&pair={}".format(coin)).get('result').get(coin)
        
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
            raise Exception("No KR Bid orders found")
        if askCount == 0:
            raise Exception("No KR Ask orders found")
        
        return bidTot/bidCount, askTot/askCount
        
    def __privateQuery(self, queryMethod, queryData = ""):
        n = nonce()
        queryData = queryData + "&nonce="+n
        queryData = queryData.encode('utf-8')
        
        sha256 = hashlib.sha256(n.encode('utf-8') + queryData).digest()
        encode = self.privatePath.encode('utf-8') + queryMethod.encode('utf-8') + sha256
        hmacsha512 = hmac.new(self.privateKey, encode, hashlib.sha512)
        
        urlRequest = urllib2.Request(self.domain + self.privatePath + queryMethod, queryData)
        urlRequest.add_header("API-Key", self.publicKey)
        urlRequest.add_header("API-Sign", base64.b64encode(hmacsha512.digest()))
        urlRequest.add_header("User-Agent", "ArbitCoin")

        
        response = eval(urllib2.urlopen(urlRequest).read().decode())
        if response.get('error'):
            print("ERR: ", response.get('error'))
        return response
    
    def __publicQuery(self, queryMethod, queryData = ""):
        urlRequest = urllib2.Request(self.domain + self.publicPath+ queryMethod + '?' + queryData)
        
        response = urllib2.urlopen(urlRequest).read().decode()
        return eval(response)

def getPrice(bid):
    if bid == None:
        return None
    else:
        return bid[0]

def nonce():
    return str(int(time.time()*1000))        