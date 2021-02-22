from datetime import datetime
from time import sleep
import traceback
from traders import gemini, coinbase, kraken
from tradeGraph import TradingGraph
import config, util


def auth():
    if config.authenticate:
        cbfile = util.getFile("Please enter the Coinbase auth file... ", "../auth/coinbaseAuth.txt")
        print("Authenticating Coinbase.")
        cb = coinbase.CoinbaseFrontend(cbfile)
        if cb.verifyAuth():
            config.trades.append(cb)
        else:
            print("Coinbase Auth Failed.")
        
        krfile = util.getFile("Please enter the Kraken auth file... ", "../auth/krakenAuth.txt")
        print("Authenticating Kraken.")
        kr = kraken.KrakenFrontend(krfile)
        if kr.verifyAuth():
            config.trades.append(kr)
        else:
            print("Kraken Auth Failed.")
        
        gmfile = util.getFile("Please enter the Gemini auth file... ", "../auth/geminiAuth.txt")
        print("Authenticating Gemini.")
        gm = gemini.GeminiFrontend(config.coins, gmfile)
        if gm.verifyAuth():
            config.trades.append(gm)
        else:
            print("Gemini Auth Failed.")
    else:
        # Public access only
        config.trades = [coinbase.CoinbaseFrontend(), kraken.KrakenFrontend(), gemini.GeminiFrontend(config.coins)]


def main():
    try:
        if config.updateOnEmpty:
            print(datetime.now().strftime("%H:%M"), " Finding arbitrage cycles...")
            
        graph = TradingGraph(config.coins, config.trades)
        cycle = graph.shortestProfitCycle()
        if cycle:
            print(datetime.now().strftime("%H:%M"), " Cycle Found:")
            print(cycle)
            graph.executeCycle(cycle)
                
        elif config.updateOnEmpty:
            print(datetime.now().strftime("%H:%M"), " None.")
    except:
        traceback.print_exc()

auth()
print("Authenticated.")
print()
print("Entering main Loop.")

while True:
    main()
    sleep(60)

# Nice.
