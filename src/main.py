from datetime import datetime
import time
import coinbase, kraken

def loop():
    while True:
        main()
        time.sleep(60)


def auth():
    global cb, kr
     
    cbfile = input("Please enter the coinbase auth file... ")
    if not cbfile:
        cbfile = "../auth/coinbaseAuth.txt"
    cb = coinbase.CoinbaseFrontend(cbfile)
    if not cb.verifyAuth():
        return False
    
    krfile= input("Please enter the kraken auth file... ")
    if not krfile:
        krfile = "../auth/krakenAuth.txt"
    kr = kraken.KrakenFrontend(krfile)
    if not kr.verifyAuth():
        return False
    
    
    print("\nConfigured. Entering main Loop.")
    return True
    

triggerThreshold = 1.00
    
def main():
#     print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    print("Checking ...")
    cbLB, cbHB, cbLS, cbHS = cb.bitcoinPrice()
    krLB, krHB, krLS, krHS = kr.bitcoinPrice()
    
    # Factor in 
    cbLST = sellTax(cbLS, cb.taxRate)
    cbHBT = buyTax(cbHB, cb.taxRate)
    krLST = sellTax(krLS, kr.taxRate)
    krHBT = buyTax(krHB, kr.taxRate)

    
    

    CBsKRb = priceDiff(cbLST, krHBT)
    KRsCBb = priceDiff(krLST, cbHBT)
    if CBsKRb >= triggerThreshold:
        print("Buy from CB at {}, Sell at Kraken at{}".format(round(CBsKRb, 5)))
        print("{}% increase".format(round((CBsKRb-1)*100, 3)))
    if KRsCBb >= triggerThreshold:
        print("Buy from Kraken, Sell at CB: {} mult".format(round(KRsCBb, 5)))
        print("{}% increase".format(round((KRsCBb-1)*100, 3)))
    

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