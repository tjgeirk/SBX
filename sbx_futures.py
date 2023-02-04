
from pandas import DataFrame as dataframe
from ccxt import kucoinfutures
from time import sleep
import pandas_ta as ta

tf = '5m'

max_leverage = 5
take_profit = 0.01
stop_profit = 0.1
stop_loss = 0.1
martingale_pcnt = 0.01
max_new_positions = 6
risk_pcnt = 0.1

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
        self.balance = float(exchange.fetch_balance()['USDT']['total'])
        self.lever = exchange.load_markets()[coin]['info']['maxLeverage']
        self.lever = max_leverage if max_leverage < self.lever else self.lever
        self.last = float(exchange.fetch_ticker(coin)['last'])
        self.q = float(self.balance/self.last)*risk_pcnt
        self.q = 1 if self.q < 1 else self.q

    def sell(self, price: float = None, side: str = None, qty: int = None) -> None:
        print('sell', self.coin)
        q = self.q if qty == None else qty

        entry_limit = self.last if price == None else price
        exit_limit = (entry_limit-(entry_limit*stop_profit/self.lever))

        try:
            (lambda: exchange.create_limit_sell_order(
                self.coin, q, entry_limit, {'leverage': self.lever, 'closeOrder': True if side == 'long' else False}))()

            if side != 'long':
                (lambda: exchange.create_stop_limit_order(
                    self.coin, 'buy', q, exit_limit, exit_limit, {'closeOrder': True, 'reduceOnly': True}))()

        except Exception as e:
            print(e)
            pass

    def buy(self, price: float = None, side: str = None, qty: int = None) -> None:
        print('buy', self.coin)
        q = self.q if qty == None else qty

        entry_limit = self.last if price == None else price
        exit_limit = (entry_limit+(entry_limit*stop_profit/self.lever))

        try:
            (lambda: exchange.create_limit_buy_order(
                self.coin, q, entry_limit, {'leverage': self.lever, 'closeOrder': True if side == 'short' else False}))()

            if side != 'short':
                (lambda: exchange.create_stop_limit_order(
                    self.coin, 'sell', q, exit_limit, exit_limit, {'closeOrder': True, 'reduceOnly': True}))()

        except Exception as e:
            print(e)
            pass


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'mfi', 'length': 2},
    {'kind': 'adx', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 8},
    {'kind': 'ema', 'close': 'close', 'length': 13},
    {'kind': 'ema', 'close': 'close', 'length': 21},
    {'kind': 'vwma', 'close': 'close', 'length': 50},
    {'kind': 'vwma', 'close': 'close', 'length': 200},
])


def strategy(coin: str, tf: str) -> None:
    try:
        sleep(exchange.rateLimit/1000)
        df = Data(coin, tf)
        order = Order(coin)
        df.ta.strategy(SBX)

        if (
            df['EMA_8'].iloc[-1] > df['EMA_13'].iloc[-1] > df['EMA_21'].iloc[-1] and
            df['HA_close'].iloc[-1] > df['VWMA_50'].iloc[-1] > df['VWMA_200'].iloc[-1] and
            df['DMP_3'].iloc[-1] > df['DMN_3'].iloc[-1] and
            df['MFI_2'].iloc[-1] >= 50 and
            df['HA_close'].iloc[-1] > df['HA_open'].iloc[-1]
        ):
            order.buy()

        elif (
            df['EMA_8'].iloc[-1] < df['EMA_13'].iloc[-1] < df['EMA_21'].iloc[-1] and
            df['HA_close'].iloc[-1] < df['VWMA_50'].iloc[-1] < df['VWMA_200'].iloc[-1] and
            df['DMP_3'].iloc[-1] < df['DMN_3'].iloc[-1] and
            df['MFI_2'].iloc[-1] <= 50 and
            df['HA_close'].iloc[-1] < df['HA_open'].iloc[-1]
        ):
            order.sell()
    except Exception as e:
        print(e)
        pass


def martingale(x: dataframe, tf: str) -> None:
    try:
        sleep(exchange.rateLimit/1000)
        df = Data(x['symbol'], tf)
        order = Order(x['symbol'])
        df.ta.strategy(SBX)

        if x['side'] == 'long':

            if df['HA_close'].iloc[-1] < df['VWMA_50'].iloc[-1] and x['percentage'] > 0:
                order.sell(x['markPrice'], x['side'], x['contracts'])

            if df['HA_close'].iloc[-1] < df['HA_open'].iloc[-1] and x['percentage'] > 0:
                order.sell(x['markPrice'], x['side'], x['contracts'])

            if x['percentage'] <= -abs(martingale_pcnt):
                order.buy(x['markPrice'], x['side'])

            if x['percentage'] <= -abs(stop_loss):
                order.sell(x['markPrice'], x['side'], x['contracts'])

            if x['percentage'] >= abs(take_profit):
                order.sell(x['markPrice'], x['side'], x['contracts'])

        elif x['side'] == 'short':

            if df['HA_close'].iloc[-1] > df['VWMA_50'].iloc[-1] and x['percentage'] > 0:
                order.buy(x['markPrice'], x['side'], x['contracts'])

            if df['HA_close'].iloc[-1] > df['HA_open'].iloc[-1] and x['percentage'] > 0:
                order.buy(x['markPrice'], x['side'], x['contracts'])

            if x['percentage'] <= -abs(martingale_pcnt):
                order.sell(x['markPrice'], x['side'])

            if x['percentage'] <= -abs(stop_loss):
                order.buy(x['markPrice'], x['side'], x['contracts'])

            if x['percentage'] >= abs(take_profit):
                order.buy(x['markPrice'], x['side'], x['contracts'])

    except Exception as e:
        print(e)
        pass


while True:
    try:
        sleep(exchange.rateLimit/1000)
        markets = exchange.load_markets()
        picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
        picker = sorted(picker, key=lambda y: picker[y], reverse=True)
        positions = [x['symbol'] for x in exchange.fetch_positions()]
        coins = picker[0:max_new_positions] + positions

        if exchange.fetch_balance()['USDT']['free'] > exchange.fetch_balance()['USDT']['total']/2:

            for coin in coins:
                print(coin)
                strategy(coin, tf)

        for x in exchange.fetch_positions():
            print(x['symbol'])
            martingale(x, tf)

    except Exception as e:
        print(e)
        sleep(exchange.rateLimit/1000)
        queue = {x['symbol'] for x in exchange.fetch_open_orders()}
        for y in [x for x in queue if x not in coins]:
            queue.remove(y)
        for x in queue:
            y = sorted(exchange.fetch_open_orders(
                x), key=lambda x: x['timestamp'])
            for a, b in enumerate(y):
                if a in range(0, 6):
                    continue
                else:
                    try:
                        exchange.cancel_order(b['id'])
                    except Exception as e:
                        print(e)
                        continue
        continue
