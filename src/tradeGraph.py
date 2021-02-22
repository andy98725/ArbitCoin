

class TradingGraph:

    def __init__(self, coins, traders):
        l = len(coins)
        self.nodes = coins
        
        # Pull edge weights from traders
        self.edges = [[None for _ in range(l)] for _ in range(l)]
        for t in traders:
            edgeVals = t.getTradeRates(coins)
            
            for c1 in range(l):
                for c2 in range(l):
                    if edgeVals[c1][c2] == None:
                        continue
                    if self.edges[c1][c2] == None or edgeVals[c1][c2] > self.edges[c1][c2].rate:
                        self.edges[c1][c2] = GraphEdge(edgeVals[c1][c2], t, coins[c1], coins[c2])
    
    def shortestProfitCycle(self):
        v = len(self.nodes)
        # It's all ratios, so start out from 1 USD
        sources = [None for _ in range(v)]
        values = [None for _ in range(v)]
        values[0] = 1
        
        # Bellman-Ford the thing
        for _ in range(1, 2):
            for i in range(v):
                for j in range(v):
                    e = self.edges[i][j]
                    if e == None or values[i] == None:
                        continue
                    
                    weight = values[i] * e.rate
                    if values[j] == None or values[j] < weight:
                        values[j] = weight
                        sources[j] = (i, e)
            
#         print(self)
#         print("Res :")
#         print([i for i in range(v)])
#         print(values)
#         print(sources)

        # Check if any cycles remain
        for i in range(v):
            for j in range(v):
                e = self.edges[i][j]
                if e == None or values[i] == None:
                    continue
                
                weight = values[i] * e.rate
                if values[j] == None or values[j] < weight:
                    # CYCLE FOUND. Find path
                    cycle = []
                    while True:
                        (j, edge) = sources[j]
                        if edge in cycle:
                            index = cycle.index(edge)+1
                            cycle.insert(0, edge)
                            return cycle[0:index]
                            break
                        cycle.insert(0, edge)
                        
        return None
    
    def __str__(self):
#         return "[Trading Graph\nNodes: {}\nEdges: {}\n]".format(self.nodes, self.edges)
        ret = "[Trading Graph\nNodes: {} Edges: [\n".format(self.nodes)
        for e in self.edges:
            ret += "{},\n".format(e)
        ret += "]"
        return ret

    
class GraphEdge:

    def __init__(self, rate, trader, c1, c2):
        self.rate = rate
        self.trader = trader
        self.c1 = c1
        self.c2 = c2
        
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "{} {}->{}: {}".format(self.trader.name, self.c1, self.c2, self.rate)
        
