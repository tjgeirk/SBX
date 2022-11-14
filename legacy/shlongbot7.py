import time
import datetime
from ccxt import kucoinfutures as kcf
from pandas import DataFrame as dataframe
from ta import momentum, trend, volatility, volume

lever = 20
tf = '1m'
coin = 'DOGE/USDT:USDT'
lots = 10


exchange = kcf({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

exchange.load_markets()


def getData(coin, tf):
    time.sleep(exchange.rateLimit / 1000)
    data = exchange.fetch_ohlcv(coin, tf, limit=500)
    df = {}
    for i, col in enumerate(['date', 'open', 'high', 'low', 'close',
                             'volume']):
        df[col] = []
        for row in data:
            if col == 'date':
                df[col].append(datetime.datetime.fromtimestamp(row[i] / 1000))
            else:
                df[col].append(row[i])
        DF = dataframe(df)
    return DF


def getPositions():
    positions = exchange.fetch_positions()
    df = {}
    df[coin] = {}
    for _, col in enumerate(['contracts', 'side', 'percentage', 'unrealizedPnl']):
        df[coin][col] = 0
        for (_, v) in enumerate(positions):
            if v['symbol'] == coin:
                df[coin][col] = v[col]
        DF = dataframe(df)
    return DF


class order:
    def buy():
        bid = exchange.fetch_order_book(coin)['bids'][0][0]
        if getPositions()[coin]['side'] != 'short':
            exchange.create_limit_order(
                coin, 'buy', lots,
                bid, {'leverage': lever})
        elif getPositions()[coin]['side'] == 'short':
            exchange.create_limit_order(coin, 'buy', getPositions()[coin]['contracts'], bid, {
                                        'closeOrder': True, 'reduceOnly': True})

    def sell():
        ask = exchange.fetch_order_book(coin)['asks'][0][0]
        if getPositions()[coin]['side'] != 'long':
            exchange.create_limit_order(
                coin, 'sell', lots, ask, {'leverage': lever})
        elif getPositions()[coin]['side'] == 'long':
            exchange.create_limit_order(coin, 'sell', getPositions()[coin]['contracts'], ask, {
                                        'closeOrder': True, 'reduceOnly': True})


def open(period=-1):
    return (getData(coin, tf)['close'].iloc[period-1] +
            getData(coin, tf)['open'].iloc[period-1])/2


def close(period=-1):
    return (getData(coin, tf)['close'].iloc[period] +
            getData(coin, tf)['high'].iloc[period] +
            getData(coin, tf)['low'].iloc[period] +
            getData(coin, tf)['open'].iloc[period])/4


def mfi(window=14, period=-1):
    return volume.money_flow_index(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], getData(coin, tf)['volume'], window).iloc[period]


def vwap(period=-1):
    return volume.volume_weighted_average_price(
        getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], getData(coin, tf)['volume']).iloc[period]


while True:
    try:
        print(getPositions())
        while close() > vwap() and mfi() > 50 and open() < close():
            print(getPositions())
            order.buy()
            if open() > close() or close() < vwap():
                order.sell()
                break
        while close() < vwap() and mfi() < 50 and open() > close():
            print(getPositions())
            order.sell()
            if open() < close() or close() > vwap():
                order.buy()
                break
    except Exception as e:
        print(e)
