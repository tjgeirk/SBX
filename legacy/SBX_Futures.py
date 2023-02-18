import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import pandas_ta as ta
import time

tf = '15m'
max_leverage = 5
take_profit = 0.01
stop_loss = 0.5
martingale = 0.01
trade_risk = 0.5

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

indicators = ta.Strategy('Indicators', ta=[
    {'kind': 'ha'},
    {'kind': 'stoch', 'k': 14, 'd': 3, 'smooth_k': 3},
    {'kind': 'ema', 'length': 7, 'close': 'close', 'prefix': 'C'},
    {'kind': 'ema', 'length': 7, 'close': 'open', 'prefix': 'O'},
])


class Order:
    def __init__(self, coin, balance):
        self.coin = coin
        self.balance = balance['free']['USDT']
        self.lever = None
        self.last = None
        self.q = None

    async def get_params(self):
        lever = min(max_leverage, (await exchange.load_markets())[self.coin]['info']['maxLeverage'])
        last = float((await exchange.fetch_ticker(self.coin))['last'])
        q = max([float(self.balance/last)*trade_risk, 1])
        self.lever = lever
        self.last = last
        self.q = q
        return {'balance': self.balance, 'lever': self.lever, 'last': self.last, 'q': self.q}

    async def sell(self, price=None, side=None, qty=None):
        params = await self.get_params()
        size = qty or params['q']
        target = price or params['last']
        try:
            await exchange.create_limit_sell_order(self.coin, size, target, {'leverage': params['lever'], 'closeOrder': side == 'long'})
            print('sell', self.coin)
        except ccxt.BaseError as e:
            print('Issue Selling!', e)

    async def buy(self, price=None, side=None, qty=None):
        params = await self.get_params()
        size = qty or params['q']
        target = price or params['last']
        try:
            await exchange.create_limit_buy_order(self.coin, size, target, {'leverage': params['lever'], 'closeOrder': side == 'short'})
            print('buy', self.coin)
        except ccxt.BaseError as e:
            print('Issue Buying!', e)


async def process_coin(coin, balance):
    await process_open_orders(coin)
    order = Order(coin, balance)
    ohlcv = await exchange.fetch_ohlcv(coin, tf)
    df = pd.DataFrame(
        ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df.ta.strategy(indicators)

    if (df['O_EMA_7'].iloc[-1] > df['C_EMA_7'].iloc[-1]) and (
            df['STOCHk_14_3_3'].iloc[-1] > df['STOCHd_14_3_3'].iloc[-1]):
        await order.buy()
    elif (df['O_EMA_7'].iloc[-1] < df['C_EMA_7'].iloc[-1]) and (
            df['STOCHk_14_3_3'].iloc[-1] < df['STOCHd_14_3_3'].iloc[-1]):
        await order.sell()


async def manage_positions(x, balance):
    order = Order(x['symbol'], balance)
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
    if x['side'] == 'short':
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
            try:
                await exchange.cancel_order(order['id'])
            except ccxt.BaseError:
                pass


async def main():
    while True:
        markets = await exchange.load_markets()
        balance = await exchange.fetch_balance()
        markets = sorted(markets.values(),
                         key=lambda x: x['info']['priceChgPct'], reverse=True)
        positions = await exchange.fetch_positions()
        coins = [x['symbol'] for x in markets][0:5]
        coins += [x['symbol'] for x in positions]
        tasks = [asyncio.create_task(process_coin(
            coin, balance)) for coin in coins]
        tasks += [asyncio.create_task(
            manage_positions(x, balance)) for x in positions]
        await asyncio.gather(*tasks)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

while __name__ == '__main__':
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
