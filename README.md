# About
ArbitCoin detects any possible arbitrage loops present in cryptocurrency trading websites Coinbase, Kraken, and Gemini.
This is done by polling the prices for each site, applying the site broker fees (hard coded), and forming a tree with mutliplicative edge weights.
Any negative cycles in the tree would indicate an arbitragre loop.

This project was completed as an introduction and indulgence to cryptocurrency and to arbitrage.
It is not expected to be profitable or particularly effective;
there are enterprise applications that do this same exact task.

# Usage

Run src/main.py with python3.

Once per minute, it prints the status of any arbitrage cycles.

# Targets

ArbitCoin pulls from the sites Coinbase, Kraken, and Gemini for the following  coins:

Bitcoin, Ethereum, Litecoin, Chainlink, Bitcoin Cash, Zcash, USD Coin, Stellar Lumens, and Aave.

It of course includes US Dollars as a 10th node.

This list is easily customisable. The sites are as well, with minor coding to match the API styles of additional sites.

# Further Development

I were to continue with this project, I would start with refactoring the code.
The brokerage frontends should pull from a parent class with methods properly abstracted, such as getting the price of a coin.

The next thing I would do, and will do if this is at all effective, is implement automated trading.
Currently, ArbitCoin only *observes* any cycles; it does nothing to execute on one.
If such a cycle existed, it would lead to easy profit through automatically trading along the cycle.

ArbitCycle already supports API authentication on each of the trading sites, so this would not be a difficult change.

# Authentication

Already implemented is an Authentication pattern for each brokerage. This is disabled by default.
Enabling it is simply changing a boolean early in main.py.
As of now it has no benefit; if I implemented the trading functionality described above, then it would become necessary..

# Support

If you like this kind of project, you can show your support by (fittingly) donating to my BTC Wallet:
```
1GmX7pchYDgdG7vvdgJ9uurXiFkJwswPnk
```

Thank you! :)
