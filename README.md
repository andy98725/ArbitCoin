# About
ArbitCoin detects any possible arbitrage loops present in cryptocurrency trading websites Coinbase, Kraken, and Gemini.
This is done by connecting to the webhook for each site, applying the site broker fees (hard coded), and forming a Directed Graph with mutliplicative edge weights.
Any negative cycles in the tree would indicate an arbitragre loop.

This project was completed as an introduction to cryptocurrency and arbitrage.
It is not expected to be profitable or particularly effective;
there are enterprise applications that fulfill this same role.

# Usage

Run src/main.py with python3.

Any time an arbitrage cycle appears, changes, or disappears, it outputs the cycle to standard out.

# Targets

ArbitCoin pulls from the sites Coinbase, Kraken, and Gemini for the following  coins:

Bitcoin, Ethereum, Litecoin, Chainlink, Bitcoin Cash, Zcash, USD Coin, Stellar Lumens, and Aave.

It includes US Dollars as well.

This list is easily customisable. More sites may also be added with some coding.

# Further Development

If this proves worthwhile, I will implement automated trading on arbitrage cycles.
Until then, ArbitCoin will solely detect and print said cycles.

The architecture could be better optimized for speed by precalculating minimum necessary values for cycles to appear along each edge.

# Authentication

An Authentication pattern for each brokerage already exists. If you want to enable this, update config.py.

As of now it has no benefit; if I implemented the automated trading, then it would be necessary.

# Support

If you like this kind of project, you can show your support by (fittingly) donating to my BTC Wallet:
```
1GmX7pchYDgdG7vvdgJ9uurXiFkJwswPnk
```

Thank you! :)
