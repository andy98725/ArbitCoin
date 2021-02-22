from datetime import datetime
from time import sleep
import coinbase, kraken, gemini
from tradeGraph import TradingGraph

updateOnEmpty = True
coins = ["USD", "BTC", "ETH", "LTC", "LINK", "BCH", "ZEC", "USDC", "XLM", "AAVE"]
trades = []


def auth(full):
    if full:
        cbfile = input("Please enter the Coinbase auth file... ")
        if not cbfile:
            cbfile = "../auth/coinbaseAuth.txt"
        cb = coinbase.CoinbaseFrontend(cbfile)
        
        print("Authenticating Coinbase.")
        if cb.verifyAuth():
            trades.append(cb)
        else:
            print("Coinbase Auth Failed.")
        
        krfile = input("Please enter the Kraken auth file... ")
        if not krfile:
            krfile = "../auth/krakenAuth.txt"
            
        print("Authenticating Kraken.")
        kr = kraken.KrakenFrontend(krfile)
        if kr.verifyAuth():
            trades.append(kr)
        else:
            print("Kraken Auth Failed.")
        
        gmfile = input("Please enter the Gemini auth file... ")
        if not gmfile:
            gmfile = "../auth/geminiAuth.txt"
            
        print("Authenticating Gemini.")
        gm = gemini.GeminiFrontend(coins, gmfile)
        if gm.verifyAuth():
            trades.append(gm)
        else:
            print("Gemini Auth Failed.")
    else:
        trades.append(coinbase.CoinbaseFrontend())
        trades.append(kraken.KrakenFrontend())
        trades.append(gemini.GeminiFrontend(coins))


def main():
    if updateOnEmpty:
        print(datetime.now().strftime("%H:%M"), " Finding arbitrage cycles...")
    graph = TradingGraph(coins, trades)
    cycle = graph.shortestProfitCycle()
    if cycle or updateOnEmpty:
        print(cycle)


auth(False)
print("Authenticated.")
print()
print("Entering main Loop.")

while True:
    main()
    sleep(60)

# Nice.
