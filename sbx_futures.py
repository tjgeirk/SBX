# SBX v1.2.1
import time
import ccxt
from statistics import mean, median, mode
from ta import trend, momentum, volatility, volume
from pandas import DataFrame as dataframe, Series as series
from matplotlib import pyplot as plt

tf = '1m'
max_leverage = 5
picker_override = None
lots_override = None
exclude = []

exchange = ccxt.kucoinfutures({
        'apiKey': '',
        'secret': '',
        'password': '',
        'adjustForTimeDifference': True,
    }
)


def picker():
    markets = exchange.load_markets(True)
    picker = {}
    for v in markets:
        if v in exclude:
            continue
        else:
            picker[v] = [markets[v]['info']['priceChgPct']]
    pick = max(picker.values())
    for i, v in picker.items():
        if pick == v:
            coin = i
            return coin


def getPosition(coin):
    time.sleep(exchange.rateLimit / 1000)
    positions = exchange.fetch_positions()
    df = {}
    for col in ['symbol', 'contracts', 'side', 'percentage', 'liquidationPrice']:
        df[col] = 0
        for v in positions:
            if v['symbol'] == coin:
                df[col] = v[col]
    return series(df)


def getData(coin, tf=tf, source='mark'):
    data = {}
    for x in ['open', 'high', 'low', 'close', 'volume']:
        data[x] = {}
    df = dataframe(exchange.fetch_ohlcv(coin, tf, params={'price': source}))
    data['volume'] = df[5]
    data['close'] = (df[1] + df[2] + df[3] + df[4]) / 4
    for i in range(0, len(df)):
        data['open'][i] = (
            ((df[1][i] + df[4][i]) / 2)
            if i == 0
            else ((df[1][i - 1] + df[4][i - 1]) / 2)
        )
        data['high'][i] = max(df[1][i], df[4][i], df[2][i])
        data['low'][i] = min(df[1][i], df[4][i], df[3][i])
    return dataframe(data)

def buyPrice():
    price = None
    while price == None:
        bid_max = max(exchange.fetch_order_book(coin)['bids'][1])
        for x, y in exchange.fetch_order_book(coin)['bids']:
            if y == bid_max:
                price = x
    return price


def sellPrice():
    price = None
    while price == None:
        ask_max = max(exchange.fetch_order_book(coin)['asks'][1])
        for x, y in exchange.fetch_order_book(coin)['asks']:
            if y == ask_max:
                price = x
    return price

data = lambda ohlcv='close': getData(coin, tf)[ohlcv]

ema = lambda window, df='close': trend.ema_indicator(data(df), window).iloc[-1]

while True:
    try:
        exchange.load_markets()
        coin = picker()
        lever = exchange.market(coin)['info']['maxLeverage'] if (exchange.market(coin)['info']['maxLeverage'] < max_leverage) else max_leverage
        balance = exchange.fetch_balance()['USDT']['free'] * 0.1 * lever

        if (data('close').iloc[-1] > ema(200)):
            q = balance / buyPrice() if lots_override == None else lots_override
            (lambda: exchange.create_stop_limit_order(coin, 'buy', q, buyPrice(), buyPrice(), {'leverage':lever, 'stop':'down'}))()
            (lambda: exchange.create_stop_limit_order(coin, 'sell', q, sellPrice(), sellPrice(), {'closeOrder':True, 'stop':'up'}))()
    
        if (data('close').iloc[-1] < ema(200)):
            q = balance / sellPrice() if lots_override == None else lots_override
            (lambda: exchange.create_stop_limit_order(coin, 'sell', q, sellPrice(), sellPrice(), {'leverage':lever, 'stop':'up'}))()
            (lambda: exchange.create_stop_limit_order(coin, 'buy', q, buyPrice(), buyPrice(), {'closeOrder':True, 'stop':'down'}))()

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit / 1000)
        continue
