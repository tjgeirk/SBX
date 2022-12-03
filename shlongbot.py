# SHLONGBOTX v1.2.1
from ta import volume, trend
import time
import datetime
import ccxt
from ta import trend, volume, volatility, momentum, others
from pandas import DataFrame as dataframe, Series as series

lever = 20
tf = '1m'
coin = 'LUNC/USDT:USDT'
lots = 10


exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


def getPositions():
    try:
        time.sleep(exchange.rateLimit / 1000)
        positions = exchange.fetch_positions()
        df = {}
        df[coin] = {}
        for col in ['contracts', 'side', 'percentage', 'unrealizedPnl', 'liquidationPrice', 'markPrice']:
            df[coin][col] = 0
            for v in positions:
                if v['symbol'] == coin:
                    df[coin][col] = v[col]
            DF = dataframe(df)
        return DF
    except Exception as e:
        print(e)


def getData(coin=coin, tf=tf, source='mark'):
    try:
        time.sleep(exchange.rateLimit / 1000)
        data = exchange.fetch_ohlcv(
            coin, tf, params={'price': source})
        df = {}
        for i, col in enumerate(['date', 'open', 'high', 'low', 'close',
                                'volume']):
            df[col] = []
            for row in data:
                if col == 'date':
                    df[col].append(
                        datetime.datetime.fromtimestamp(row[i] / 1000))
                else:
                    df[col].append(row[i])
            DF = dataframe(df)
        return DF
    except Exception as e:
        print(e)


def o(period=0):
    if period != 0:
        return getData(coin, tf)['open'].iloc[period]
    elif period == 0:
        return getData(coin, tf)['open']


def h(period=0):
    if period != 0:
        return getData(coin, tf)['high'].iloc[period]
    elif period == 0:
        return getData(coin, tf)['high']


def l(period=0):
    if period != 0:
        return getData(coin, tf)['low'].iloc[period]
    elif period == 0:
        return getData(coin, tf)['low']


def c(period=0):
    if period != 0:
        return getData(coin, tf)['close'].iloc[period]
    elif period == 0:
        return getData(coin, tf)['close']


def v(period=0):
    if period != 0:
        return getData(coin, tf)['volume'].iloc[period]
    elif period == 0:
        return getData(coin, tf)['volume']


class order:
    ask = exchange.fetch_order_book(coin)['asks'][0][0]
    bid = exchange.fetch_order_book(coin)['bids'][0][0]

    def buy(price=None):
        side = getPositions()[coin]['side']
        price = order.bid if price == None else price
        try:
            time.sleep(exchange.rateLimit / 1000)
            if side != 'short':
                time.sleep(exchange.rateLimit / 1000)
                exchange.create_limit_order(coin, 'buy', lots, price, {
                    'leverage': lever, 'timeInForce': 'IOC'})
            elif side == 'short':
                time.sleep(exchange.rateLimit / 1000)
                exchange.cancel_all_orders()
                exchange.create_limit_order(coin, 'buy', lots, price, {
                    'closeOrder': True, 'reduceOnly': True, 'timeInForce': 'IOC'})
        except Exception as e:
            print(e)

    def sell(price=None):
        price = order.ask if price == None else price
        side = getPositions()[coin]['side']
        try:
            time.sleep(exchange.rateLimit / 1000)
            if side != 'long':
                time.sleep(exchange.rateLimit / 1000)
                exchange.create_limit_order(
                    coin, 'sell', lots, price, {'leverage': lever, 'timeInForce': 'IOC'})
            elif side == 'long':
                time.sleep(exchange.rateLimit / 1000)
                exchange.cancel_all_orders()
                exchange.create_limit_order(coin, 'sell', lots, price, {
                    'closeOrder': True, 'reduceOnly': True, 'timeInForce': 'IOC'})
        except Exception as e:
            print(e)


def Open(period=-1):
    open = (c(period-1) + o(period-1))/2
    return open


def Close(period=-1):
    close = (o(period) + h(period) + l(period) + c(period))/4
    return close


def ema(window=60, period=-1):
    return trend.ema_indicator(c(), window).iloc[period]


def gator(s=5, m=3, f=2):
    return 1 if ema(f, -1) > ema(m, -2) > ema(s, -3) else -1 if ema(f, -1) < ema(m, -2) < ema(s, -3) else 0


def mfi(window=5, smooth=3, period=-1):
    mf = trend.sma_indicator(volume.money_flow_index(
        h(), l(), c(), v(), window), smooth)
    mfi = mf.iloc[period]
    signal = momentum.kama(mf, smooth).iloc[period]
    return 1 if mfi > signal else -1 if signal > mfi else 0


while True:
    try:
        print(f'MFI: {mfi()}\nGTR: {gator()}')
        r = mfi() + gator()
        if r == 2 and Close() > Open() and Close(-2) > Open(-2):
            print('buy')
            order.buy()
        elif r == -2 and Close() < Open() and Close(-2) < Open(-2):
            print('sell')
            order.sell()
    except Exception as e:
        print(e)
        continue
