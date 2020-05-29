# 【BFS-X】ポジションを自炊して高速に売買を行うbitFlyerでの高速botフレームワーク(mmbotと高速スキャルピングbotのサンプルロジック付属)


---
## ３．クラスの中で使用できるメンバ関数
---

BFS-Xでは、ユーザーがロジックを記載したクラス(MyStrategy)はベースとなるロジッククラスを継承する形で記載することで、事前に用意されたクラスメンバ関数を使用して実際の売買などを簡単に取引を行うコードを記述することが出来ます。
### ■ メンバ関数詳細

#### ●　self._childorder(type, side, size, price=0, time_in_force="GTC")
> 注文を発行します。  

|入力|型|説明|
|---|---|---|
|type|string|注文の執行条件(LIMIT/MARKET)|
|side|string|売買方向。買い注文の場合は "BUY", 売り注文の場合は "SELL" を指定します。|
|size|float|売買数量|
|price|int|執行条件がLIMITの場合の指値価格(MARKETの場合には省略可能)|
|time_in_force|str|執行数量条件 を "GTC", "IOC", "FOK" のいずれかで指定します。省略した場合の値は "GTC" です。|

|出力|型|説明|
|---|---|---|
|res|dict| bitFlyer HTTP API からのレスポンス|
コード例
```python
self._childorder(type="LIMIT", side="BUY", size=0.01, price=854000)
```
実行例(正常オーダー時)
```python
{'child_order_acceptance_id': 'JRF20191211-001824-668915'}
```
実行例(エラー時　(例))
```python
{'status': -106, 'error_message': 'The price is too low.', 'data': None}
```
```python
{'status': -205, 'error_message': 'Margin amount is insufficient for this order.', 'data': None}
```

> [Tips]  
下記のようなコードでオーダー後に`child_order_acceptance_id`を得ることが出来ます。(idは個別キャンセルなどに使えます)  
```python
res = self._childorder(type="LIMIT", side="BUY", size=0.01, price=854000)
if res and "JRF" in str(res) :
    id = res['child_order_acceptance_id']
else:
    # オーダー失敗
```


#### ●　self._limit_buy(price, size, time_in_force="GTC")
> 指値での買い注文を発行します。(過去との互換性のために用意されています)  
> self._childorder(type="LIMIT", side="BUY", size=size, price=price) を行う事と同じです。

|入力|型|説明|
|---|---|---|
|price|int|指値価格|
|size|float|売買数量|
|time_in_force|str|執行数量条件 を "GTC", "IOC", "FOK" のいずれかで指定します。省略した場合の値は "GTC" です。|

|出力|型|説明|
|---|---|---|
|res|dict| bitFlyer HTTP API からのレスポンス|

#### ●　self._limit_sell(price, size, time_in_force="GTC")
> 指値での売り注文を発行します。(過去との互換性のために用意されています)  
> self._childorder(type="LIMIT", side="SELL", size=size, price=price) を行う事と同じです。

|入力|型|説明|
|---|---|---|
|price|int|指値価格|
|size|float|売買数量|
|time_in_force|str|執行数量条件 を "GTC", "IOC", "FOK" のいずれかで指定します。省略した場合の値は "GTC" です。|

|出力|型|説明|
|---|---|---|
|res|dict| bitFlyer HTTP API からのレスポンス|

#### ●　self._market_buy( size )
> 成買いの注文を発行します。(過去との互換性のために用意されています)  
> self._childorder(type="MARKET", side="BUY", size=size) を行う事と同じです。

|入力|型|説明|
|---|---|---|
|size|float|売買数量|

|出力|型|説明|
|---|---|---|
|res|dict| bitFlyer HTTP API からのレスポンス|

#### ●　self._market_sell( size )
> 成売りの注文を発行します。(過去との互換性のために用意されています)  
> self._childorder(type="MARKET", side="SELL", size=size) を行う事と同じです。

|入力|型|説明|
|---|---|---|
|size|float|売買数量|

|出力|型|説明|
|---|---|---|
|res|dict| bitFlyer HTTP API からのレスポンス|

#### ●　self.order(type, side, size, trigger=0, price=0, offset=0 )
> 特殊注文を行うためのオーダーパラメータを作成します。  
後述するself._parentorder関数の引数として使用するオーダーパラメータとして利用します。使用例はself._parentorder関数の項目を参照してください。

|入力|型|説明|
|---|---|---|
|type|string|注文の執行条件(LIMIT/MARKET/STOP/STOP_LIMIT/TRAIL)|
|side|string|売買方向。買い注文の場合は "BUY", 売り注文の場合は "SELL" を指定します。|
|size|float|売買数量|
|trigger|int|執行条件がSTOPおよびSTOP_LIMITの場合のトリガー価格|
|price|int|執行条件がLIMITおよびSTOP_LIMITの場合の指値価格|
|offset|int|執行条件がTRAILの場合のオフセット価格|

|出力|型|説明|
|---|---|---|
|order|dict| self._parentorderに与えるためのパラメータ形式|

実行例
```python
{'product_code': 'FX_BTC_JPY', 'condition_type': 'STOP', 'side': 'SELL', 'size': 0.01, 'trigger_price': 799988}
```

#### ●　self._parentorder(params, method='SIMPLE', time_in_force="GTC")
> 特殊注文を発行します。  

|入力|型|説明|
|---|---|---|
|params|list[dict]|self.order()で生成したパラメータをリストとして渡します|
|method|string|注文方法を指定します(SIMPLE/IFD/OCO/IFDOCO) 省略時はSIMPLE|
|time_in_force|str|執行数量条件 を "GTC", "IOC", "FOK" のいずれかで指定します。省略した場合の値は "GTC" です。|

コード例
```python
# STOP注文 854000に到達したら成買い
self._parentorder( [self.order(type="STOP", side="BUY", size=0.01, trigger=854000)] )
```
```python
# self.ltp-1000に達したら、self.ltp-500に売り指値
self._parentorder( [self.order(type="STOP_LIMIT", side="SELL", size=0.01, trigger=self.ltp-1000, price=self.ltp-500)] )
```
```python
# 直近高値から4000円さがったら成売り
self._parentorder( [self.order(type="TRAIL", side="SELL", size=0.01, offset=4000)] )
```
```python
# IFD注文　指値753000で発注、約定したら732000に損切のSTOP指値を置く
self._parentorder( [
    self.order(type="LIMIT", side="BUY", size=0.01, price=753000),
    self.order(type="STOP", side="SELL", size=0.01, trigger=732000)],
    method='IFD' )
```
```python
# OCO注文　854000に売り指値、753000に買い指値、どちらかが約定したらもう一方はキャンセル
self._parentorder( [
    self.order(type="LIMIT", side="SELL", size=0.01, price=854000),
    self.order(type="LIMIT", side="BUY", size=0.01, price=753000)],
    method='OCO' )
```
```python
# IFDOCO注文　753000に買い指値、約定したら、直近高値から4000円下がったら成売りするトレーリングオーダーと、
# 734000まで下がったら733000に売り指値を置くSTOP_LIMITオーダーを発行し、いずれかが約定したらもう一方はキャンセル
self._parentorder( [
    self.order(type="LIMIT", side="BUY", size=0.01, price=753000),
    self.order(type="STOP_LIMIT", side="SELL", size=0.01, trigger=734000, price=733000),
    self.order(type="TRAIL", side="SELL", size=0.01, offset=4000) ], method='IFDOCO' )
```
実行例(正常オーダー時)
```python
{'parent_order_acceptance_id': 'JRF20191211-025851-475607'}
```
実行例(エラー時　(例))
```python
{'status': -205, 'error_message': 'Margin amount is insufficient for this order.', 'data': None}
```

> [Tips]  
下記のようなコードでオーダー後に`parent_order_acceptance_id`を得ることが出来ます。(idは個別キャンセルなどに使えます)  
```python
res = self._parentorder( [...略...] )
if res and "JRF" in str(res) :
    id = res['parent_order_acceptance_id']
else:
    # オーダー失敗
```

#### ●　self._cancel_childorder( id )
> idを指定して注文キャンセルを行います。オーダー発注時の戻りから`child_order_acceptance_id`を保存しておいて、idを指定することで個別キャンセル処理を行えます。

|入力|型|説明|
|---|---|---|
|id|string|child_acceptance_id または child_order_id|

|出力|型|説明|
|---|---|---|
|-|-|-|

> [Tips]  
複数のbotを平行稼働させるためには、出来る限りself._cancel_all_orders()ではなくこちらの個別キャンセルを使用するのが良いでしょう。  
2019/12/2移行のAPI規制以降`_cancel_all_orders`はAPI回数制限の対象なのでAPI回数制限の観点からもこちらの個別キャンセルを使用するのが良いでしょう。

#### ●　self._cancel_parentorder( parent_order_acceptance_id)
> idを指定して特殊注文をキャンセルします。オーダー発注時の戻りから`parent_order_acceptance_id`を保存しておいて、idを指定することで個別キャンセル処理を行えます。親注文に関連して生成された子注文もすべて一括でキャンセルされます。

|入力|型|説明|
|---|---|---|
|id|string|parent_order_acceptance_id または parent_order_id|

|出力|型|説明|
|---|---|---|
|-|-|-|

#### ●　self._cancel_all_orders()
> 全注文キャンセルを行います。   
※この関数を実行する場合、並行稼働中のbotのオーダーもキャンセルしますので実行する場合には複数のbot稼働はできません 

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|-|-|-|

#### ●　self._close_position()
> 現在ポジションと同数の反対売買を行ってポジションのクローズを行います。  

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|result|bool|売買成功したら True / 失敗の場合には Falseを戻り値として返します|

#### ●　self._get_positions()
> 現在の建玉リストを取得します。（バックテスト非対応）  
 BFS-X内部で保持している建玉リストを返しますので、実際のAPIコールは行いません（API呼び出し回数の制限に影響せずに何度でも取得可能です）

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|position|list[dict]|現在の建玉リストを返します|

実行例
```python
[{'id': 'JRF20191210-135023-798164', 'price': 806878, 'size': 0.03, 'side': 'SELL', 'timestamp': 1575985977.0647564},
 {'id': 'JRF20191210-135027-257923', 'price': 806848, 'size': 0.03, 'side': 'SELL', 'timestamp': 1575985977.0647614},
 {'id': 'JRF20191210-135219-910054', 'price': 807620, 'size': 0.05, 'side': 'SELL', 'timestamp': 1575985977.0648136},
 {'id': 'JRF20191210-135247-258872', 'price': 807273, 'size': 0.03, 'side': 'SELL', 'timestamp': 1575985977.0648184}]
 ```

#### ●　self._get_board()
> 現在の板情報を取得します。（バックテスト非対応）  
RealtimeAPIをwebsocketで常時受信しており、APIコールすることなく（APIの回数制限を気にせず）この関数でその時点での板情報を取得することが出来ます。

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|board|dict{list[dict]}|現在の取引板データを返します|

実行例
```python
{'mid_price': 588401,
 'bids': [{'price': 588382.0, 'size': 0.05021743}, {'price': 588381.0, 'size': 0.01}, ....],
 'asks': [{'price': 588404.0, 'size': 2.91807838}, {'price': 588423.0, 'size': 0.01474511},...] }
```

#### ●　self._get_spot_board()
> 現在の現物(BTC_JPY)の板情報を取得します。（バックテスト非対応）  
ロジックパラメータファイルの`handle_spot_realtime_api`が`True`の時だけに有効な値を返します。  
RealtimeAPIをwebsocketで常時受信しており、APIコールすることなく（APIの回数制限を気にせず）この関数でその時点での板情報を取得することが出来ます。

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|board|dict{list[dict]}|現在の取引板データを返します|

実行例
```python
{'mid_price': 588401,
 'bids': [{'price': 588382.0, 'size': 0.05021743}, {'price': 588381.0, 'size': 0.01}, ....],
 'asks': [{'price': 588404.0, 'size': 2.91807838}, {'price': 588423.0, 'size': 0.01474511},...] }
```

#### ●　self._get_effective_tick(size_thru, startprice=0, limitprice=1000)
> 現在の板状況からの有効スプレッドを算出します。  
startprice (指定されていなければmid_priceからとなる) から板の上下に向かってsize_thru (単位:BTC)で指定した分の板の位置を検索します。
上下に向かって検索する限界ラインはlimitprice (単位:JPY) で指定できます。

|入力|型|説明|
|---|---|---|
|size_thru|float|対象のBTCサイズ|
|startprice|int|検索開始位置 (0の場合はその時点でのmid_priceから)|
|limitprice|int|検索限界範囲 (省略時には上下1000円)|

|出力|型|説明|
|---|---|---|
|spread|dict|算出された有効スプレッドのbidとaskの価格を返します|

実行例
```python
{'bid': 596420.0, 'ask': 596543.0}
```

#### ●　self._get_board_api()
> 現在の板情報をPublicAPIを使って取得します。時間はかかりますが、その時点での板情報を完全に取得します（バックテスト非対応）

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|board|dict{list[dict]}|現在の取引板データを返します|

> 戻り値の形式はself._get_board()と同じ形式です

#### ●　self._getcollateral_api()
> APIを通じて証拠金残高などを取得することが出来ます。

|入力|型|説明|
|---|---|---|
|-|-|-|

|出力|型|説明|
|---|---|---|
|collateral|dict|現在の証拠金データを返します|

実行例
```python
{'collateral': 409012.0, 'open_position_pnl': -16.76390806, 'require_collateral': 12399.9211182025, 'keep_rate': 32.98369660525939}
```

#### ●　self._get_balance(refresh=True)
> 現物板で取引する場合に使用する口座の資産残高(JPY)の情報を取得します。
refresh = False で呼び出した場合には前回API取得時にキャッシュされた値が返されます（更新されません）  
もし現物板で取引する場合(trade.yamlのproductが "`BTCJPY`" の場合)で、adjust_position_with_api が `true` に設定されている場合には30秒に1回のポジション確認時についでに値が更新され、キャッシュの値は30秒に1回自動的に更新されますので、その際にはrefresh=`False`で呼び出しを行うと頻繁なAPIアクセスを減らすことが出来ます。

|入力|型|説明|
|---|---|---|
|refresh|bool|実際にAPIアクセスを行うかどうか(True/False)|

|出力|型|キー|型|説明|
|---|---|---|---|---|
|res|dict| currency_code|string|常に "JPY" |
|||amount|int|口座の資産残高|
|||available|int|発注余力|
データ例
```python
 {
    "currency_code": "JPY",
    "amount": 1024078,
    "available": 508000
  }
```


#### ●　self._send_discord( text, image )
> position_discord_webhooksで指定したDiscord webhookへメッセージまたはメッセージと画像を送ることが出来ます。メッセージに@everyoneなどのメンションを付けておき、通知設定することでスマートフォンなどへの通知にも使えます。

|入力|型|説明|
|---|---|---|
|text|string|送信するメッセージ|
|image|string|送信する画像のパス名 (画像がない場合は省略可)|

|出力|型|説明|
|---|---|---|
|-|-|-|


#### ●　self.fetch_cryptowatch_candle( minutes=1 )
> Cryptowatchから指定した分足のローソク足データを取得します。バックグラウンドで定期的に(自動的に)取得されているものとは異なり、呼び出したタイミングで指定された長さの足を呼び出したタイミングで実際にCryptowatchから取得を行います。  
複数の長さの足を用いたロジックや、分足データで取引するロジックで、初回のみCryptowatchからデータを取得して、その後は自炊ローソクをつなげて稼働させるようなときに使えます。

|入力|型|説明|
|---|---|---|
|minutes|int|足の長さ（分）省略時1分足|

|出力|型|説明|
|---|---|---|
|candles|pandas|取得したローソク足が格納されたpandasを返します|

使用例
```python
candles = self.fetch_cryptowatch_candle( minutes=120 )
```
実行結果例
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
