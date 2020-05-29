# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
from datetime import datetime, timedelta
import time
from threading import Thread, Lock
import requests
import traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

class MyStrategy(Strategy):

    def initialize(self):
        self.times_history = deque(maxlen=1440)        # 60秒ごと1日分
        self.market_price_history = deque(maxlen=1440) # 60秒ごと1日分
        self.openinterest_history = deque(maxlen=1440) # 60秒ごと1日分
        self.last_minutes = 0
        self.curretn_open_interest = 0
        open_interest_thread = Thread(target=self.open_interest, args=())  # 定期的にMexのAPIからOIを取得する関数を別スレッドで起動
        open_interest_thread.start()                                       # 別スレッドにするのはAPI取得中メインのロジックが止まることを避けるため

    # 定期的にMexのAPIからOIを取得する関数（別スレッドで起動される）
    def open_interest(self):
        while True:
            try:
                self.curretn_open_interest = requests.get("https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&columns=openInterest&reverse=true").json()[0]['openInterest']
                self._logger.info( "Open Interest : {}".format(self.curretn_open_interest) )

            except Exception as e:             # エラー処理適当、全エラー握りつぶす ww
                self._logger.exception("Mex API error : {}, {}".format(e, traceback.print_exc()))

            time.sleep( 10 )  # MEXのAPIを叩く頻度がどの程度が適切かわからないけど10秒毎くらいならBANされることもないだろう

    # メイン部
    # timescale=0なので、logic_loop_period秒ごとに呼ばれる
    def logic(self):

        if self.curretn_open_interest == 0 : return     # 初回がまだ取得されていなければなにもしない（起動直後など）

        # 60秒(logic_loop_periodで指定)ごとにopen_interestをdequeに保管
        self.times_history.append( datetime.utcnow()+timedelta(hours=9) ) # UTCから計算するのはタイムゾーン設定がJSTでなくてもJST時間でプロットするため
        self.market_price_history.append( self.ltp )                      # 現在価格
        self.openinterest_history.append( self.curretn_open_interest )    # 現在のOpen Interest

        # 5分(300秒)ごとに、dequeに保管された証拠金をプロットしてdiscordへ送信
        if len(self.times_history) > 2 and self.last_minutes != int(time.time() / 300) :
            self.last_minutes = int(time.time() / 300) 

            # 証拠金のプロット
            image_file = 'open_interest.png'
            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()
            ax1 = fig.add_subplot(111)
            ax1.set_title('MEX Open Interest')
            ax2 = ax1.twinx()
            ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, loc: "{:,}".format(int(x)))) 
            ax2.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter(useOffset=False,useMathText=True)) 
            ax1.plot(list(self.times_history), list(self.market_price_history), label='market price', color='red', linestyle='dashed')
            ax2.plot(list(self.times_history), list(self.openinterest_history), label='open interest', color='blue')
            ax1.tick_params(axis='y', colors='red')
            ax2.tick_params(axis='y', colors='blue')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M'))
            h1, l1 = ax1.get_legend_handles_labels()
            ax1.legend(h1, l1, loc='upper left', prop={'size': 8})
            h2, l2 = ax2.get_legend_handles_labels()
            ax2.legend(h2, l2, loc='upper right', prop={'size': 8})
            plt.savefig(image_file)
            plt.close()

            # discordへ送信 (画像付き)
            self._send_discord( '@everyone\nOpen Interestグラフ', image_file )

        return False

    def loss_cut_check(self):
        return False

