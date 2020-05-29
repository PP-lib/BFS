# 【BFS-X】ポジションを自炊して高速に売買を行うbitFlyerでの高速botフレームワーク(mmbotと高速スキャルピングbotのサンプルロジック付属)


---
## ４．クラスの中で使用できるメンバ変数
---

BFS-Xでは、ユーザーがロジックを記載したクラス(MyStrategy)はベースとなるロジッククラスを継承する形で記載することで、事前に用意されたクラスメンバ変数を利用できます。これらの変数を参照することで売買判断などを行います。
### ■ メンバ変数詳細
#### ●　self._strategy_config
> この変数ではロジックパラメータファイル(yamlファイル）で指定したparameters以下にアクセスできます

例えばyamlファイルに
```python
parameters:
 mfi_period : 50
 mfi_limit : 15
```
の様に記載されていた場合、self._strategy_config[`'mfi_period'`]には50が入っていて、self._strategy_config[`'mfi_limit'`]には15が入っています。

> [Tips]  
パラメータファイルは稼働中でも書き換え可能で、ファイルスタンプの変更を検知して自動的に再読み込みが行われます。パラメータを変えてみてパラメータの変化によるbotの挙動の変化を確認することが出来て便利ですので、変更する可能性のあるパラメータは出来るだけロジックパラメータファイル(yamlファイル）に記載してself._strategy_configから呼び出すようにしておきましょう。


#### ●　self.open
> 生成された自炊ローソクの始値価格のリストが入っています。確定足のみで構成されており、self.open[-1]が直近の確定足の始値価格です。

使用例
```python
# talibを用いてemaを計算
o = np.array(self.open)
ema = talib.EMA(o, timeperiod=self._strategy_config['period'])
```


#### ●　self.high
> 生成された自炊ローソクの高値価格のリストが入っています。確定足のみで構成されており、self.high[-1]が直近の確定足の高値価格です。

使用例
```python
# talibを用いてemaを計算
h = np.array(self.high)
ema = talib.EMA(h, timeperiod=self._strategy_config['period'])
```


#### ●　self.low
> 生成された自炊ローソクの安値価格のリストが入っています。確定足のみで構成されており、self.low[-1]が直近の確定足の安値価格です。

使用例
```python
# talibを用いてemaを計算
l = np.array(self.low)
ema = talib.EMA(l, timeperiod=self._strategy_config['period'])
```


#### ●　self.close
> 生成された自炊ローソクの終値価格のリストが入っています。確定足のみで構成されており、self.close[-1]が直近の確定足の終値価格です。

使用例
```python
# talibを用いてemaを計算
c = np.array(self.close)
ema = talib.EMA(c, timeperiod=self._strategy_config['period'])
```


#### ●　self.volume
> 生成された自炊ローソクの取引高のリストが入っています。確定足のみで構成されており、self.volume[-1]が直近の確定足の取引高です。


#### ●　self.buy_volume
> 生成された自炊ローソクの取引高のうち買いでの取引高のリストが入っています。確定足のみで構成されており、self.buy_volume[-1]が直近の確定足の買いでの取引高です。


#### ●　self.sell_volume
> 生成された自炊ローソクの取引高のうち売りでの取引高のリストが入っています。確定足のみで構成されており、self.sell_volume[-1]が直近の確定足の売りでの取引高です。


#### ●　self.count
> 生成された自炊ローソクに含まれる約定数のリストが入っています。確定足のみで構成されており、self.count[-1]が直近の確定ローソク足に含まれるの約定数です。


#### ●　self.buy_count
> 生成された自炊ローソクに含まれる買い約定数のリストが入っています。確定足のみで構成されており、self.buy_count[-1]が直近の確定ローソク足に含まれるの買いの約定数です。


#### ●　self.sell_count
> 生成された自炊ローソクに含まれる買い約定数のリストが入っています。確定足のみで構成されており、self.sell_count[-1]が直近の確定ローソク足に含まれるの売りの約定数です。


#### ●　self.total_value
> 生成された自炊ローソクに含まれる取引高x価格（総取引額）のリストが入っています。確定足のみで構成されており、self.total_value[-1]が直近の確定ローソク足に含まれるの総取引額です。


#### ●　self.current_candle
> 未確定足のデータがdict形式で格納されています。

> [Tips]   
ロジックパラメータファイルの`logic_loop_period`を`timescale`よりも小さな数値にした場合、ローソク足が確定したタイミング以外でも`logic_loop_period`秒間隔で`logic()`関数が呼び出され、未確定足の値によって売買判断を行うロジックを作ることが出来ます。

データ例
```
{'exec_date': datetime.datetime(2020, 1, 6, 17, 4, 24, 583899), 'open': 827501, 'high': 827638, 'low': 827424, 'close': 827532, 'volume': 16.70524989999998, 'buy': 13.518446249999986, 'sell': 3.186803649999997, 'count': 304, 'count_buy': 183, 'count_sell': 121, 'total_value': 13823854.021870475}
```

使用例
```python
# 未確定足のデータを最後に追加して指数を計算
h = np.append( np.array(self.high),self.current_candle['high'] )
l = np.append( np.array(self.low),self.current_candle['low'] )
c = np.append( np.array(self.close),self.current_candle['close'] )
v = np.append( np.array(self.volume),self.current_candle['volume'] )
mfi = ta.MFI(h, l, c, v, self._strategy_config['mfi_period'])
```


#### ●　self.candle_date
> 生成された自炊ローソクの確定しているローソク足の時刻(`timestamp`)が入っています。  

mmbotモード/秒スキャモード/スイングモードのいずれでもパラメータファイル(yamlファイル）の中で指定される`timescale`が0以外の場合には使用できます。

> [Tips]   
ロジックパラメータファイルの`logic_loop_period`を`timescale`よりも小さな数値にした場合、ローソク足が確定したタイミング以外でも`logic_loop_period`秒間隔で`logic()`関数が呼び出されますが、self.candle_dateが前回と変わっているかどうかでローソク足が更新されて呼び出されたかどうかが判断できます。


#### ●　self.candle_date_list
> 確定ローソク足の時間列リストが入っています。


#### ●　self.exec_date
> 確定していない足に含まれている最新の約定時刻が入っています。


#### ●　self.execution_timestamp
> 約定履歴の最新の配信時刻が入っています。  
下記のようなコードで、約定履歴受信から実際の売買までどの程度の時間で行えたかなどご自身のロジックの速度評価が可能です。
```python
self._logger.info( "order time : {:.2f}msec".format(
    (time.time()-self.execution_timestamp)*1000) )
```


#### ●　self.board_timestamp
> 最後に板情報更新を受信した際のタイムスタンプが入っています。  


#### ●　self.from_lastcandle_update
> 現在のローソク足になってから何秒たっているかの数値です。

次のローソクが更新する少し前に取引するなどのロジックに使う事が出来るでしょう。


#### ●　self.product
> 取引対象の通貨 ( 'FX_BTC_JPY' / 'BTC_JPY' / 'BTCJPY29MAR2019' など) ```trade.yaml```で指定した```product```が取得できます。

#### ●　self._minimum_order_size
> 最小発注数量。FXBTCJPYの場合には0.01、BTCJPYの場合には0.001です。

参考URL
https://bitflyer.com/ja-jp/faq/4-27


#### ●　self.current_pos
> 現在保有しているポジションです。  
ポジションは自炊管理して計算されたものですので、何度参照してもAPIアクセスは発生しません。売り建てポジの場合には数値はマイナスとなります。

使用例
```python
lotsize = self._strategy_config['lotsize']
# 現在ポジをプラスしてドテンロング
if fLong and lotsize-self.current_pos >= self._minimum_order_size :
    self._market_buy( size = lotsize-self.current_pos )
# 現在ポジをプラスしてドテンショート
if fShort and lotsize+self.current_pos >= self._minimum_order_size :
    self._market_sell( size = lotsize+self.current_pos )    
```

#### ●　self.current_average
> 現在保有しているポジションの平均価格です。


#### ●　self.current_profit
> 現在の算出利益です。（0:00に一度リセットされますので0:00からの利益です）


#### ●　self.current_profit_unreal
> 現在保有しているポジションの含み損益です。


#### ●　self.current_fixed_profit
> 現在の確定損益です。


#### ●　self.ltp
> 現在のLTP価格です(trade.yamlファイルの中のproductで指定された取引所のLTP価格です)


#### ●　self.best_ask
> 現在のbest_ask価格です(配信された約定履歴の最後のBUY価格をbest_askとしています)


#### ●　self.best_bid
> 現在のbest_bid価格です(配信された約定履歴の最後のSELL価格をbest_bidとしています)


#### ●　self.mid_price
> 現在のmid_priceを取得できます。RealtimeAPI経由で板情報が配信される際に['mid_price']で取得された値です。


#### ●　self.spotprice
> 現在の現物価格(BTCJPY)です。乖離率(SFD値)を算出するためにお使いいただけます。格納されている価格はRealtimeAPIで最後に受信した`LTP`です。


#### ●　self.spotprice_exec
> 現物(BTCJPY)の最終約定価格です。格納されている価格はRealtimeAPIで最後に受信した約定履歴の一番最後の約定価格です。  

> [Hint]   
RealtimeAPIの`lightning_ticker_BTC_JPY`を受信するタイミングと、`lightning_executions_BTC_JPY`を受信するタイミングが微妙に異なるため、一瞬ですが、`self.spotprice`と`self.spotprice_exec`とは異なる値を持つことがあります。

#### ●　self.sfd
> 現在の乖離率(SFD値)です


#### ●　self.sfd_commission
> SFDで徴収・付与された損益  
`self.current_profit`で得られるポジション損益とは別にSFDにて支払い・受け取りを行った額が確認できます。

> [Hint]   
ポジショングラフに表示される損益のグラフは、ポジション損益とSFD損益が合算されたものがプロットされ、損益グラフに表示される損益のグラフはポジション損益とSFD損益がそれぞれ別にプロットされます。

<img src="images/sfd_position.png" width="55%">
<img src="images/sfd_profit.png" width="55%">


#### ●　self.cryptowatch_candle
> Cryptowatchから取得したデータがpandas形式で収納されています。Cryptowatchからの取得は定期的に自動で行われています。  
足の長さ（分）はパラメータファイル(yaml)のcryptowatch_candleで指定します。open(始値) , high(高値) , low(安値) , close(終値) , volume(出来高) が取得できます。サンプルロジックst_ema_candleやdisp_candleを参考にしてみてください。

データ例
```python
                       open    high     low   close        volume
date                                                             
2019-12-25 02:00:00  807201  808550  792739  796912   7582.944893
2019-12-25 04:00:00  798876  805696  794336  799601   5290.204502
2019-12-25 06:00:00  799601  804050  798432  801888   3512.811112
2019-12-25 08:00:00  801846  805000  798180  800992   3758.826602
2019-12-25 10:00:00  800740  803093  799000  801387   3460.671240
2019-12-25 12:00:00  801418  803235  799300  801764   3753.378133
2019-12-25 14:00:00  801738  802590  801079  801945    281.920158
```


#### ●　self.board_age
> 前回の板情報スナップショットから何回更新されたかを取得できます。  
> self.board_ageが0の時には、板スナップショットが更新された直後です。例えば、板情報の差分更新時には取引せず、板スナップショットが更新された時だけ取引するようなロジックを作成する際に使用できます。


#### ●　self.ordered_list
> 現在の発注済み（子注文）の未約定リストが取得できます。(dict型のリスト形式)  
> 特殊注文(親注文)のトリガーによって発生した子注文も含まれます

|キー|型|説明|
|---|---|---|
|id|string|child_acceptance_idが入っています|
|child_order_type|string|```'LIMIT'``` (```'MARKET'```はすぐに処理されるため基本的にこのリストに残っているのは```'LIMIT'```のみです）|
|remain|float|未約定残数(btc)|
|side|string|```'BUY'``` / ```'SELL'```|
|TTE|float|注文時のタイムスタンプ(TTL計算用)|
|price|int|注文価格|
|size|float|注文数量(btc)|
|parent_id|str|紐付けされている親注文idが入っています<br>特殊注文がトリガーされて発生した子注文の場合には親注文のparent_order_acceptance_idが入っています<br>子注文として発行された注文の場合は``` '' ```です
|sendorder|float|sendchildorderを呼び出した時刻のタイムスタンプ|
|accepted|float|child_acceptance_idが割り当てられてsendchildorderの処理が完了した時刻のタイムスタンプ|
|ordered|float|bitFlyerサーバーでオーダーが処理されて（板乗りして）リアルタイムAPIのprivateチャンネルでORDERイベントを受信した時刻のタイムスタンプ|

データ例
```python
[{'id': 'JRF20200512-094231-655108', 'child_order_type': 'LIMIT', 'remain': 0.01, 'side': 'BUY', 'TTE': 1589276551, 'price': 949465, 'size': 0.01, 'parent_id': '', 'sendorder': 1589276551.05321, 'accepted': 1589276551.3192055, 'ordered': 1589276551.631691},
 {'id': 'JRF20200512-094231-490346', 'child_order_type': 'LIMIT', 'remain': 0.01, 'side': 'SELL', 'TTE': 1589276551, 'price': 950465, 'size': 0.01, 'parent_id': '', 'sendorder': 1589276551.3506725, 'accepted': 1589276551.5062394, 'ordered': 1589276552.6875}]
```



> [Tips]   
下のようなコードで特殊注文のトリガーから発生した注文リストだけを抜き出すことが可能です。
```python
triggerd_order_list = [x for x in self.ordered_list if x['parent_id'] != '']
```
> [Tips]   
下のようなコードで板乗りが完了している注文だけを抜き出すことが可能です。
```python
ordered_list = [x for x in self.ordered_list if x.get('ordered')!=None]
```

#### ●　self.parentorder_ordered_list
> 現在の発注済みで未完了の親注文の```parent_order_acceptance_id```がリスト形式で取得できます。

データ例
```python
['JRF20191225-060817-285390' , 'JRF20191225-061518-502715']
```

#### ●　self.server_latency
> 直近の約定配信の遅延秒数です。サーバーの遅延判断などにお使い頂けます。


#### ●　self.server_latency_rate
> 直近の約定遅延が最低値からどの程度上がっているか（ビジーの判断基準）の秒数です。詳細は6章のlatency_limit の項目を参照ください。


#### ●　self.server_health
> サーバーのステータスです。"NORMAL", "BUSY", "VERY BUSY", "SUPER BUSY"などの文字列が入っています。サーバーの遅延判断などにお使い頂けます。


#### ●　self.is_backtesting
> バックテストモードかどうかを示しています。Trueの場合にはバックテスト中であることを示しており、例えばバックテスト時には定期的なステータス表示をスキップする様な使い方が可能です。


#### ●　self.no_trade_period
> 指定されたノートレード期間かどうか (True/False) を確認できます。  
> 詳細は6章のno_trade の項目を参照ください。


#### ●　self._initial_collateral
> 初回起動時または日付が変わった時点での証拠金。この数値とself._getcollateral_api()で得られる数値を比較することで当日の損益を算出できます。

#### ●　self.api_count
> 直近５分間のAPIアクセス回数  
> サーバーからHTTPのレスポンスヘッダでAPI残数が取得されるので、その値から算出された値です。


#### ●　self.api_count_total
> 直近５分間のAPIアクセス回数（全bot最大値)  
> 複数のbotを同一アカウントで稼働させている場合、PositionServer経由でそれぞれのbotのAPIアクセス回数（残数）は共有されており、この変数から全botの中で最大の(もっとも残数の少ない)値を得ることが出来ます。


#### ●　self.api_order_count
> 直近５分間の注文系APIアクセス回数  
> サーバーからHTTPのレスポンスヘッダでAPI残数が取得されるので、その値から算出された値です。


#### ●　self.api_count2
> 直近1分間の0.1btc以下の注文回数

#### ●　self.log_folder
> ロジックの設定ファイルで指定されたログフォルダ  
ロジック側で何らかの保存ファイルなどを作成したい場合にはこのフォルダの中に作成することが推奨されます。


#### ●　self.executed_history
> 約定した自分のオーダー直近100件のリスト  
※ idは同じidの注文が分割して約定する場合があるため、重複しないように末尾に4桁のランダムな数字が追加されてます。オリジナルのidは['id'][:25]で取り出してください。  

|キー|型|説明|
|---|---|---|
|id|string|child_acceptance_idが入っています(末尾の4桁はランダム)|
|price|int|約定価格|
|lot|float|注文数量(btc) プラスの場合はBUY マイナスの場合にはSELL|
|date|str|約定時刻|
|timestamp|float|約定を受信した時刻のタイムスタンプ|
|sendorder|float|sendchildorderを呼び出した時刻のタイムスタンプ|
|accepted|float|child_acceptance_idが割り当てられてsendchildorderの処理が完了した時刻のタイムスタンプ|
|ordered|float|bitFlyerサーバーでオーダーが処理されて（板乗りして）リアルタイムAPIのprivateチャンネルでORDERイベントを受信した時刻のタイムスタンプ|

データ例
```python
[{'id': 'JRF20200512-094301-099042+1015', 'price': 950388, 'lot': -0.01, 'date': '2020-05-12T09:43:24.9685843Z', 'timestamp': 1589276605.4393315, 'sendorder': 1589276581.093942, 'accepted': 1589276581.265079, 'ordered': 1589276582.069016}, 
{'id': 'JRF20200512-094400-285869+2566', 'price': 949507, 'lot': 0.01, 'date': '2020-05-12T09:44:21.2761647Z', 'timestamp': 1589276662.8631773, 'sendorder': 1589276640.219771, 'accepted': 1589276640.5430055, 'ordered': 1589276640.6757529}, 
{'id': 'JRF20200512-094331-551140+9979', 'price': 949453, 'lot': 0.01, 'date': '2020-05-12T09:44:21.29179Z', 'timestamp': 1589276662.878866, 'sendorder': 1589276611.3009338, 'accepted': 1589276611.4926784, 'ordered': 1589276611.9680452}]
'timestamp': 1589273555.8885381}]
```