import cbpro
from traders.traderType import Frontend

class CoinbaseFrontend(Frontend):

    def __init__(self, filename=None):
        super().__init__("CB", 0.005)
        self.authClient = self.__authenticateFromFile(filename)
        
    def verifyAuth(self):
        acts = self.authClient.get_accounts()
        
        if type(acts) is dict and acts.get('message'):
            print("Authentication returned: ", acts.get('message'))
            return False
            
        return True

    def getTradeRates(self, coins):
        bestTrades = [[None for _ in range(len(coins))] for _ in range(len(coins))]
        products = self.authClient.get_products()
        
#         # Cache any found trades
#         self.tradeCache = list()
        
        for trade in products:
            c1 = trade.get('base_currency')
            c2 = trade.get('quote_currency')
            if c1 in coins and c2 in coins:
#                 self.tradeCache.append(trade)
                c1 = coins.index(c1)
                c2 = coins.index(c2)
                bid, ask = self.__price(trade.get('id'))
                
                if bid != None:
                    bid = self.__tax(bid)
                    if bestTrades[c1][c2] == None or bestTrades[c1][c2] < bid:
                        bestTrades[c1][c2] = bid
                
                if ask != None:
                    ask = self.__tax(1 / ask)
                    if bestTrades[c2][c1] == None or bestTrades[c2][c1] < ask:
                        bestTrades[c2][c1] = ask
        return bestTrades
    
    def __price(self, pid):
        book = self.authClient.get_product_order_book(product_id=pid, level=1)
        
        bidTot = 0
        bidCount = 0
        if book.get('bids') != None:
            for t in book.get('bids'):
                price = float(t[0])
                qty = float(t[1])
                bidTot = bidTot + price * qty 
                bidCount = bidCount + qty

        askTot = 0
        askCount = 0
        if book.get('asks') != None:
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
    
    def __tax(self, val):
        return val / (1 + self.taxRate)
    
    def __authenticateFromFile(self, filename):
        if filename:
            with open(filename, 'r') as file:
                key = file.readline().strip()
                secret = file.readline().strip()
                passphrase = file.readline().strip()
            
            return cbpro.AuthenticatedClient(key, secret, passphrase)
        else:
            return cbpro.PublicClient()
