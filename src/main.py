from datetime import datetime
import traceback, time
from traders import gemini, coinbase, kraken
from graph.cycleGraph import TradingGraph
import config, util

graph = TradingGraph(config.coins)


def auth():
    if config.authenticate:
        cbfile = util.getFile("Please enter the Coinbase auth file... ", "../auth/coinbaseAuth.txt")
        print("Authenticating Coinbase.")
        cb = coinbase.CoinbaseFrontend(config.coins, graph, cbfile)
        if cb.verifyAuth():
            config.trades.append(cb)
        else:
            print("Coinbase Auth Failed.")
        
        krfile = util.getFile("Please enter the Kraken auth file... ", "../auth/krakenAuth.txt")
        print("Authenticating Kraken.")
        kr = kraken.KrakenFrontend(config.coins, graph, krfile)
        if kr.verifyAuth():
            config.trades.append(kr)
        else:
            print("Kraken Auth Failed.")
        
        gmfile = util.getFile("Please enter the Gemini auth file... ", "../auth/geminiAuth.txt")
        print("Authenticating Gemini.")
        gm = gemini.GeminiFrontend(config.coins, graph, gmfile)
        if gm.verifyAuth():
            config.trades.append(gm)
        else:
            print("Gemini Auth Failed.")
    else:
        # Public access only
        config.trades = [coinbase.CoinbaseFrontend(config.coins, graph),
                         kraken.KrakenFrontend(config.coins, graph),
                         gemini.GeminiFrontend(config.coins, graph)]


def main():
    pass
#     try:
#         if config.updateOnEmpty:
#             print(datetime.now().strftime("%H:%M"), " Finding arbitrage cycles...")
#         
#         cycle = graph.shortestProfitCycle()
#         if cycle:
#             print(datetime.now().strftime("%H:%M"), " Cycle Found:")
#             print(cycle)
#             graph.executeCycle(cycle)
#                  
#         elif config.updateOnEmpty:
#             print(datetime.now().strftime("%H:%M"), " None.")
#     except:
#         traceback.print_exc()


auth()

print("Authenticated.")
print("Main Thread Online.", flush=True)

while True:
    time.sleep(5)
    main()

# Nice.

# The next problem:
# We currently have a directed graph with edges of weight and capacity.
# One edge (USD -> BTC) can have multiple edges of weight and size, representing trades
# Right now the graph finds negative cycles by sampling only the best edges/rates and running Bellman-Ford
# When it finds a profitable cycle, it displays the profit + change in values if all trades succeed

# Ideally it should translate to some equilibrium portfolio, like 100% USD (or 50/50 USD/BTC)
# The algorithm should determine if it's still profitable to do so immediately
# Alternatively, it could have some min/max threshold for each coin
# and only execute trades within that threshold.

# Investigate:
# Can you do part of an order? (Are they all-or-nothing?)
# Can you set up an order without proper funds?
# How long/expensive is it to transfer coin between accounts?