from ta import volatility as vol, trend as tr, momentum as mom
import pandas as pd
import ccxt.async_support as ccxt
import asyncio
import time

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


LOOKBACK = 20
PAIRLIST_LENGTH = 5
TIMEFRAME = '5m'
MAX_LEVERAGE = 5
INITIAL_RISK = 1/PAIRLIST_LENGTH


async def get_price_data(exchange, symbol):
    ohlcvs = await exchange.fetch_ohlcv(symbol, TIMEFRAME)
    columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = pd.DataFrame(ohlcvs, columns=columns)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
    df.set_index('Timestamp', inplace=True)
    return df


async def set_targets(exchange, symbol):
    price_data = await get_price_data(exchange, symbol)
    kc = vol.KeltnerChannel(price_data['High'], price_data['Low'], price_data['Close'], LOOKBACK)
    price_data['upper_band'] = kc.keltner_channel_hband()
    price_data['middle_band'] = kc.keltner_channel_mband()
    price_data['lower_band'] = kc.keltner_channel_lband()
    price_data['ema200'] = tr.ema_indicator(price_data['Close'], 200)

    last_close = price_data['Close'].iloc[-1]
    middle = price_data['middle_band'].iloc[-1]
    lower = price_data['lower_band'].iloc[-1]
    upper = price_data['upper_band'].iloc[-1]
    ema200 = price_data['ema200'].iloc[-1]
    direction = 'Up' if last_close > middle else 'Down'
    is_trending = abs(
        last_close - middle) > abs(middle - lower)

    if is_trending:
        buy_target, sell_target = (middle, upper) if direction == 'Up' else (
            lower, middle)
    else:
        buy_target, sell_target = (lower, upper)

    return buy_target, sell_target, last_close, ema200, 


async def place_orders(symbol, exchange):
    buy_target, sell_target, last_close, ema200, = await set_targets(exchange, symbol)
    balance = (await exchange.fetch_balance())['free']['USDT']
    lever = min(exchange.markets[symbol]['info']['maxLeverage'], MAX_LEVERAGE)
    long_qty = max(1, (balance * lever / buy_target) * INITIAL_RISK)
    short_qty = max(1, (balance * lever / sell_target) * INITIAL_RISK)
    positions = await exchange.fetch_positions()
    orders = await exchange.fetch_open_orders()

    if ema200 <= last_close:

        buy_orders = [x['symbol'] for x in orders if x['side'] == 'buy']
        long_positions = [x['symbol']
                          for x in positions if x['side'] == 'long']

        if symbol not in buy_orders and symbol not in long_positions:

            print(f'Placing long order for {symbol} at {buy_target}...')
            await exchange.create_stop_limit_order(
                symbol, 'buy', long_qty, buy_target, buy_target, {'leverage': lever})

    if ema200 >= last_close:

        sell_orders = [x['symbol'] for x in await exchange.fetch_open_orders() if x['side'] == 'sell']
        short_positions = [x['symbol']
                           for x in positions if x['side'] == 'short']

        if symbol not in sell_orders and symbol not in short_positions:

            print(f'Placing short order for {symbol} at {sell_target}...')
            await exchange.create_stop_limit_order(
                symbol, 'sell', short_qty, sell_target, sell_target, {'leverage': lever})


async def manage_positions(x):
    buy_target, sell_target, last_close, ema200 = await set_targets(
        exchange, x['symbol'])

    orders = await exchange.fetch_open_orders(params={'stop': True})
    orders += await exchange.fetch_open_orders(params={'stop': False})
    lever = min(exchange.markets[x['symbol']]
                ['info']['maxLeverage'], MAX_LEVERAGE)

    if x['side'] == 'long':
        sell_orders = [y['symbol'] for y in orders if y['side'] == 'sell']

        if x['symbol'] not in sell_orders:
            await exchange.create_limit_order(x['symbol'], 'sell',
                                              x['contracts'], sell_target, {'closeOrder': True})


    elif x['side'] == 'short':
        buy_orders = [y['symbol'] for y in orders if y['side'] == 'buy']

        if x['symbol'] not in buy_orders:
            await exchange.create_limit_order(x['symbol'], 'buy',
                                              x['contracts'], buy_target, {'closeOrder': True})


    if x['side'] == 'long' and buy_target <= x['liquidationPrice']:
        await exchange.create_market_order(x['symbol'], 'sell', x['contracts'], None, {'closeOrder': True})

    elif x['side'] == 'short' and sell_target >= x['liquidationPrice']:
        await exchange.create_market_order(x['symbol'], 'buy', x['contracts'], None, {'closeOrder': True})

    for order_id in [y['id'] for y in orders if (time.time() - x['timestamp'] / 1000) > 10]:
        try:
            await exchange.cancel_order(order_id)
        except ccxt.BaseError:
            pass


async def main():
    while True:
        try:
            markets = await exchange.load_markets()
            markets = sorted(markets.values(),
                             key=lambda x: x['info']['priceChgPct'], reverse=True)
            positions = await exchange.fetch_positions()
            top_gainers = [x['symbol'] for x in markets][:PAIRLIST_LENGTH]
            tasks = [asyncio.create_task(place_orders(
                coin, exchange)) for coin in top_gainers]

            tasks += [asyncio.create_task(manage_positions(x))
                      for x in positions]

            await asyncio.gather(*tasks)

        except Exception as e:
            print(e)
            continue

while __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
        continue
