## "I'm John Bollinger. I'm the guy who created
##  Bollinger Bands, and I am not dead." 
##                        -John Bollinger, 2019
##
##


import ta.volatility as vol
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

PAIRLIST_LENGTH = 10
TIMEFRAME = '15m'
MAX_LEVERAGE = 5
INITIAL_RISK = .5/PAIRLIST_LENGTH


async def get_price_data(exchange, symbol):
    ohlcvs = await exchange.fetch_ohlcv(symbol, TIMEFRAME)
    columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = pd.DataFrame(ohlcvs, columns=columns)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
    df.set_index('Timestamp', inplace=True)
    return df


async def set_targets(exchange, symbol):
    price_data = await get_price_data(exchange, symbol)
    bands = vol.BollingerBands(price_data['Close'], 20, 1)
    price_data['upper_band'] = bands.bollinger_hband()
    price_data['middle_band'] = bands.bollinger_mavg()
    price_data['lower_band'] = bands.bollinger_lband()

    last_close = price_data['Close'].iloc[-1]
    last_middle_band = price_data['middle_band'].iloc[-1]
    last_lower_band = price_data['lower_band'].iloc[-1]
    last_upper_band = price_data['upper_band'].iloc[-1]
    trend_direction = 'Up' if last_close > last_middle_band else 'Down'
    is_trending = abs(
        last_close - last_middle_band) > abs(last_middle_band - last_lower_band)

    if is_trending:
        buy_target, sell_target = (last_middle_band, last_upper_band) if trend_direction == 'Up' else (
            last_lower_band, last_middle_band)
    else:
        buy_target, sell_target = (last_lower_band, last_upper_band)

    return buy_target, sell_target, last_close


async def place_orders(symbol, exchange):
    buy_target, sell_target, last_close = await set_targets(exchange, symbol)
    balance = (await exchange.fetch_balance())['free']['USDT']
    lever = min(exchange.markets[symbol]['info']['maxLeverage'], MAX_LEVERAGE)
    long_qty = max(1, (balance * lever / buy_target) * INITIAL_RISK)
    short_qty = max(1, (balance * lever / sell_target) * INITIAL_RISK)

    if last_close <= buy_target:
        print(f'Placing long order for {symbol} at {buy_target}...')
        await exchange.create_limit_order(
            symbol, 'buy', long_qty, buy_target, {'leverage': lever})

    if last_close >= sell_target:
        print(f'Placing short order for {symbol} at {sell_target}...')
        await exchange.create_limit_order(
            symbol, 'sell', short_qty, sell_target, {'leverage': lever})


async def manage_positions(x, open_orders):
    buy_target, sell_target, _ = await set_targets(
        exchange, x['symbol'])

    if x['symbol'] not in open_orders:
        if x['side'] == 'long':
            print(
                f'{x["symbol"]} target is {sell_target}...')
            await exchange.create_limit_order(
                x['symbol'], 'sell', x['contracts'], sell_target, {'closeOrder': True})
        elif x['side'] == 'short':
            print(
                f'{x["symbol"]} target is {buy_target}...')
            await exchange.create_limit_order(
                x['symbol'], 'buy', x['contracts'], buy_target, {'closeOrder': True})

    if x['side'] == 'long' and sell_target <= x['liquidationPrice']:
        await exchange.create_market_order(x['symbol'], 'sell', x['contracts'], None, {'closeOrder': True})

    elif x['side'] == 'short' and buy_target >= x['liquidationPrice']:
        await exchange.create_market_order(x['symbol'], 'buy', x['contracts'], None, {'closeOrder': True})


async def close_open_orders(x, open_orders):
    now = time.time()
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 15:
            try:
                await exchange.cancel_order(order['id'])
            except ccxt.BaseError:
                pass


async def main():
    while True:
        try:
            markets = await exchange.load_markets()
            balance = await exchange.fetch_balance()
            markets = sorted(markets.values(),
                             key=lambda x: x['info']['priceChgPct'], reverse=True)
            positions = await exchange.fetch_positions()
            top_gainers = [x['symbol'] for x in markets][:PAIRLIST_LENGTH]
            open_positions = [x['symbol'] for x in positions]
            open_orders = [x['symbol'] for x in await exchange.fetch_open_orders(params={'stop': True})]

            tasks = [asyncio.create_task(place_orders(
                coin, exchange)) for coin in top_gainers if coin not in (open_positions or open_orders)]

            tasks += [asyncio.create_task(manage_positions(x, open_orders))
                      for x in positions]

            tasks += [asyncio.create_task(close_open_orders(coin, open_orders)
                                          for coin in open_orders if coin not in (open_positions or top_gainers))]

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
