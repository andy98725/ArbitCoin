from abc import ABC, abstractclassmethod


class Frontend(ABC):
    
    def __init__(self, name, taxRate, tradeGraph, coins):
        self.name = name
        self.taxRate = taxRate
        self.graph = tradeGraph
        
    @abstractclassmethod
    def verifyAuth(self):
        pass
    
    def addBidOption(self, pid, rate, size):
        c1, c2 = self.tradeDict[pid]
        rate = self.__tax(rate)

        self.graph.addEdge(c1, c2, rate, size, self)
        
    def removeBidOption(self, pid, rate):
        c1, c2 = self.tradeDict[pid]
        rate = self.__tax(rate)
        
        self.graph.removeEdge(c1, c2, rate, self)

    # Asks are inverted bids
    def addAskOption(self, pid, rate, size):
        c1, c2 = self.tradeDict[pid]
        rate = self.__tax(1 / rate)
        
        self.graph.addEdge(c2, c1, rate, size, self)

    def removeAskOption(self, pid, rate):
        c1, c2 = self.tradeDict[pid]
        rate = self.__tax(1 / rate)
        
        self.graph.removeEdge(c2, c1, rate, self)
    
    def __tax(self, val):
        return val / (1 + self.taxRate)
    
#     @abstractclassmethod
#     def getTradeRates(self, coins):
#         pass
