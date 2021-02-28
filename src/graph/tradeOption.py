
from util import synchronized


class TradeOption:

    def __init__(self, rate, size, trader):
        self.rate = rate
        self.size = size
        self.trader = trader
        
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "{:.8f} ({}) Sz {:.6f}".format(self.rate, self.trader.name, self.size)
    
    def __eq__(self, other):
        return other != None and self.rate == other.rate and self.trader == other.trader
    
    def __gt__(self, other):
        return self.rate > other.rate
    
    def __lt__(self, other):
        return self.rate < other.rate
    
class BestTradeHolder:

    def __init__(self):
        self.bestTrade = None

    @synchronized
    def setBest(self, trade):
        self.bestTrade = trade

    @synchronized
    def getBest(self):
        return self.bestTrade

    