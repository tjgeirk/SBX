import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import pandas_ta as ta
import time


tf = '5m'
max_leverage = 5
take_profit = 0.2
stop_loss = 0.1
martingale = 0.01
trade_risk = 0.25


exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


indicators = ta.Strategy('Indicators', ta=[
    {'kind': 'ha'},
    {'kind': 'ema', 'length': 200, 'close': 'close', 'prefix': 'C'},
    {'kind': 'ema', 'length': 200, 'close': 'open', 'prefix': 'O'},
    {'kind': 'ema', 'length': 8, 'close': 'close', 'prefix': 'C'},
    {'kind': 'ema', 'length': 8, 'close': 'open', 'prefix': 'O'},
])


async def process_coin(coin, positions):
    df = pd.DataFrame(await exchange.fetch_ohlcv(coin, tf), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.ta.strategy(indicators)
    open_ema_short = df['O_EMA_8'].iloc[-1]
    close_ema_short = df['C_EMA_8'].iloc[-1]
    open_ema_long = df['O_EMA_200'].iloc[-1]
    close_ema_long = df['C_EMA_200'].iloc[-1]
    ha_open = df['HA_low'].iloc[-1]
    ha_close = df['HA_high'].iloc[-1]
    order = Order(coin)

    if (open_ema_long < close_ema_long) and (
            open_ema_short > close_ema_short) and (ha_open < ha_close):
        await order.buy()
    elif (open_ema_long > close_ema_long) and (
            open_ema_short < close_ema_short) and (ha_open > ha_close):
        await order.sell()

    for x in positions:
        if x['symbol'] != coin:
            continue
        else:
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
                if x['percentage'] >= 0.02:
                    high_price = df['high'].max()
                    stop_price = high_price - high_price*0.02
                    await order._place_stop_limit_order('sell', x['contracts'], stop_price)

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
                if x['percentage'] >= 0.02:
                    low_price = df['low'].min()
                    stop_price = low_price + low_price*0.02
                    await order._place_stop_limit_order('buy', x['contracts'], stop_price)


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
                (target * martingale / self.lever)
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

    async def buy(self, price=None, side=None, qty=None):
        await self._params()
        print('buy', self.coin)
        size = qty or self.q
        target = price or self.last

        try:
            await exchange.create_limit_buy_order(self.coin, size, target, {'leverage': self.lever, 'closeOrder': side == 'short'})
        except ccxt.BaseError as e:
            print('Issue Buying!', e)


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
        positions = await exchange.fetch_positions()
        coins = set([x['symbol'] for x in ordered_coins]
                    [0:5] + [x['symbol'] for x in positions])
        tasks = [asyncio.create_task(process_coin(
            coin, positions)) for coin in coins]
        await asyncio.gather(*tasks)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

while __name__ == '__main__':
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
