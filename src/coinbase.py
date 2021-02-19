import cbpro
from itertools import islice

class CoinbaseFrontend:
    def __init__(self, filename):
        self.authClient = authenticateFromFile(filename)
        self.taxRate = 0.005
    
    def verifyAuth(self):
        acts = self.authClient.get_accounts()
        
        if type(acts) is dict and acts.get('message'):
            print("Authentication returned: ", acts.get('message'))
            return False
            
        return True
    
    def bitcoinPrice(self, maxReqs = 200):
        trades = islice(self.authClient.get_product_trades(product_id="BTC-USD"), maxReqs)
        
        # Find best offers
        lowBuy = None
        highBuy = None
        lowSell = None
        highSell = None
        for t in trades:
            if t.get('side') == 'buy':
                if lowBuy == None or lowBuy.get('price') > t.get('price'):
                    lowBuy = t
                if highBuy == None or highBuy.get('price') < t.get('price'):
                    highBuy = t
            else:
                if lowSell == None or lowSell.get('price') > t.get('price'):
                    lowSell = t
                if highSell == None or highSell.get('price') < t.get('price'):
                    highSell = t
        
        if lowBuy == None or highBuy == None or lowSell == None or highSell == None:
            err = "Missing CB Purchase point: low Buy {}, high Buy {}, low Sell {}, high Sell {}"
            raise Exception(err.format(lowBuy, highBuy, lowSell, highSell))
        
        return getPrice(lowBuy), getPrice(highBuy), getPrice(lowSell), getPrice(highSell)
#         buyString = "Buying at: ("+lowBuy.get('price').strip('0')+" - " + highBuy.get('price').strip('0') + ")"
#         sellString = "Selling at: ("+lowSell.get('price').strip('0')+" - " + highSell.get('price').strip('0') + ")"
#         
#         return buyString + "\n" + sellString
    
        
def getPrice(trade):
    if trade == None:
        return None
    else:
        return trade.get('price').strip('0')
def authenticateFromFile(filename):
    with open(filename, 'r') as file:
        key = file.readline().strip()
        secret = file.readline().strip()
        passphrase = file.readline().strip()
    
    return cbpro.AuthenticatedClient(key,secret, passphrase)