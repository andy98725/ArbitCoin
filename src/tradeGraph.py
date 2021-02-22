
class TradingGraph:
    def __init__(self, coins, traders):
        l = len(coins)
        # Init starting values, beginning with money
        self.nodes = coins
        self.values = [None for _ in range(l)]
        self.values[0] = 1 
        
        # Pull edge weights from traders
        self.edges = [[None for _ in range(l)] for _ in range(l)]
        for t in traders:
            edgeVals = t.getTradeRates(coins)
            
            for c1 in range(l):
                for c2 in range(l):
                    if edgeVals[c1][c2] == None:
                        continue
                    if self.edges[c1][c2] == None or edgeVals[c1][c2] > self.edges[c1][c2].rate:
                        self.edges[c1][c2] = GraphEdge(edgeVals[c1][c2], t)
    
    def shortestProfitCycle(self):
        # TODO
        return None
    
    
    
    def __str__(self):
        return "[Trading Graph\nNodes: {}\nEdges: {}\n]".format(self.nodes, self.edges)
            

    
class GraphEdge:
    def __init__(self, rate, trader):
        self.rate = rate
        self.trader = trader
        