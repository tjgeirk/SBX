import concurrent.futures,ccxt,pandas as pd,pandas_ta as ta,numpy as np,time
tf='5m'
max_leverage=10
take_profit=0.01
stop_loss=0.2
martingale=0.02
exchange=ccxt.kucoinfutures({
    'apiKey':'',
    'secret':'',
    'password':'',
    'adjustForTimeDifference':True
})
def Data(coin,tf=tf):
	ohlcv=exchange.fetch_ohlcv(coin,tf,limit=500);columns=['dates','opens','highs','lows','closes','volumes'];df=pd.DataFrame({})
	for (i,v) in enumerate(columns):df[v]=np.array([x[i]for x in ohlcv],dtype=np.float64 if i>0 else np.int64)
	return pd.DataFrame(df)
class Order:
	def __init__(self,coin):self.coin=coin;self.balance=float(exchange.fetch_balance()['USDT']['total']);self.lever=min(max_leverage,exchange.load_markets()[self.coin]['info']['maxLeverage']);self.last=float(exchange.fetch_ticker(self.coin)['last']);self.q=max([float(self.balance/self.last)*0.01,1])
	def sell(self,price=None,side=None,qty=None):
		print('sell',self.coin);q=self.q if qty==None else qty;target=self.last if price==None else price
		try:exchange.create_limit_sell_order(self.coin,q,target,{'leverage':self.lever,'closeOrder':True if side=='long'else False})
		except ccxt.BaseError as e:print('Issue Selling!',e)
		try:exchange.create_stop_limit_order(self.coin,'buy',q,target-target*0.1/self.lever,target-target*0.1/self.lever,{'closeOrder':True})
		except ccxt.BaseError as e:print('Issue Placing Stop!',e)
	def buy(self,price=None,side=None,qty=None):
		print('buy',self.coin);q=self.q if qty==None else qty;target=self.last if price==None else price
		try:exchange.create_limit_buy_order(self.coin,q,target,{'leverage':self.lever,'closeOrder':True if side=='short'else False})
		except ccxt.BaseError as e:print('Issue Buying!',e)
		try:exchange.create_stop_limit_order(self.coin,'sell',q,target+target*0.1/self.lever,target+target*0.1/self.lever,{'closeOrder':True})
		except ccxt.BaseError as e:print('Issue Placing Stop!',e)
SBX=ta.Strategy(name='SBX',ta=[{'kind':'ha'},{'kind':'mfi','length':2},{'kind':'adx','length':3},{'kind':'ema','close':'close','length':8},{'kind':'ema','close':'close','length':13},{'kind':'ema','close':'close','length':21},{'kind':'ema','close':'close','length':200}])
def process_coin(coin):
	print(coin,'Process');df=Data(coin,tf);order=Order(coin);df.ta.strategy(SBX);ema8=df['EMA_8'].iloc[-1];ema13=df['EMA_13'].iloc[-1];ema21=df['EMA_21'].iloc[-1];ema200=df['EMA_200'].iloc[-1];dmp3=df['DMP_3'].iloc[-1];dmn3=df['DMN_3'].iloc[-1];mfi2=df['MFI_2'].iloc[-1];ha_close=df['HA_close'].iloc[-1];ha_open=df['HA_open'].iloc[-1]
	if ema8>ema13>ema21>ema200 and dmp3>dmn3 and mfi2>=50 and ha_close>ha_open:order.buy()
	if ema8<ema13<ema21<ema200 and dmp3<dmn3 and mfi2<=50 and ha_close<ha_open:order.sell()
def process_position(x):
	order=Order(x['symbol']);coin=x['symbol'];print(coin,'Position')
	if x['side']=='long':
		if x['percentage']<=-abs(martingale):order.buy(x['markPrice'],x['side'],x['contracts'])
		if x['percentage']<=-abs(stop_loss):order.sell(x['markPrice'],x['side'],x['contracts'])
		if x['percentage']>=abs(take_profit):order.sell(x['markPrice'],x['side'],x['contracts'])
	elif x['side']=='short':
		if x['percentage']<=-abs(martingale):order.sell(x['markPrice'],x['side'],x['contracts'])
		if x['percentage']<=-abs(stop_loss):order.buy(x['markPrice'],x['side'],x['contracts'])
		if x['percentage']>=abs(take_profit):order.buy(x['markPrice'],x['side'],x['contracts'])
def cancelOrders():
	openOrders=exchange.fetch_open_orders()
	for z in [x for x in{y['symbol']for y in openOrders}if x not in coins]:
		toCancel=[x['id']for x in openOrders if x['symbol']==z]
		for id in toCancel:
			try:exchange.cancel_order(id)
			except ccxt.BaseError as e:print(e);continue
	return
while True:
	try:
		time.sleep(exchange.rateLimit/1000)
		with concurrent.futures.ThreadPoolExecutor(max_workers=5)as executor:
			markets=exchange.load_markets();picker=sorted({x:[markets[x]['info']['priceChgPct']]for x in markets},key=lambda y:y[1],reverse=True);positions=[x['symbol']for x in exchange.fetch_positions()];coins=picker[0:4]+positions;strat={executor.submit(process_coin,coin):coin for coin in coins};pos={executor.submit(process_position,x):x for x in exchange.fetch_positions()}
			for future in concurrent.futures.as_completed(strat):continue
			for future in concurrent.futures.as_completed(pos):continue
			cancelOrders()
	except Exception as e:print(e);continue
