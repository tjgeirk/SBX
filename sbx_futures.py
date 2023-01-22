# Note to future self: it's this one! (you can safely ignore if not future self)
#
import pandas_ta as ta
from time import sleep
from ccxt import kucoinfutures
from pandas import DataFrame as dataframe

tf = '5m'
max_leverage = 5

exchange = kucoinfutures({
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
        self.balance = float(exchange.fetch_balance()['USDT']['free'])
        self.lever = exchange.load_markets()[coin]['info']['maxLeverage']
        self.lever = max_leverage if max_leverage < self.lever else self.lever
        self.last = float(exchange.fetch_ticker(coin)['last'])
        self.q = float(self.balance/self.last)*0.05
        self.q = 1 if self.q < 1 else self.q

    def sell(self, price=None) -> None:
        print('sell')
        target = self.last if price == None else price
        (lambda: exchange.create_limit_sell_order(
            self.coin, self.q, target, {'leverage': self.lever}))()
        (lambda: exchange.create_stop_limit_order(
            self.coin, 'buy', self.q, (target-(target*0.1/self.lever)), (target-(target*0.1/self.lever)), {'closeOrder': True}))()

    def buy(self, price=None) -> None:
        print('buy')
        target = self.last if price == None else price
        (lambda: exchange.create_limit_buy_order(
            self.coin, self.q, target, {'leverage': self.lever}))()
        (lambda: exchange.create_stop_limit_order(
            self.coin, 'sell', self.q, (target+(target*0.1/self.lever)), (target+(target*0.1/self.lever)), {'closeOrder': True}))()


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'mfi', 'length': 2},
    {'kind': 'adx', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 20},
    {'kind': 'ema', 'close': 'close', 'length': 50},
    {'kind': 'ema', 'close': 'close', 'length': 200}])

while True:
    markets = exchange.load_markets()
    picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
    picker = sorted(picker, key=lambda y: picker[y], reverse=True)
    coins = picker[0:5] + [x['symbol'] for x in exchange.fetch_positions()]
    try:
        for coin in coins:
            df = Data(coin, tf)
            order = Order(coin)
            df.ta.strategy(SBX)
            orders = exchange.fetch_open_orders(coin)
            if len(orders) >= 3:
                tif = max([x['timestamp'] for x in orders])
                for x in orders:
                    if x['timestamp'] < tif:
                        exchange.cancel_order(x['id'])

            if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]:

                if (
                        df['DMP_3'].iloc[-1] >
                        df['DMN_3'].iloc[-1] and
                        df['MFI_2'].iloc[-1] >= 50 and
                        df['HA_close'].iloc[-1] >
                        df['HA_open'].iloc[-1]):
                    order.buy()

            if df['EMA_20'].iloc[-1] < df['EMA_50'].iloc[-1] < df['EMA_200'].iloc[-1]:

                if (
                        df['DMP_3'].iloc[-1] <
                        df['DMN_3'].iloc[-1] and
                        df['MFI_2'].iloc[-1] <= 50 and
                        df['HA_close'].iloc[-1] <
                        df['HA_open'].iloc[-1]):
                    order.sell()

            for x in exchange.fetch_positions():
                coin = x['symbol']
                order = Order(coin)

                if x['side'] == 'long' and x['percentage'] <= -0.01:
                    order.buy(x['markPrice'])

                if x['side'] == 'short' and x['percentage'] <= -0.01:
                    order.sell(x['markPrice'])

                if x['percentage'] <= -0.05 and x['side'] == 'long':
                    order.buy(x['markPrice'])

                if x['percentage'] <= -0.05 and x['side'] == 'short':
                    order.sell(x['markPrice'])

                if x['percentage'] >= 0.1 and x['side'] == 'long':
                    order.sell(x['markPrice'])

                if x['percentage'] >= 0.1 and x['side'] == 'short':
                    order.buy(x['markPrice'])

    except Exception as e:
        print(e)
        sleep(exchange.rateLimit/1000)
        continue
