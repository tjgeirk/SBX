import statistics
import time
import ccxt
import pandas_ta as ta
from matplotlib import pyplot as plt
from pandas import DataFrame as dataframe, Series as series

tf = '15m'

max_leverage = 10
picker_override = None
exclude = []
include = []
exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})

no_signal = []


def picker() -> str:
    z = None
    picker = {}
    markets = exchange.load_markets(True)
    for v in markets:
        if v in (no_signal or exclude):
            continue
        else:
            picker[v] = markets[v]['info']['priceChgPct']
    pick = max(picker.values())
    for i, v in picker.items():
        if pick == v:
            z = i
    return z


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
        self.target_buy = self.last-(self.last*0.05)/self.lever
        self.target_sell = self.last+(self.last*0.05)/self.lever
        self.q = (self.b/self.last)*self.lever

    def sell(self) -> None:
        print('sell')
        exchange.create_limit_sell_order(
            self.coin, self.q, self.last, {'leverage': self.lever})

    def buy(self) -> None:
        print('buy')
        exchange.create_limit_buy_order(
            self.coin, self.q, self.last, {'leverage': self.lever})

    def takeProfits(self) -> None:
        for x in exchange.fetch_positions():
            if x['percentage'] >= 0.05 or x['percentage'] <= -0.25:
                exchange.create_stop_limit_order(self.coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['markPrice'], x['entryPrice'], {
                                                 'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up', 'remark': 'Percentage'})

        open_orders = sorted(exchange.fetch_open_orders(),
                             key=lambda x: x['timestamp'], reverse=True)

        for i, x in enumerate(open_orders):
            if i in range(0, 6):
                continue
            else:
                exchange.cancel_order(x['id'])


no_signal = []


def dropCoin(coin):
    global no_signal
    print(f'Dropping {coin} from trade pairs list.')
    no_signal.append(coin)
    if len(no_signal) >= 10:
        no_signal = []


SBX = ta.Strategy(name="SBX", ta=[
    {"kind": "ha"},
    {"kind": "ema", "close": "HA_close", "length": 20},
    {"kind": "ema", "close": "HA_close", "length": 50},
    {"kind": "ema", "close": "HA_close", "length": 200},
    {"kind": "adx"},
    {"kind": "donchian"},
])

while True:
    try:
        coins = [x['symbol'] for x in exchange.fetch_positions()]
        if picker() not in coins or exclude:
            coins.append(picker())
        for coin in list(set(coins)):
            print(coin)
            df = Data(coin, tf)
            order = Order(coin)

            df.ta.strategy(SBX)

            if order.q >= 1:
                if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1] and df['HA_open'].iloc[-1] < df['HA_close'].iloc[-1]:
                    order.buy()
                if df['EMA_20'].iloc[-1] < df['EMA_50'].iloc[-1] < df['EMA_200'].iloc[-1] and df['HA_open'].iloc[-1] > df['HA_close'].iloc[-1]:
                    order.sell()
                else:
                    dropCoin(coin)
            else:
                for x in exchange.fetch_open_orders():
                    if x['info']['closeOrder'] == False:
                        exchange.cancel_order(x['id'])

            order.takeProfits()

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/1000)
        continue
