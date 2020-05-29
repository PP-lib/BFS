# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
from datetime import datetime, timedelta
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

class MyStrategy(Strategy):

    def initialize(self):
        self.times_history = deque(maxlen=120)        # 30秒ごと1時間分
        self.market_price_history = deque(maxlen=120) # 30秒ごと1時間分
        self.profit_history = deque(maxlen=120)       # 30秒ごと1時間分
        self.last_minutes = 0

    def logic(self):
        if self._initial_collateral == 0 :            # 初期証拠金残高がまだ取得されていなければ損益計算出来ないのでなにもしない（起動直後など）
            return

        self._logger.info( '-'*50 )
        self._logger.info( 'initial collateral: {}'.format( self._initial_collateral ) )       # 初期証拠金残高(日付が変わって最初に取得されたもの)

        # 60秒(timescaleで指定)ごとに証拠金取得
        responce = self._getcollateral_api()
        self._logger.info( 'current collateral: {}'.format( responce['collateral'] ) )         # 証拠金残高
        self._logger.info( 'open_position_pnl : {}'.format( responce['open_position_pnl'] ) )  # 含み損益
        self._logger.info( 'require_collateral: {}'.format( responce['require_collateral'] ) ) # 必要証拠金
        self._logger.info( 'keep_rate         : {}'.format( responce['keep_rate'] ) )          # 維持率
        self._logger.info( 'profit of today   : {}'.format( responce['collateral'] + responce['open_position_pnl'] - self._initial_collateral ) )  # 証拠金残高の変化から算出された本日の損益

        # discordへ送信 (テキスト)
        self._send_discord( '[collateral : {}]'.format( responce['collateral'] ) )

        # dequeに保管
        self.times_history.append( datetime.utcnow()+timedelta(hours=9) )
        self.market_price_history.append( self.ltp )
        self.profit_history.append( int(responce['collateral'] + responce['open_position_pnl'] - self._initial_collateral) )

        # 5分ごとに、dequeに保管された証拠金をプロットしてdiscordへ送信
        if len(self.times_history) > 2 and self.last_minutes != int(time.time() / 300) :
            self.last_minutes = int(time.time() / 300) 

            # 証拠金のプロット
            image_file = 'foward_test.png'
            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()
            ax1 = fig.add_subplot(111)
            ax2 = ax1.twinx()
            ax1.plot(list(self.times_history), list(self.market_price_history), label='market price', color='blue')
            ax2.plot(list(self.times_history), list(self.profit_history), label='profit', color='red')
            h1, l1 = ax1.get_legend_handles_labels()
            ax1.legend(h1, l1, loc='upper left', prop={'size': 8})
            h2, l2 = ax2.get_legend_handles_labels()
            ax2.legend(h2, l2, loc='upper right', prop={'size': 8})
            plt.savefig(image_file)
            plt.close()

            # discordへ送信 (画像付き)
            self._send_discord( '@everyone\n証拠金(損益)グラフ', image_file )

        return False

    def loss_cut_check(self):
        return False

