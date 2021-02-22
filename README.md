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

If this proves worthwhile, I will implement automated trading on arbitrage cycles.
Until then, ArbitCoin will solely detect and print said cycles.

The architecture could be better optimized for speed.
Currently, ArbitCoin polls each brokerage once per minute through RESTful interfaces for trade options,
forms a directed graph from the aggregate, and detects any negative cycles.
This could be optimized through Websockets to update existing trade knowledge and update a continuous graph.

Doing so would allow ArbitCoin to go off of real time updates, greatly increasing the response time and detection rate. This would allow it to place an exact start and end on arbitrage cycle windows, and possibly even compete with enterprise software (given enough optimizations and good latency).

# Authentication

An Authentication pattern for each brokerage already exists. If you want to enable this, update config.py.

As of now it has no benefit; if I implemented the automated trading, then it would be necessary.

# Support

If you like this kind of project, you can show your support by (fittingly) donating to my BTC Wallet:
```
1GmX7pchYDgdG7vvdgJ9uurXiFkJwswPnk
```

Thank you! :)
