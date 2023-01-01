# Kill Death Ratio

import ccxt
exchange=ccxt.kucoinfutures()

def Kill_Death_Ratio(coin:str='BTC/USDT:USDT'):
    return (exchange.fetch_ticker(coin)['bidVolume']/
            exchange.fetch_ticker(coin)['askVolume'])
