from abc import ABC, abstractclassmethod

class Frontend(ABC):
    
    def __init__(self, name, taxRate):
        self.name = name
        self.taxRate = taxRate
        
    @abstractclassmethod
    def verifyAuth(self):
        pass
    
    @abstractclassmethod
    def getTradeRates(self, coins):
        pass
