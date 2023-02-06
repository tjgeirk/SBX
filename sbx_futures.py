import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import time

tf = '5m'
max_leverage = 10
take_profit = 0.02
stop_loss = 0.2
martingale = 0.01

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


def Data(coin, tf=tf):
    ohlcv = exchange.fetch_ohlcv(coin, tf, limit=200)
    dates = np.array([x[0] for x in ohlcv], dtype=np.int64)
    opens = np.array([x[1] for x in ohlcv], dtype=np.float64)
    highs = np.array([x[2] for x in ohlcv], dtype=np.float64)
    lows = np.array([x[3] for x in ohlcv], dtype=np.float64)
    closes = np.array([x[4] for x in ohlcv], dtype=np.float64)
    volumes = np.array([x[5] for x in ohlcv], dtype=np.float64)
    return pd.DataFrame({'date': dates, 'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes})


class Order:
    def __init__(self, coin):
        self.coin = coin
        self.balance = float(exchange.fetch_balance()['USDT']['total'])
        self.lever = min(max_leverage, exchange.load_markets(
                          )[self.coin]['info']['maxLeverage'])
        self.last = float(exchange.fetch_ticker(self.coin)['last'])
        self.q = max([float(self.balance/self.last)*0.01, 1])


    def sell(self, price=None, side=None, qty=None) -> None:
        print('sell', self.coin)
        q = self.q if qty == None else qty
        target = self.last if price == None else price
        try:
            exchange.create_limit_sell_order(self.coin, q, target, {'leverage': self.lever, 'closeOrder': True if side == 'long' else False})
        except ccxt.BaseError as e:
            print(e)
        try:
            exchange.create_stop_limit_order(self.coin, 'buy', q, (target-(target*0.1/self.lever)), (target-(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print(e)

    def buy(self, price=None, side=None, qty=None) -> None:
        print('buy', self.coin)
        q = self.q if qty == None else qty
        target = self.last if price == None else price
        try:
            exchange.create_limit_buy_order(self.coin, q, target, {'leverage': self.lever, 'closeOrder': True if side == 'short' else False})
        except ccxt.BaseError as e:
            print(e)
        try:
            exchange.create_stop_limit_order(self.coin, 'sell', q, (target+(target*0.1/self.lever)), (target+(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print(e)


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'mfi', 'length': 2},
    {'kind': 'adx', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 8},
    {'kind': 'ema', 'close': 'close', 'length': 13},
    {'kind': 'ema', 'close': 'close', 'length': 21},
    {'kind': 'vwma', 'close': 'close', 'length': 200},
])
while True:
    try:
        time.sleep(exchange.rateLimit / 1000)
        markets = exchange.load_markets()
        picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
        picker = sorted(picker, key=lambda y: picker[y], reverse=True)
        positions = [x['symbol'] for x in exchange.fetch_positions()]
        coins = picker[0:5] + positions
        openOrders = exchange.fetch_open_orders()

        for y in [x for x in {x['symbol'] for x in openOrders} if x not in coins]:
            toCancel = [x['id'] for x in openOrders if x['symbol'] == y]
            for id in toCancel:
                try:
                    exchange.cancel_order(id)
                except ccxt.BaseError as e:
                    print(e)

        balance = exchange.fetch_balance()
        if balance['USDT']['free'] > balance['USDT']['total'] / 2:
            for coin in coins:
                time.sleep(exchange.rateLimit / 1000)
                df = Data(coin, tf)
                order = Order(coin)
                df.ta.strategy(SBX)

                ema8 = df['EMA_8'].iloc[-1]
                ema13 = df['EMA_13'].iloc[-1]
                ema21 = df['EMA_21'].iloc[-1]
                vwma200 = df['VWMA_200'].iloc[-1]
                dmp3 = df['DMP_3'].iloc[-1]
                dmn3 = df['DMN_3'].iloc[-1]
                mfi2 = df['MFI_2'].iloc[-1]
                ha_close = df['HA_close'].iloc[-1]
                ha_open = df['HA_open'].iloc[-1]

                if (ema8 > ema13 > ema21 > vwma200) and (dmp3 > dmn3) and (mfi2 >= 50) and (ha_close > ha_open):
                    order.buy()
                if (ema8 < ema13 < ema21 < vwma200) and (dmp3 < dmn3) and (mfi2 <= 50) and (ha_close < ha_open):
                    order.sell()

        for x in exchange.fetch_positions():
            time.sleep(exchange.rateLimit/1000)
            coin = x['symbol']
            order = Order(coin)

            if x['side'] == 'long':
                if x['percentage'] <= -abs(martingale):
                    order.buy(x['markPrice'], x['side'], x['contracts'])
                if x['percentage'] <= -abs(stop_loss):
                    order.sell(x['markPrice'], x['side'], x['contracts'])
                if x['percentage'] >= abs(take_profit):
                    order.sell(x['markPrice'], x['side'], x['contracts'])
                    
            elif x['side'] == 'short':
                if x['percentage'] <= -abs(martingale):
                    order.sell(x['markPrice'], x['side'], x['contracts'])
                if x['percentage'] <= -abs(stop_loss):
                    order.buy(x['markPrice'], x['side'], x['contracts'])
                if x['percentage'] >= abs(take_profit):
                    order.buy(x['markPrice'], x['side'], x['contracts'])

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/1000)
        continue
