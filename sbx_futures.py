import concurrent.futures
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import time


tf = '1m'
max_leverage = 5
take_profit = 0.01
stop_loss = 0.2
martingale = 0.05

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


def get_data(coin, tf=tf):
    ohlcv = exchange.fetch_ohlcv(coin, tf, limit=500)
    cols = ['dates', 'opens', 'highs', 'lows', 'closes', 'volumes']
    df = pd.DataFrame({c: np.array(
        [x[i] for x in ohlcv], dtype=np.float64 if i > 0 else np.int64) for i, c in enumerate(cols)})
    return df


class Order:
    def __init__(self, coin: str) -> None:
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
            exchange.create_limit_sell_order(self.coin, q, target, {
                'leverage': self.lever, 'closeOrder': True if side == 'long' else False})
        except ccxt.BaseError as e:
            print('Issue Selling!', e)

        try:
            exchange.create_stop_limit_order(self.coin, 'buy', q, (target-(
                target*0.1/self.lever)), (target-(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)

    def buy(self, price=None, side=None, qty=None) -> None:
        print('buy', self.coin)
        q = self.q if qty == None else qty
        target = self.last if price == None else price

        try:
            exchange.create_limit_buy_order(self.coin, q, target, {
                'leverage': self.lever, 'closeOrder': True if side == 'short' else False})
        except ccxt.BaseError as e:
            print('Issue Buying!', e)

        try:
            exchange.create_stop_limit_order(self.coin, 'sell', q, (target+(
                target*0.1/self.lever)), (target+(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'ema', 'close': 'HA_open', 'length': 8, 'prefix': 'O'},
    {'kind': 'ema', 'close': 'HA_close', 'length': 8, 'prefix': 'C'},
    {'kind': 'ema', 'close': 'HA_high', 'length': 21, 'prefix': 'H'},
    {'kind': 'ema', 'close': 'HA_low', 'length': 21, 'prefix': 'L'},
])


def process_coin(coin: str):
    df = get_data(coin, tf)
    order = Order(coin)
    df.ta.strategy(SBX)
    
    oma8 = df['O_EMA_8'].iloc[-1]
    cma8 = df['C_EMA_8'].iloc[-1]
    hma21 = df['H_EMA_21'].iloc[-1]
    lma21 = df['L_EMA_21'].iloc[-1]
    
    green = True if df['HA_open'].iloc[-1] > df['HA_close'].iloc[-1] else False
    red   = True if df['HA_open'].iloc[-1] < df['HA_close'].iloc[-1] else False
    
    if (green is True) and (cma8 > oma8) and (cma8 > hma21):
        order.buy()
    if (red is True) and (cma8 < oma8) and (cma8 < lma21):
        order.sell()


def process_position(x):
    order = Order(x['symbol'])
    coin = x['symbol']
    print(coin, "Position")
    df = get_data(coin, tf)

    if x['side'] == 'long':
        if x['percentage'] <= -abs(martingale):
            order.buy(df['lows'].iloc[-1], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            print(f"Stop-Loss at {x['percentage']*100}%")
            order.sell(x['markPrice'], x['side'], x['contracts'])
        if x['percentage'] >= abs(take_profit):
            order.sell(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")

    elif x['side'] == 'short':
        if x['percentage'] <= -abs(martingale):
            order.sell(df['highs'].iloc[-1], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Stop-Loss at {x['percentage']*100}%")
        if x['percentage'] >= abs(take_profit):
            order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")

def process_open_orders(coin):
    now = time.time()
    open_orders = exchange.fetch_open_orders(coin)
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 60:
            exchange.cancel_order(order['id'])

def main():
    markets = exchange.load_markets(True)
    picker = sorted({x: [markets[x]['info']['priceChgPct']] for x in markets}, key=lambda y: y[1], reverse=True)
    coins = picker[0:5]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        cn = {executor.submit(process_coin, coin): coin for coin in coins}
        ps = {executor.submit(process_position, x): x for x in exchange.fetch_positions()}
        cl = {executor.submit(process_open_orders, coin): coin for coin in coins}

        concurrent.futures.wait(cn.keys() | ps.keys() | cl.keys())


while __name__ == '__main__':
    main()
