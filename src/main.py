from datetime import datetime
import time
import coinbase, kraken
from tradeGraph import TradingGraph

def loop():
    while True:
        main()
        time.sleep(60)


def auth():
    global cb, kr
     
#     cbfile = input("Please enter the coinbase auth file... ")
    cbfile = None
    if not cbfile:
        cbfile = "../auth/coinbaseAuth.txt"
    cb = coinbase.CoinbaseFrontend(cbfile)
    if not cb.verifyAuth():
        return False
    
#     krfile= input("Please enter the kraken auth file... ")
    krfile = None
    if not krfile:
        krfile = "../auth/krakenAuth.txt"
    kr = kraken.KrakenFrontend(krfile)
    if not kr.verifyAuth():
        return False
    
    
    print("\nConfigured. Entering main Loop.")
    return True
    


coins = ["USD", "BTC", "ETH", "LTC", "LINK"]
def main():
    graph = TradingGraph(coins, [cb, kr])
    print(graph.shortestProfitCycle())
    
#     for c in coins:
#         priceCheck(c, cb, kr)
#         priceCheck(c, kr, cb)
#         
# def priceCheck(coin, cb, kr):
#     # cbBid = they buy, we sell coin
#     # cbAsk = they sell, we buy coin
# #     cbBid, cbAsk = cb.price(coin)
# #     krBid, krAsk = kr.price(coin)
#     _, cbAsk = cb.price(coin)
#     krBid, _ = kr.price(coin)
#     
# #     cbBidT =  cb.taxRate * cbBid
#     cbAskT = cb.taxRate * cbAsk
#     krBidT =  kr.taxRate * krBid
# #     krAskT = kr.taxRate * krAsk
#     
#     cbTOkr = krBid - cbAsk
#     cbTOkrT = krBidT + cbAskT
# #     krTOcb = cbBid - krAsk
# #     krTOcbT = cbBidT + krAskT
#     
# #     if cbTOkr > cbTOkrT:
#     if cbTOkr > 0:
#         print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
#         print("Coin {}".format(coin))
#         print("Buy from {} at {}, Sell at {} at {}").format(cb.name, cbAsk, kr.name, krBid)
#         print("{} Tax of {}, {} Tax of {}".format(cb.name, cbAskT, kr.name, krBidT))
#         print("Gross profit of {} minus taxes of {} is profit of {}".format(cbTOkr, cbTOkrT, cbTOkr-cbTOkrT))
#     
def sellTax(sell, tax):
    return float(sell) / (1 + tax)
def buyTax(buy, tax):
    return float(buy) * (1 - tax)
def priceDiff(sell, buy):
    return float(sell) / float(buy)


if auth():
    loop()
else:
    print("Auth Failed.")