# 【BFS-X】ポジションを自炊して高速に売買を行うbitFlyerでの高速botフレームワーク(mmbotと高速スキャルピングbotのサンプルロジック付属)


---
## ５．環境構築と起動方法
---

当noteでは基本的に**環境構築や起動方法はサポート対象外**ですが、簡単な説明だけをこちらに記載しておきます。  
こちらの説明を読んで理解いただける方を販売対象とさせていただきます。

### ■ フォルダ構成
配布されているファイルはフォルダ構成のまま圧縮されていますので、そのままのフォルダ構成でファイルを展開して用意してください。  
Pythonが稼働できる環境であれば、様々な環境で使用することが可能ですが、一例としてAWSでのフォルダ構成例はこちらです。  
何らかのサブフォルダを作ってからその中に展開していただいても結構です。

<img src="images/folders.png" width="55%">





---
### ■ 構成ファイル
#### ●　```trade.py```
BFS-Xの本体プログラムです。  
**このファイルがある場所をカレントフォルダにして起動**してください。


#### ●　```trade.yaml```
BFS-Xの稼働パラメータです。詳細は6章を参照してください。  
trade.pyと同じフォルダに配置します。


#### ●　```libs```フォルダ
BFS-Xを動かすためのライブラリが入っているフォルダです。


#### ●　```pybitflyer```フォルダ
pybitflyerの改造版が入っているフォルダです。


#### ●　```strategy```フォルダ
サンプルロジック（とそのパラメータファイル）が入っています。


#### ●　```strategy_readme.txt```
サンプルロジックを簡単に説明したファイルです。（テキストファイル）


#### ●　```pos_server.py```
複数のbotを起動するときに、ポジションを統合管理するサーバーです。trade.yamlファイルからAPIキーなどを読み込んで動作します。  
使用する場合にはtrade.yamlファイルの pos_server : ['localhost', 51000] の部分のコメントを外してください。 詳細な使用方法は8章を参照してください。 
**ポジションサーバーを使う場合には adjust_position_with_api を falseにしてください。（重要）**


#### ●　```backtest_scalpingmode.py / backtest_scalpingmode.yaml```
秒スキャモード用のバックテストプログラムとそのパラメータファイルです。


#### ●　```backtest_cryptowatch.py / backtest_cryptowatch.yaml```
スイングモード用のバックテストプログラムとそのパラメータファイルです。


---
> [Tips]  
 strategyフォルダにはたくさんのサンプルロジックが入っています。ご自身のロジックや、サンプルロジックの内で稼働させるロジックを別フォルダ(下図の例だと MyLogicフォルダ) に入れておくと分かりやすいでしょう。


<img src="images/mylogic.png" width="50%">

---






### ■ 必要なパッケージのインストール
BFS-Xでは下記のパッケージを必要とします。
```
websocket-client
python-dateutil
pandas==0.24.2
pyyaml
matplotlib
requests
sortedcontainers
discord
influxdb
```

pipコマンドなどを用いてパッケージのインストールを行ってください。
当方で動作確認したawsの環境では下記のコマンドでインストールを行いました。各々の環境で異なる可能性はありますので、必要に応じて調べてみてください。

```
sudo pip install websocket-client python-dateutil pandas==0.24.2 pyyaml matplotlib requests sortedcontainers discord influxdb
```
実行例
<img src="images/pipinstall.png">


そのほか、指数の計算などのためにTA-Libなどもインストールされると良いかと思います。





### ■ 今後のバージョンアップ方法
新しいバージョンへのバージョンアップは基本的に **ルートフォルダにあるpythonファイル(```trade.py``` / ```pos_server.py``` / ```backtest_scalpingmode.py``` / ```backtest_cryptowatch.py``` など)と、 ```libs```フォルダと```pybitflyer```フォルダを上書きしていただけば更新いただけます**。  
ご自身のロジックを**別フォルダ**に入れられている場合には、```strategy```フォルダも上書きしても問題ありません。  
ただし、**trade.yamlファイルは設定したAPIキーなどが上書きされてしまうので上書きしていはいけません**。  
後述する起動方法でtrade.yaml以外のファイル名を使って起動させることもできるので、別のファイル名にして運用しておけば全て上書きしてバージョンアップすることもできるでしょう。

### ■ タイムゾーンの変更
稼働させる環境によってはタイムゾーンが日本標準時(JST)ではなく協定世界時(UTC)になっていることもあるでしょう。UTCのままでもBFS-Xは稼働できますが、1時間ごとの統計表示や損益グラフなどの時刻表示がズレることがあるので、JSTに変更しておくことをお勧めします。

dateコマンドで確認して、USTと表示されているようでしたら、下記のコマンドを用いてJST設定に変更しておきましょう。
```
sudo sed -i -e 's/ZONE="UTC"/ZONE="Japan"/g' /etc/sysconfig/clock
sudo ln -sf /usr/share/zoneinfo/Japan /etc/localtime
```
実行例
<img src="images/timezone.png">







### ■ 起動方法

#### ●　【方法１】もっともシンプルな起動方法
```trade.py```があるフォルダをカレントフォルダにして```trade.py```をPython3で実行します。

実行コマンド
```
python3 trade.py
```
起動されると```trade.py```と同じフォルダにある```trade.yaml```がパラメータファイルとして読み込まれ、その中の```strategy_py:```で設定されたロジックファイルと```strategy_yaml:```で指定されたロジックパラメータファイルが読み込まれbotがスタートします。

取引所のapiとシークレットキーを```apikey:```と```secret:```に記載しておけば取引が開始されます。

起動時のイメージ
<img src="images/startup.png">







#### ●　【方法２】稼働パラメータを指定しての起動方法 (引数1つ指定しての起動)
複数の稼働パラメータを使い分けたい場合や、デフォルトの```trade.yaml```という名前以外の稼働パラメータを使いたい場合(バージョンアップ時にそのまま上書きすると```trade.yaml```ファイルは上書きされてしまうため、それを避けたい場合など)には起動時にパラメータファイルを指定して起動させることも可能です。

実行コマンド例
```
python3 trade.py mytrade.yaml
```
起動されると```trade.py```と同じフォルダにある```mytrade.yaml```がパラメータファイルとして読み込まれ、その中の```strategy_py:```で設定されたロジックファイルと```strategy_yaml:```で指定されたロジックパラメータファイルが読み込まれbotがスタートします。  
また、下記のようにサブフォルダ内にパラメータを入れておいて起動させることも可能です。


稼働パラメータをサブフォルダに入れておく実行コマンド例
```
python3 trade.py myparams/mytrade.yaml
```

#### ●　【方法３】ロジックファイル・ロジックパラメータファイルを指定しての起動方法 (引数2つ指定しての起動)
ロジックファイルを稼働パラメータファイル(```mytrade.yaml```)内に記載しておくのではなく、コマンドライン引数として指定することも可能です。  
ロジックファイル(.py)とロジックパラメータファイル(.yaml)をカレントフォルダからの相対パス指定で引数として与えます。

実行コマンド例
```
python3 trade.py mylogic/oreno_logic.py mylogic/oreno_logic.yaml
```
起動されると```mylogic/oreno_logic.py```がロジックファイル、```mylogic/oreno_logic.yaml```がロジックパラメータファイルが読み込まれbotがスタートします。  

---
> [Tips]  
 複数のターミナルを開いて、それぞれ異なるロジックファイルを指定して起動せることで同一口座で複数のロジックを平行させて稼働させることが可能です。(この場合には```pos_server.py```を使って adjust_position_with_api を falseにしてください。)

稼働例

<img src="images/multi.png">

---

#### ●　【方法４】稼働パラメータ・ロジックファイル・ロジックパラメータファイルを指定しての起動方法 (引数３つ指定しての起動)
稼働パラメータ・ロジックファイル(.py)・ロジックパラメータファイル(.yaml)の全てをコマンドラインから指定して起動することも可能です。

例えば　```trade_fx.yaml```にFX_BTC_JPY用の稼働ファイルを用意して、```trade_spot.yaml```に現物のBTC_JPY用の稼働ファイルを用意しておいて、下記のように両方の取引板で稼働させる事も可能です。

実行コマンド例
```
【bot1:FX】
python3 trade.py trade_fx.yaml mylogic/logic1.py mylogic/logic1.yaml

【bot2:現物】
python3 trade.py trade_spot.yaml mylogic/logic2.py mylogic/logic2.yaml
```

### ■ 停止・再稼働

BFS-Xでは停止する際に ```Ctrl+C``` キーを押して中断すれば、現在の未約定発注のキャンセルを行って、現在のポジションをファイルに書き出し保存します。  
この情報をもとに、再起動時には中断時のポジション情報から継続して稼働することが出来ます。


---
> [Tips1]  
 BFS-Xでは定期的に現在ポジをファイルに残しておいて、停止後再稼働した際に、持っていたポジ情報を復元して継続稼働することができます。  
 停止後ポジションを手動でクリアするなどしてポジションゼロから再スタートしたい場合には、ログフォルダ内のposition.csvを削除して再稼働させるとポジション情報を無しにして再稼働させることができます。

> [Tips2]  
 BFS-Xでは損益情報も定期的にファイルに保存しており、停止後再稼働した際にも当日の損益情報は引き続きグラフ化されます。損益情報をクリアしてゼロから再スタートしたい場合には、profit.csvを削除して再稼働させればOKです。

> [Tips3]  
 BFS-Xでは日々リセットされる日時損益とは別に最長100日の損益をグラフプロットします。長期グラフはログフォルダの中に```profit_all.csv```として保存されており、起動時に読み込まれます。もしリセットしたい場合には、```profit_all.csv```を削除して再起動させることでリセットすることが出来ます。また特定の期間以前を削除する場合には、行単位で削除することも可能です。