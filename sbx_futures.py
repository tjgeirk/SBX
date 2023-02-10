import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import pandas_ta as ta
import time


tf = '15m'
max_leverage = 20
take_profit = 0.2
stop_loss = 0.05
martingale = 0.01
trade_risk = 0.1


exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'macd', 'close': 'volume', 'prefix': 'VOL'},
    {'kind': 'macd', 'close': 'close'},
])


async def process_coin(coin: str):
    df = pd.DataFrame(await exchange.fetch_ohlcv(coin, tf), columns=[
                      'timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.ta.strategy(SBX)
    order = Order(coin)
    c = df['HA_close'].iloc[-1]
    o = df['HA_open'].iloc[-1]
    macd = df['MACDh_12_26_9'].iloc[-1]
    macv = df['VOL_MACDh_12_26_9'].iloc[-1]

    if macd > 0 and macv > 0 and c > o:
        await order.buy()
    elif macd < 0 and macv < 0 and c < o:
        await order.sell()


async def process_position(x):
    coin = x['symbol']
    order = Order(coin)
    if x['side'] == 'long':
        if x['percentage'] >= abs(martingale):
            await order.buy(x['markPrice'], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            await order.sell(x['markPrice'], x['side'], x['contracts'])
            print(f"Stop-Loss at {x['percentage']*100}%")
        if x['percentage'] >= abs(take_profit):
            await order.sell(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")

    elif x['side'] == 'short':
        if x['percentage'] >= abs(martingale):
            await order.sell(x['markPrice'], x['side'])
            print(f"Martingale at {x['percentage']*100}%")
        if x['percentage'] <= -abs(stop_loss):
            await order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Stop-Loss at {x['percentage']*100}%")
        if x['percentage'] >= abs(take_profit):
            await order.buy(x['markPrice'], x['side'], x['contracts'])
            print(f"Take-Profit at {x['percentage']*100}%")


class Order:
    def __init__(self, coin):
        self.coin = coin
        self.balance = None
        self.lever = None
        self.last = None
        self.q = None

    async def _params(self):
        balance = float((await exchange.fetch_balance())['USDT']['total'])
        lever = min(max_leverage, (await exchange.load_markets())[self.coin]['info']['maxLeverage'])
        last = float((await exchange.fetch_ticker(self.coin))['last'])
        q = max([float(balance/last)*0.01, 1])
        self.balance = balance
        self.lever = lever
        self.last = last
        self.q = q
        return {'balance': self.balance, 'lever': self.lever, 'last': self.last, 'q': self.q}

    async def _place_stop_limit_order(self, side, size, target):
        try:
            stop_price = target + \
                ((side == 'sell') - (side == 'buy')) * \
                (target * trade_risk / self.lever)
            await exchange.create_stop_limit_order(self.coin, side, size, stop_price, stop_price, {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)

    async def sell(self, price=None, side=None, qty=None):
        await self._params()
        print('sell', self.coin)
        size = qty or self.q
        target = price or self.last

        try:
            await exchange.create_limit_sell_order(self.coin, size, target, {'leverage': self.lever, 'closeOrder': side == 'long'})
        except ccxt.BaseError as e:
            print('Issue Selling!', e)

        await self._place_stop_limit_order('buy', size, target)

    async def buy(self, price=None, side=None, qty=None):
        await self._params()
        print('buy', self.coin)
        size = qty or self.q
        target = price or self.last

        try:
            await exchange.create_limit_buy_order(self.coin, size, target, {'leverage': self.lever, 'closeOrder': side == 'short'})
        except ccxt.BaseError as e:
            print('Issue Buying!', e)

        await self._place_stop_limit_order('sell', size, target)


async def process_open_orders(coin):
    now = time.time()
    open_orders = await exchange.fetch_open_orders(coin)
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 300:
            await exchange.cancel_order(order['id'])


async def main():
    while True:
        markets = await exchange.load_markets()
        ordered_coins = sorted(
            markets.values(), key=lambda x: x['info']['priceChgPct'], reverse=True)
        coins = []
        for x in range(0, 5):
            coins.append(ordered_coins[x]['symbol'])
        tasks = [asyncio.create_task(process_coin(coin)) for coin in coins]
        tasks += [asyncio.create_task(process_position(x)) for x in await exchange.fetch_positions()]
        tasks += [asyncio.create_task(process_open_orders(coin))
                  for coin in coins]
        await asyncio.gather(*tasks)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

while __name__ == '__main__':
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
        continue
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
