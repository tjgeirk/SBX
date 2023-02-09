import ccxt.async_support as ccxt
import asyncio
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


async def get_data(coin, tf=tf):
    ohlcv = await exchange.fetch_ohlcv(coin, tf, limit=500)
    cols = ['dates', 'opens', 'highs', 'lows', 'closes', 'volumes']
    df = pd.DataFrame({c: np.array(
        [x[i] for x in ohlcv], dtype=np.float64 if i > 0 else np.int64) for i, c in enumerate(cols)})
    return df


async def get_order_params(coin):
    balance = float((await exchange.fetch_balance())['USDT']['total'])
    lever = min(max_leverage, (await exchange.load_markets())[coin]['info']['maxLeverage'])
    last = float((await exchange.fetch_ticker(coin))['last'])
    q = max([float(balance/last)*0.01, 1])
    return {'balance': balance, 'lever': lever, 'last': last, 'q': q}


class Order:
    def __init__(self, coin, lever, last, q) -> None:
        self.coin = coin
        self.lever = lever
        self.last = last
        self.q = q

    async def sell(self, price=None, side=None, qty=None) -> None:
        print('sell', self.coin)
        q = self.q if qty == None else qty
        target = self.last if price == None else price

        try:
            await exchange.create_limit_sell_order(self.coin, q, target, {
                'leverage': self.lever, 'closeOrder': True if side == 'long' else False})
        except ccxt.BaseError as e:
            print('Issue Selling!', e)

        try:
            await exchange.create_stop_limit_order(self.coin, 'buy', q, (target-(target*0.1/self.lever)), (target-(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)

    async def buy(self, price=None, side=None, qty=None) -> None:
        print('buy', self.coin)
        q = self.q if qty == None else qty
        target = self.last if price == None else price

        try:
            await exchange.create_limit_buy_order(self.coin, q, target, {'leverage': self.lever, 'closeOrder': True if side == 'short' else False})
        except ccxt.BaseError as e:
            print('Issue Buying!', e)

        try:
            await exchange.create_stop_limit_order(self.coin, 'sell', q, (target+(target*0.1/self.lever)), (target+(target*0.1/self.lever)), {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'ema', 'close': 'HA_close', 'length': 20},
])


async def process_coin(coin: str):
    df = await get_data(coin, tf)
    df.ta.strategy(SBX)
    ema20 = df['EMA_20'].iloc[-1]
    ha_close = df['HA_close'].iloc[-1]
    ha_open = df['HA_open'].iloc[-1]

    params = await get_order_params(coin)
    order = Order(coin, params['lever'], params['last'], params['q'])
    if (ha_open < ha_close) and (ha_close > ema20):
        await order.buy()
    if (ha_open > ha_close) and (ha_close < ema20):
        await order.sell()


async def process_position(x):
    coin = x['symbol']
    df = await get_data(coin, tf)

    params = await get_order_params(coin)
    order = Order(coin, params['lever'], params['last'], params['q'])

    if x['side'] == 'long':
        if x['percentage'] <= -abs(martingale):
            await order.buy(x['markPrice'], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            await order.sell(x['markPrice'], x['side'], x['contracts'])
            print(f"Stop-Loss at {x['percentage']*100}%")
        if x['percentage'] >= abs(take_profit):
            await order.sell(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")

    elif x['side'] == 'short':
        if x['percentage'] <= -abs(martingale):
            await order.sell(x['markPrice'], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            await order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Stop-Loss at {x['percentage']*100}%")
        if x['percentage'] >= abs(take_profit):
            await order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")


async def process_open_orders(coin):
    now = time.time()
    open_orders = await exchange.fetch_open_orders(coin)
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 60:
            await exchange.cancel_order(order['id'])


async def main():
    markets = await exchange.load_markets()
    ordered_coins = sorted(markets.values(), key=lambda x: x['info']['priceChgPct'], reverse=True)
    coins = []
    for x in range(0, 5):
        coins.append(ordered_coins[x]['symbol'])
    tasks = [asyncio.create_task(process_coin(coin)) for coin in coins]
    tasks += [asyncio.create_task(process_position(x)) for x in await exchange.fetch_positions()]
    tasks += [asyncio.create_task(process_open_orders(coin)) for coin in coins]
    await asyncio.gather(*tasks)
    await asyncio.sleep(75)

while __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
        asyncio.run(exchange.close())
