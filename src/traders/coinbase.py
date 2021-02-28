import cbpro, atexit
from traders.traderType import Frontend
from util import synchronized


class CoinbaseFrontend(Frontend):

    def __init__(self, coins, tradeGraph, filename=None):
        super().__init__("CB", 0.005, tradeGraph, coins)
        
        self.authClient = self.__authenticateFromFile(filename)
        self.tradeDict = self.__getTradeDict(coins)
        
        self.websocketClient = CoinbaseWebsocket(self, list(self.tradeDict.keys()))
        self.websocketClient.start()
        atexit.register(self.websocketClient.close)
        
    def verifyAuth(self):
        acts = self.authClient.get_accounts()
        
        if type(acts) is dict and acts.get('message'):
            print("Authentication returned: ", acts.get('message'))
            return False
            
        return True
    
    def __getTradeDict(self, coins):
        tradeDict = dict()
        
        products = self.authClient.get_products()
        for trade in products:
            c1 = trade['base_currency']
            c2 = trade['quote_currency']
            if c1 in coins and c2 in coins:
                tradeDict[trade['id']] = (c1, c2)
        
        return tradeDict
    
    def __authenticateFromFile(self, filename):
        if filename:
            with open(filename, 'r') as file:
                key = file.readline().strip()
                secret = file.readline().strip()
                passphrase = file.readline().strip()
            
            return cbpro.AuthenticatedClient(key, secret, passphrase)
        else:
            return cbpro.PublicClient()
        
        
        # Use this to test cycle detection.
#     def addBidOption(self, pid, rate, size):
#         c1, c2 = self.tradeDict[pid]
#         if c1 == 'BTC' and c2 == 'USD':
#             rate = 100000
#         self.graph.addEdge(c1, c2, rate, size, self)


class CoinbaseWebsocket(cbpro.WebsocketClient):

    def __init__(self, parent, targets):
        super().__init__(url="wss://ws-feed.pro.coinbase.com/", products=targets, channels=["level2"])
        self.parent = parent

    @synchronized
    def on_message(self, msg):
            if msg['type'] == 'snapshot':
                self.__snapshotInit(msg)
            elif msg['type'] == 'l2update':
                self.__processTrade(msg)
            elif msg['type'] == 'subscriptions':
                pass  # Confirmation message
            else:
                raise Exception("Unrecognized Message: {}".format(msg))
            
    def __snapshotInit(self, msg):
        pid = msg['product_id']
        for price, size in msg['asks']:
            self.parent.addAskOption(pid, float(price), float(size))
        for price, size in msg['bids']:
            self.parent.addBidOption(pid, float(price), float(size))
        
    def __processTrade(self, msg):
        pid = msg['product_id']
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
        
    def on_open(self):
        print("Coinbase Websocket Online.", flush=True)
