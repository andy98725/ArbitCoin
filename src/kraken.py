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
            
        self.taxRate = 0.001
    
    def verifyAuth(self):
        balance =  self.__privateQuery("Balance")
        
        if type(balance) is dict and balance.get('error'):
            print("Authentication returned: ", balance.get('error'))
            return False
            
        return True
    
    def bitcoinPrice(self):
        depth = self.__publicQuery("Depth", "&pair=XXBTZUSD").get('result').get('XXBTZUSD')
        
        lowBuy = highBuy = None
        lowSell = highSell = None
        
        for t in depth.get('bids'):
            if lowBuy == None or lowBuy[0] < t[0]:
                lowBuy = t
            if highBuy == None or highBuy[0] < t[0]:
                highBuy = t
        for t in depth.get('asks'):
            if lowSell == None or lowSell[0] < t[0]:
                lowSell = t
            if highSell == None or highSell[0] < t[0]:
                highSell = t
                
        if lowBuy == None or highBuy == None or lowSell == None or highSell == None:
            err = "Missing Kraken Purchase point: low Buy {}, high Buy {}, low Sell {}, high Sell {}"
            raise Exception(err.format(lowBuy, highBuy, lowSell, highSell))

        return getPrice(lowBuy), getPrice(highBuy), getPrice(lowSell), getPrice(highSell)
        
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