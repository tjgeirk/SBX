# S H L O N G B O T X - v1.1.2
import time
import datetime
import ccxt
from pandas import DataFrame as dataframe
from ta import volume, volatility, trend, momentum

lever = 20
tf = '1m'
coins = ['REN/USDT:USDT']
lots = 1


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


def getData(coin, tf, source='mark'):
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
    try:
        time.sleep(exchange.rateLimit / 1000)
        if period != 0:
            return getData(coin, tf)['open'].iloc[period]
        elif period == 0:
            return getData(coin, tf)['open']
    except Exception as e:
        print(e)


def h(period=0):
    try:
        time.sleep(exchange.rateLimit / 1000)
        if period != 0:
            return getData(coin, tf)['high'].iloc[period]
        elif period == 0:
            return getData(coin, tf)['high']
    except Exception as e:
        print(e)


def l(period=0):
    try:
        time.sleep(exchange.rateLimit / 1000)
        if period != 0:
            return getData(coin, tf)['low'].iloc[period]
        elif period == 0:
            return getData(coin, tf)['low']
    except Exception as e:
        print(e)


def c(period=0):
    try:
        time.sleep(exchange.rateLimit / 1000)
        if period != 0:
            return getData(coin, tf)['close'].iloc[period]
        elif period == 0:
            return getData(coin, tf)['close']
    except Exception as e:
        print(e)


def v(period=0):
    try:
        time.sleep(exchange.rateLimit / 1000)
        if period != 0:
            return getData(coin, tf)['volume'].iloc[period]
        elif period == 0:
            return getData(coin, tf)['volume']
    except Exception as e:
        print(e)


class order:
    def ask(index=0):
        try:
            time.sleep(exchange.rateLimit / 1000)
            return exchange.fetch_order_book(coin)['asks'][index][0]
        except Exception as e:
            print(e)

    def bid(index=0):
        try:
            time.sleep(exchange.rateLimit / 1000)
            return exchange.fetch_order_book(coin)['bids'][index][0]
        except Exception as e:
            print(e)

    def buy(price):
        side = getPositions()[coin]['side']
        try:
            time.sleep(exchange.rateLimit / 1000)
            if side != 'short':
                exchange.create_stop_limit_order(
                    coin, 'buy', lots, price, price, {'leverage': lever, 'stop': 'up'})
            elif side == 'short':
                exchange.cancel_all_orders()
                exchange.cancel_all_orders(coin, {'stop': True})
                exchange.create_stop_limit_order(coin, 'buy', getPositions()[coin]['contracts'], price, price, {
                    'closeOrder': True, 'reduceOnly': True, 'stop': 'down'})
        except Exception as e:
            print(e)

    def sell(price):
        side = getPositions()[coin]['side']
        try:
            time.sleep(exchange.rateLimit / 1000)
            if side != 'long':
                exchange.create_stop_limit_order(
                    coin, 'sell', lots, price, price, {'leverage': lever, 'stop': 'down'})
            elif side == 'long':
                exchange.cancel_all_orders()
                exchange.cancel_all_orders(coin, {'stop': True})
                exchange.create_stop_limit_order(coin, 'sell', getPositions()[coin]['contracts'], price, price, {
                                                 'closeOrder': True, 'reduceOnly': True, 'stop': 'up'})
        except Exception as e:
            print(e)


def Open(period=-1):
    try:
        open = (c(period-1) + o(period-1))/2
        return open
    except Exception as e:
        print(e)


def Close(period=-1):
    try:
        close = (o(period) + h(period) + l(period) + c(period))/4
        return close
    except Exception as e:
        print(e)


def ema(df, window, period=-1):
    return trend.ema_indicator(df, window).iloc[period]


def stoch(period=-1):
    return momentum.stoch(h(), l(), c(), 20, 3).iloc[period]


def signal(period=-1):
    return momentum.stoch_signal(h(), l(), c(), 20, 3).iloc[period]


while True:
    for coin in coins:
        if Close() > ema(c(), 200):
            try:
                if Open(-3) > Close(-3) and Open(-2) > Close(-2) and Open() < Close():
                    while ema(c(), 2) > ema(c(), 3) > ema(c(), 5):
                        order.buy(order.bid())
                if stoch() < 20 and stoch() > signal() and Open() < Close():
                    order.buy(order.bid())
                if getPositions()[coin]['side'] == 'long':
                    if stoch() > 80:
                        order.sell(order.ask())
            except Exception as e:
                print(e)

        elif Close() < ema(c(), 200):
            try:
                if Open(-3) < Close(-3) and Open(-2) < Close(-2) and Open() > Close():
                    while ema(c(), 2) < ema(c(), 3) < ema(c(), 5):
                        order.sell(order.ask())
                if stoch() > 80 and stoch() < signal() and Open() > Close():
                    order.sell(order.ask())
                if getPositions()[coin]['side'] == 'short':
                    if stoch() < 20:
                        order.buy(order.bid())
            except Exception as e:
                print(e)
