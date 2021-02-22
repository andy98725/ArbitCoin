from datetime import datetime
from time import sleep
import coinbase, kraken, gemini
from tradeGraph import TradingGraph

updateOnEmpty = False
coins = ["USD", "BTC", "ETH", "LTC", "LINK", "BCH", "ZEC", "USDC", "XLM", "AAVE"]
trades = []


def auth():
    cbfile = input("Please enter the Coinbase auth file... ")
#     cbfile = None
    if not cbfile:
        cbfile = "../auth/coinbaseAuth.txt"
    cb = coinbase.CoinbaseFrontend(cbfile)
    
    print("Authenticating Coinbase.")
    if cb.verifyAuth():
        trades.append(cb)
    else:
        print("Coinbase Auth Failed.")
    
    krfile= input("Please enter the Kraken auth file... ")
#     krfile = None
    if not krfile:
        krfile = "../auth/krakenAuth.txt"
        
    print("Authenticating Kraken.")
    kr = kraken.KrakenFrontend(krfile)
    if kr.verifyAuth():
        trades.append(kr)
    else:
        print("Kraken Auth Failed.")
    
    gmfile= input("Please enter the Gemini auth file... ")
#     gmfile = None
    if not gmfile:
        gmfile = "../auth/geminiAuth.txt"
        
    print("Authenticating Gemini.")
    gm = gemini.GeminiFrontend(gmfile, coins)
    if gm.verifyAuth():
        trades.append(gm)
    else:
        print("Gemini Auth Failed.")

def loop():
    while True:
        main()
        sleep(60)

def main():
#         print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    if updateOnEmpty:
        print(datetime.now().strftime("%H:%M"), " Finding arbitrage cycles...")
    graph = TradingGraph(coins, trades)
    cycle = graph.shortestProfitCycle()
    if cycle or updateOnEmpty:
        print(cycle)
    
auth()
print("Authenticated.")
print()
print("Entering main Loop.")
loop()


# Nice.
