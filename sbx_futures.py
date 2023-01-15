import statistics
import time
import ccxt
import pandas_ta as ta
from matplotlib import pyplot as plt
from pandas import DataFrame as dataframe, Series as series

tf = '5m'
max_leverage = 5

exclude = []
include = []

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})


def Data(coin: str, tf: str = tf) -> dataframe:
    data = {}
    for i, v in enumerate(['date', 'open', 'high', 'low', 'close', 'volume']):
        data[v] = {}
        for n, x in enumerate(exchange.fetch_ohlcv(coin, tf, limit=1000)):
            data[v][n] = x[i]
    return dataframe(data)


class Order:
    def __init__(self, coin: str) -> None:
        self.coin = coin
        self.b = float(exchange.fetch_balance()['USDT']['free'])
        self.ml = exchange.load_markets()[coin]['info']['maxLeverage']
        self.lever = max_leverage if max_leverage < self.ml else self.ml
        self.t = exchange.fetch_ticker(coin)
        self.bid = float(self.t['info']['bestBidPrice'])
        self.ask = float(self.t['info']['bestAskPrice'])
        self.last = float(self.t['last'])
        self.q = (self.b*self.lever/self.last)/2

    def sell(self, price=None) -> None:
        print('sell')
        target = self.last if price == None else price
        exchange.create_limit_sell_order(
            self.coin, self.q, target, {'leverage': self.lever})

    def buy(self, price=None) -> None:
        print('buy')
        target = self.last if price == None else price
        exchange.create_limit_buy_order(
            self.coin, self.q, target, {'leverage': self.lever})


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'mfi', 'length': 5},
    {'kind': 'adx', 'length': 5},
    {'kind': 'ema', 'close': 'close', 'length': 21},
    {'kind': 'ema', 'close': 'close', 'length': 13},
    {'kind': 'ema', 'close': 'close', 'length': 8},
    {'kind': 'ema', 'close': 'close', 'length': 5},
    {'kind': 'ema', 'close': 'close', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 2}])


while True:
    markets = exchange.load_markets()
    picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
    picker = sorted(picker, key=lambda y: picker[y], reverse=True)
    open_positions = [x['symbol'] for x in exchange.fetch_positions()]
    coins = picker[0:5] + open_positions
    try:
        for coin in coins:
            df = Data(coin, tf)
            df.ta.strategy(SBX)
            order = Order(coin)

            if order.q >= 1:

                if (ta.increasing(df['ADX_5'], 21).iloc[-1] == 1 and
                    ta.increasing(df['DMP_5'], 21).iloc[-1] == 1 and
                    df['MFI_5'].iloc[-1] > 50 and
                    df['EMA_8'].iloc[-1] > 
                    df['EMA_13'].iloc[-1] > 
                    df['EMA_21'].iloc[-1]
                    ):
                    order.buy()

                if (ta.increasing(df['ADX_5'], 21).iloc[-1] == 1 and
                    ta.increasing(df['DMN_5'], 21).iloc[-1] == 1 and
                    df['MFI_5'].iloc[-1] < 50 and
                    df['EMA_8'].iloc[-1] < 
                    df['EMA_13'].iloc[-1] < 
                    df['EMA_21'].iloc[-1]
                    ):
                    order.sell()

        for x in exchange.fetch_positions():
            order = Order(x['symbol'])
            df = Data(x['symbol'], tf)
            df.ta.strategy(SBX)

            if (x['side'] == 'long' and 
                df['EMA_2'].iloc[-1] < 
                df['EMA_3'].iloc[-1] <
                df['EMA_5'].iloc[-1]):
                order.sell(x['markPrice'])

            elif (x['side'] == 'short' and
                df['EMA_2'].iloc[-1] >
                df['EMA_3'].iloc[-1] >
                df['EMA_5'].iloc[-1]):
                order.buy(x['markPrice'])

            elif (x['percentage'] >= 0.02 or x['percentage'] <= -0.1):
                (lambda: exchange.create_stop_limit_order(x['symbol'], 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['markPrice'], x['markPrice'], {
                 'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up',  'reduceOnly': True}))()

        open_orders = sorted(exchange.fetch_open_orders(),
                             key=lambda x: x['timestamp'], reverse=True)
        for i, x in enumerate(open_orders):
            if i in range(0, 6) or x['info']['closeOrder'] == True:
                continue
            else:
                exchange.cancel_order(x['id'])

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/1000)
        continue
