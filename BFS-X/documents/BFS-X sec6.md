# 【BFS-X】ポジションを自炊して高速に売買を行うbitFlyerでの高速botフレームワーク(mmbotと高速スキャルピングbotのサンプルロジック付属)


---
## ６．BFS-X稼働パラメータファイル
---


BFS-Xの動作に関して、稼働パラメータファイルで設定を変更することが出来ます。  
稼働パラメータファイルのデフォルト名は```trade.yaml```ですが、5章で説明した通り起動時引数で指定することも可能です。


### ■ ファイル形式
稼働パラメータファイルはYAML形式で記載されており、```項目名 : 値``` の形式で記載されています。


記述例（デフォルトのパラメータ）
<img src="images/trade_yaml.png">



### ■ 設定パラメータ詳細
#### ●　strategy_py :
読み込むロジックファイル(.py)を指定します。
カレントフォルダ(trade.pyがあるフォルダ)からの相対パスで指定します。


#### ●　strategy_yaml :
読み込むロジックパラメータファイル(.yaml)を指定します。
カレントフォルダ(trade.pyがあるフォルダ)からの相対パスで指定します。


#### ●　apikey :
bitFlyerの ```API Key``` を設定します。  

APIキーの権限は下記の通り設定してください。  
<img src="images/api.png" width="70%">  
特に気付きにくいのが「注文のイベントを受信」のチェックです。こちらが入っていない場合には起動時にwebsocketの認証に失敗した旨のエラーが出ます。  

<img src="images/auth.png">


#### ●　secret :
bitFlyerの ```API Secret``` を設定します。


#### ●　product :
取引するマーケットを指定します。  
FX_BTC_JPY / BTC_JPY / BTCJPY29MAR2019 などが指定できます。


#### ●　console_output :
稼働時にコンソール出力を行うかどうかを選択します。(true / false)  
この項目をfalseにすると、コンソールに出力する代わりにログフォルダ内にconsole.txtというファイルを作成しそちらへ出力を行います。  
SSHなどでターミナル接続して稼働させる場合にターミナルを切断しても稼働を続けるためnohupコマンドで起動させますが、その際にコンソールの代わりファイルに出力させておけば、tail -f console.txtとコマンドを打つことでログをリアルタイム表示させて稼働チェックを行う事が出来ます。  
このパラメータは稼働中でも変更可能です。


#### ●　adjust_position_with_api :
定期的なポジション補正を行うかどうかを指定します。(true / false)  
trueを指定しておくと定期的にAPIでgetpositionsを行い、自炊している想定ポジションと実際のポジションがズレている場合に、成売買でポジション数を合わせるように補正を行います。  
複数botを稼働させる場合にはこの項目は```false```にして、別途ポジションサーバーを稼働させるようにしてください。（8章を参照してください）


#### ●　check_cross_trade :
対当売買の判定を行うかどうかを指定します。(true / false)  
trueの場合にはexpire期間過ぎても約定履歴に流れてこなかったけれどgetchildordersで確認して注文残数がなくなっていれば対当売買として処理するようにします。  
当パラメータは通常は```true```にしてください。


#### ●　api_limit2 :
bitFlyerのAPI制限のうち、「0.1 以下の数量の注文は、すべての板の合計で 1 分間で 100 回を上限とします。」とされている制限のための閾値を設定します。  
BFS-Xでは内部で直近1分間の「0.1 以下の数量の注文」をカウントしており、そのカウンターが```api_limit2```を超えた場合に、api_pending_timeで指定した秒数の間は新規の発注を停止します。  
デフォルトでは80になっていますが、状況に応じて変更してください。  
なお、ロジックからカウンターは```self.api_count2```で読み取ることが出来ます。


#### ●　api_pending_time :
「0.1 以下の数量の注文」回数が api_limit2 を超えた場合に休止する時間（秒）を指定します。


#### ●　base_position :
ある一定のポジションをキープしながら運用する場合に使用します。  
apiから取得したgetpositionsの値に対して、ここで指定した数(単位はBTC)を引いて判定することで、adjust_position_with_apiを使用した際に常に一定のポジションを持つようにすることができます。  
例えば常にショートポジションをもってSFDを回避するようなときに使用します。


#### ●　interval_health_check :
サーバーのBUSY（"NORMAL", "BUSY", "VERY BUSY", "SUPER BUSY"などの状態）を取得する間隔（秒）を指定します。  
頻繁に確認すると遅延への対応が迅速に行えますが「同一 IP アドレスからの API の呼出は 5 分間で 500 回を上限とします。」というAPI回数制限に引っかかりやすくなります。


#### ●　execution_check_with_public_channel :
パブリックのexecutions配信でポジション自炊を行うか選択します。 (ture/false)  
false(デフォルト)の場合には RealtimeAPI の PRIVATE CHANNELS の 注文イベントを元にポジション自炊を行います。
true の場合には、RealtimeAPI の PUBLIC CHANNELS で配信されている約定データを元にポジション自炊を行います。


#### ●　no_trade :
トレード停止する時間を指定することが可能です。   
指定した期間はポジションを減らす方向（ロングポジを持っている場合にはショートオーダー、ショートポジを持っている場合にはロングオーダー）のみを実行します。  


記述例１
```python
# メンテ前の3:50～メンテ明けの4:10までの期間トレードを停止する
no_trade :
  - period: 03:50-04:10
```

カンマの後に曜日指定することも可能です。（0=月曜日、1=火曜日、…　5=土曜日、6=日曜日）  

記述例２
```python
# 土曜日の1:50～11:00まではトレードを停止する
no_trade :
  - period: 01:50-11:00,5
```

複数行記述することで複数の時間帯を指定することも可能です。

記述例３
```python
no_trade :
  - period: 23:45-00:10
  - period: 03:50-04:10
  - period: 01:50-11:00,5
```
> [Tips]   
ノートレード期間に入った時にポジションを強制的にクローズするかどうかはロジックパラメータファイルの`close_position_while_no_trade`で指定できます。  
`True`に指定した場合には `close_position : True` にしたときと同様の挙動で['lotsize']の3倍以下のポジションであれば成り⾏きで決済を⾏い強制的にポジションクローズします。  
短期間に取引を行うmmbotなどではノートレード期間の価格変動リスクを避けるためにノーポジションにするほうが安全ですが、長期間の取引を行うスイングロジックなどではノートレード期間でもポジションを保持する方が良いでしょう。


#### ●　pos_server / pos_server_graph_period / pos_server_discord / pos_server_discord_interval :
これらのパラメータはポジションサーバー(pos_server.py)を使用する際に設定します。複数ロジックを動作させない場合はこの項目はデフォルトのままコメントアウトされた状態でお使いください。  
使用方法の詳細は8章の「複数botの平行稼働（ポジションサーバーについて）」を参照してください。