import bisect

from util import synchronized
from graph.tradeOption import BestTradeHolder


class GraphEdge:

    def __init__(self, c1, c2):
        self.c1 = c1
        self.c2 = c2
        self.trades = list()
        self.best = BestTradeHolder()
        
        # TODO replace with get static
    def getStatic(self):
        return StaticEdge(self.c1, self.c2, self.getBest())

    def getBest(self):
        return self.best.getBest() 
    
    @synchronized
    def addTrade(self, trade):
        bisect.insort(self.trades, trade)
        
        # Update best
        if self.trades[-1] == trade:
            self.best.setBest(trade)
            return True
        else:
            return False
    
    @synchronized
    def removeTrade(self, trade):
        tradeI = bisect.bisect_left(self.trades, trade)
        # Gemini can process a remove trade that it hasn't seen
        l = len(self.trades)
        if tradeI < l and self.trades[tradeI] == trade:
            del self.trades[tradeI]
        
        # Update best
        if l - 1 == 0:
            self.best.setBest(None)
            return True
        elif l - 1 == tradeI:  # Deleted max value
            self.best.setBest(self.trades[-1])
            return True
        else:
            return False


class StaticEdge: 

    def __init__(self, c1, c2, trade): 
        self.c1 = c1
        self.c2 = c2
        self.trade = trade

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "{}->{}: [{}]".format(self.c1, self.c2, self.trade)

    def __eq__(self, other):
        return other != None and self.trade == other.trade
