from datetime import datetime
import time
import coinbase, kraken
from tradeGraph import TradingGraph
import gemini


coins = ["USD", "BTC", "ETH", "LTC", "LINK"]
trades = []

def auth():
     
#     cbfile = input("Please enter the Coinbase auth file... ")
    cbfile = None
    if not cbfile:
        cbfile = "../auth/coinbaseAuth.txt"
    cb = coinbase.CoinbaseFrontend(cbfile)
    
    print("Authenticating Coinbase...")
    if cb.verifyAuth():
        trades.append(cb)
    else:
        print("Coinbase Auth Failed.")
    
#     krfile= input("Please enter the Kraken auth file... ")
    krfile = None
    if not krfile:
        krfile = "../auth/krakenAuth.txt"
        
    print("Authenticating Kraken...")
    kr = kraken.KrakenFrontend(krfile)
    if kr.verifyAuth():
        trades.append(kr)
    else:
        print("Kraken Auth Failed.")
    
#     gmfile= input("Please enter the Gemini auth file... ")
    gmfile = None
    if not gmfile:
        gmfile = "../auth/geminiAuth.txt"
        
    print("Authenticating Gemini...")
    gm = gemini.GeminiFrontend(gmfile, coins)
    if gm.verifyAuth():
        trades.append(gm)
    else:
        print("Gemini Auth Failed.")
    


def loop():
    while True:
        main()
        time.sleep(60)

def main():
#         print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    print(datetime.now().strftime("%H:%M"), " Finding profit routes...")
    graph = TradingGraph(coins, trades)
    print(graph.shortestProfitCycle())
    
def sellTax(sell, tax):
    return float(sell) / (1 + tax)
def buyTax(buy, tax):
    return float(buy) * (1 - tax)
def priceDiff(sell, buy):
    return float(sell) / float(buy)


auth()
print("\nConfigured. Entering main Loop.")
loop()



# Nice.