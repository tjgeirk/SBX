import concurrent.futures
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
import openai

tf = '5m'
max_leverage = 5
take_profit = 0.01
stop_loss = 0.2
martingale = 0.02

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

# openai.api_key = ''


def Data(coin, tf=tf) -> pd.DataFrame:
    ohlcv = exchange.fetch_ohlcv(coin, tf, limit=500)
    columns = ['dates', 'opens', 'highs', 'lows', 'closes', 'volumes']
    df = pd.DataFrame({})
    for i, v in enumerate(columns):
        df[v] = np.array([x[i] for x in ohlcv],
                         dtype=np.float64 if i > 0 else np.int64)
    return pd.DataFrame(df)


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
    {'kind': 'ema', 'close': 'close', 'length': 2},
    {'kind': 'ema', 'close': 'close', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 4},
    {'kind': 'ema', 'close': 'close', 'length': 200},
])


def process_coin(coin: str) -> None:
    df = Data(coin, tf)
    order = Order(coin)
    df.ta.strategy(SBX)

    ema2 = df['EMA_8'].iloc[-1]
    ema3 = df['EMA_13'].iloc[-1]
    ema5 = df['EMA_21'].iloc[-1]
    ema200 = df['EMA_200'].iloc[-1]
    ha_close = df['HA_close'].iloc[-1]
    ha_open = df['HA_open'].iloc[-1]
    
    # input_text = ''
    # input_text += f"Closes: {df['HA_close']}, Opens: {df['HA_open']}"

    # prompt = (f"Please identify the average number of periods between trend reversals based on these haikin-ashi candles, and return only the number with no additional text:\n\n"
    #           f"{input_text}")
    
    # completions = openai.Completion.create(
    #     engine="text-davinci-002",
    #     prompt=prompt,
    #     max_tokens=1024,
    #     n=1,
    #     stop=None,
    #     temperature=0.5,
    # )
    # interval = completions.choices[0].text.strip()

    # print(interval)

    if (ema8 > ema13 > ema21 > ema200) and (ha_close > ha_open):
        order.buy()
    if (ema8 < ema13 < ema21 < ema200) and (ha_close < ha_open):
        order.sell()




def process_position(x) -> None:
    order = Order(x['symbol'])
    coin = x['symbol']
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


def cancelOrders() -> None:
    orders = exchange.fetch_open_orders()
    most_recent_orders = {}
    for order in orders:
        symbol = order['symbol']
        timestamp = order['timestamp']
        if symbol not in most_recent_orders:
            most_recent_orders[symbol] = (timestamp, order['id'])
        else:
            prev_timestamp, prev_order_id = most_recent_orders[symbol]
            if timestamp > prev_timestamp:
                exchange.cancel_order(prev_order_id)
                most_recent_orders[symbol] = (timestamp, order['id'])
            else:
                exchange.cancel_order(order['id'])

while True:
    try:
        time.sleep(exchange.rateLimit/1000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            markets = exchange.load_markets()
            picker = sorted({x: [markets[x]['info']['priceChgPct']]
                            for x in markets}, key=lambda y: y[1], reverse=True)
            positions = [x['symbol'] for x in exchange.fetch_positions()]
            coins = picker[0:4] + positions

            strat = {executor.submit(process_coin, coin)
                                     : coin for coin in coins}

            pos = {executor.submit(process_position, x)
                                   : x for x in exchange.fetch_positions()}

            for future in concurrent.futures.as_completed(strat):
                continue

            for future in concurrent.futures.as_completed(pos):
                continue

            cancelOrders()

    except Exception as e:
        print(e)
        continue
