import ccxt
import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import pandas_ta as ta

indicators = ta.Strategy('Indicators', ta=[
    {'kind': 'ha'},
    {'kind': 'tema', 'length': 50},
    {'kind': 'tema', 'length': 200},
    {'kind': 'macd', 'fast': 8, 'slow': 21, 'signal': 3},
    {'kind': 'macd', 'fast': 8, 'slow': 21, 'signal': 3, 'prefix': 'VOL', 'close': 'volume'}])


async def strategy(exchange, ticker, balance):
    df = pd.DataFrame(await exchange.fetch_ohlcv(ticker, '15m'))
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    df.ta.strategy(indicators)
    print(ticker)
    ema50 = df['TEMA_50'].iloc[-1]
    ema200 = df['TEMA_200'].iloc[-1]
    macv = df['VOL_MACDh_8_21_3'].iloc[-1]
    macd = df['MACDh_8_21_3'].iloc[-1]
    ha_open = df['HA_open'].iloc[-1]
    ha_close = df['HA_close'].iloc[-1]
    close = df['close'].iloc[-1]

    try:
        if (macd > 0) and (macv > 0) and (ema50 > ema200) and (ha_close > ha_open):
            await buy_coin(exchange, ticker, close, balance)
        elif (macd < 0) and (macv < 0) and (ha_close < ha_open):
            await sell_coin(exchange, ticker, close, balance)
    except Exception as e:
        print(e)


async def buy_coin(exchange, ticker, close, balance, quote_ticker='USDT'):
    print(f'BUY {ticker}')
    order = await exchange.create_limit_buy_order(ticker, balance[quote_ticker]['free']/10/close, close, {'timeInForce': 'GTT', 'cancelAfter': 300})
    print(order)


async def sell_coin(exchange, ticker, close, balance, quote_ticker='USDT'):
    print(f'SELL {ticker}')
    order = await exchange.create_limit_sell_order(ticker, balance[ticker.split('/')[0]]['free'], close, {'timeInForce': 'GTT', 'cancelAfter': 300})
    print(order)


async def main():
     async with ccxt.kucoin({
        'apiKey': '',
        'secret': '',
        'password': '',
    }) as exchange:
        while True:
            try:
                balance = await exchange.fetch_balance()
                positions = [x for x in sorted(
                    balance['info']['data'], key=lambda x: x['balance'], reverse=True) if float(x['balance']) > 0]
                tickers = await exchange.fetch_tickers()
                tickers = {x: tickers[x] for x in tickers if 'USDT' in x}
                gainers = sorted(
                    tickers, key=lambda x: tickers[x]['percentage'], reverse=True)[:5]
                await asyncio.gather(*[strategy(exchange, ticker, balance) for ticker in gainers], *[strategy(exchange, ticker, balance) for ticker in [f"{x['currency']}/USDT" for x in positions if x['currency'] != 'USDT']])
            except Exception as e:
                print(e)
                await asyncio.sleep(1)
            await exchange.close()

while __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
