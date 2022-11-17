import time
import datetime
import ccxt
from pandas import DataFrame as dataframe
from ta import volume, volatility, trend


lever = 20
tf = '1m'
coins = ['ETH/USDT:USDT']
lots = 10


exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


exchange.load_markets()
exchange.cancel_all_orders(params={'stop': True})
exchange.cancel_all_orders()


def getData(coin, tf, source='mark'):
    time.sleep(exchange.rateLimit / 1000)
    data = exchange.fetch_ohlcv(coin, tf, limit=500, params={'price': source})
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

    def ask(index=0):
        return exchange.fetch_order_book(coin)['asks'][index][0]

    def bid(index=0):
        return exchange.fetch_order_book(coin)['bids'][index][0]

    def buy():
        if getPositions()[coin]['side'] != 'short':
            exchange.create_stop_limit_order(
                coin, 'buy', lots,
                order.ask(), order.ask(), {'leverage': lever, 'stop': 'up'})
        elif getPositions()[coin]['side'] == 'short':
            exchange.create_stop_limit_order(coin, 'buy', getPositions()[coin]['contracts'], order.bid(), order.bid(), {
                'closeOrder': True, 'reduceOnly': True, 'stop': 'down'})

    def sell():
        if getPositions()[coin]['side'] != 'long':
            exchange.create_stop_limit_order(
                coin, 'sell', lots, order.bid(), order.bid(), {'leverage': lever, 'stop': 'down'})
        elif getPositions()[coin]['side'] == 'long':
            exchange.create_stop_limit_order(coin, 'sell', getPositions()[coin]['contracts'], order.ask(), order.ask(), {
                'closeOrder': True, 'reduceOnly': True, 'stop': 'up'})


def Open(period=-1):
    o = (getData(coin, tf)['close'].iloc[period-1] +
         getData(coin, tf)['open'].iloc[period-1])/2
    return o


def Close(period=-1):
    c = (getData(coin, tf)['close'].iloc[period] +
         getData(coin, tf)['high'].iloc[period] +
         getData(coin, tf)['low'].iloc[period] +
         getData(coin, tf)['open'].iloc[period])/4
    return c


def High(period=-1):
    h = getData(coin, tf)['high'].iloc[period] if getData(coin, tf)[
        'high'].iloc[period] > Open() else Open()
    return h


def Low(period=-1):
    l = getData(coin, tf)['low'].iloc[period] if getData(coin, tf)[
        'low'].iloc[period] < Open() else Open()
    return l


class dc:
    def hi(period=-1, window=20):
        return volatility.donchian_channel_hband(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], window).iloc[period]

    def md(period=-1, window=20):
        return volatility.donchian_channel_mband(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], window).iloc[period]

    def lo(period=-1, window=20):
        return volatility.donchian_channel_lband(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], window).iloc[period]


def mfi(period=-1, window=3):
    return volume.money_flow_index(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], getData(coin, tf)['volume'], window).iloc[period]


def ema(window=5, ohlcv='close', period=-1):
    return trend.ema_indicator(getData(coin, tf)[ohlcv], window).iloc[period]


def signals(candles=5):
    signals = []
    for x in range(1, int(candles+1)):
        z = 'bar' if x == 1 else 'bars'
        print(f'looking back {x} {z}')
        if dc.hi(-x) > dc.hi(-x-1):
            signals.append('up')
            print(f'possible buy signal on {x}')
        if dc.lo(-x) < dc.lo(-x-1):
            signals.append('down')
            print(f'possible sell signal on {x}')
    return signals


while True:
    time.sleep(exchange.rateLimit/1000)
    for coin in coins:
        try:
            s = signals(3)
            
            print(getPositions())
            if 'down' in s and ema(2, 'open') < ema(2, 'close') and mfi() > 50:
                print('buy signal confirmed - placing order')
                order.buy()

            if 'up' in s and ema(2, 'open') > ema(2, 'close') and mfi() < 50:
                print('sell signal confirmed - placing order')
                order.sell()
                
            s = signals(5)
            
            if 'down' in s and dc.hi() > dc.hi(-2):
                order.buy()
            if 'up' in s and dc.lo() < dc.lo(-2):
                order.sell()

        except Exception as e:
            print(e)
