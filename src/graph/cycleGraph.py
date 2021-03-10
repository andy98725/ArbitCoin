from datetime import datetime

import config
from util import synchronized
from graph.graphEdge import GraphEdge
from graph.tradeOption import TradeOption


class TradingGraph:

    def __init__(self, coins):
        self.nodes = coins
        self.edges = [[GraphEdge(c1, c2) for c2 in coins] for c1 in coins]
        self.cycle = None
    
    def addEdge(self, c1, c2, rate, size, trader):
        if not c1 in self.nodes:
            raise Exception("Coin not found: {}".format(c1))
        if not c2 in self.nodes:
            raise Exception("Coin not found: {}".format(c2))
        
        if self.edges[self.nodes.index(c1)][self.nodes.index(c2)].addTrade(TradeOption(rate, size, trader)):
            self.__updateCycles(trader)

    def removeEdge(self, c1, c2, rate, trader):
        if not c1 in self.nodes:
            raise Exception("Coin not found: {}".format(c1))
        if not c2 in self.nodes:
            raise Exception("Coin not found: {}".format(c2))
        
        if self.edges[self.nodes.index(c1)][self.nodes.index(c2)].removeTrade(TradeOption(rate, 0, trader)):
            self.__updateCycles(trader)
    
    @synchronized
    def __updateCycles(self, trader):
        cycle = self.shortestProfitCycle()
        if cycle != None and cycle.profitPerc < config.thresholdPerc:
            cycle = None
        
        if self.cycle != cycle:
            self.cycle = cycle
            print(datetime.now().strftime("%H:%M:%S.%f"), " Cycle Change detected:")
            print(self.cycle)
            print(flush=True)
    
    def shortestProfitCycle(self):
        v = len(self.nodes)
        trades = [[self.edges[i][j].getBest() for j in range(v)] for i in range(v)]
        # It's all ratios, so start out from 1 USD
        sources = [None for _ in range(v)]
        values = [None for _ in range(v)]
        values[0] = 1
        
        # Bellman-Ford the thing
        for _ in range(1, 2 * v):
            for i in range(v):
                for j in range(v):
                    e = trades[i][j]
                    if e == None or values[i] == None:
                        continue
                    
                    weight = values[i] * e.rate
                    if values[j] == None or values[j] < weight:
                        values[j] = weight
                        sources[j] = (i, self.edges[i][j])
            
        # Check if any cycles remain
        for i in range(v):
            for j in range(v):
                e = trades[i][j]
                if e == None or values[i] == None:
                    continue
                
                weight = values[i] * e.rate
                if values[j] == None or values[j] < weight:
                    # CYCLE FOUND. Find path
                    cycle = []
                    while True:
                        (j, edge) = sources[j]
                        # Break on a loop or undefined source
                        if edge in cycle or not sources[j]:
                            index = cycle.index(edge) + 1
                            cycle.insert(0, edge)
                            return Cycle([e.getStatic() for e in cycle[0:index]])
                            break
                        cycle.insert(0, edge)
                        
        return None
    
    def executeCycle(self, cycle):
        # Ensure authorized
        if not config.authenticate:
            return
        if not config.autoTrade:
            prompt = input("Commence Trade? [y/N]").lower()
            if not prompt or prompt[0] != 'y':
                return
        print("TODO")
        # TODO:
        # Execute on trades in cycle as quickly and simultaneously as possible
        
    def __str__(self):
#         return "[Trading Graph\nNodes: {}\nEdges: {}\n]".format(self.nodes, self.edges)
        ret = "[Trading Graph\nNodes: {} Edges: [\n".format(self.nodes)
        for e in self.edges:
            ret += "{},\n".format(e)
        ret += "]"
        return ret


class Cycle:

    def __init__(self, cycleArr):
        firstCoin = None
        
        # Cycle the trade listing until earliest coin is first (typically USD)
        for edge in cycleArr:
            if firstCoin == None or config.coins.index(firstCoin) > config.coins.index(edge.c1):
                firstCoin = edge.c1
        for _ in range(len(cycleArr)):
            if cycleArr[0].c1 == firstCoin:
                break
            cycleArr.append(cycleArr.pop(0))
        self.cycle = cycleArr
    
        # Find max flow/min cut, and calculate profit from that
        maxFlow = cycleArr[0].trade.size
        for edge in cycleArr:
            if maxFlow > edge.trade.size:
                maxFlow = edge.trade.size
            maxFlow = maxFlow * edge.trade.rate
            
        self.profitCoin = firstCoin
        self.profit = maxFlow
        for edge in cycleArr:
            self.profit *= edge.trade.rate
        self.profit -= maxFlow
        self.profitPerc = self.profit / maxFlow * 100
        
        # Find net changes in each coin from executing all trades
        self.changes = dict()
        
        for edge in cycleArr:
            if self.changes.get(edge.c1):
                self.changes[edge.c1] = self.changes[edge.c1] + edge.trade.size
            else:
                self.changes[edge.c1] = edge.trade.size
                
            if self.changes.get(edge.c2):
                self.changes[edge.c2] = self.changes[edge.c2] - edge.trade.size * edge.trade.rate
            else:
                self.changes[edge.c2] = -edge.trade.size * edge.trade.rate
    
    def __eq__(self, other):
        return other != None and self.cycle == other.cycle
            
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(self.cycle) + "\nProfit {}% ({} {}) [Offset {}]".format(self.profitPerc, self.profit, self.profitCoin, self.changes)

