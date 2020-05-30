# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import time
from collections import deque
import numpy as np

class MyStrategy(Strategy):
    """
    # ロジック内で使用できるメンバ変数
    : self._strategy_config       : strategy_config.yamlファイルのparameters:以下にアクセスできます
    : self.candle_date            : 確定しているローソク足の時刻
    : self.exec_date              : 未確定足に含まれている最新の約定時刻
    : self.open                   : openのリスト
    : self.high                   : highのリスト
    : self.low                    : lowのリスト
    : self.close                  : closeのリスト
    : self.volume                 : volumeのリスト
    : self.buy_volume             : buy_volumeのリスト
    : self.sell_volume            : sell_volumeのリスト
    : self.current_candle         : 未確定足のデータ
    : self.from_lastcandle_update : 現在のローソク足になってから何秒たっているか
    : self.api_count              : 過去5分の間にapiにアクセスした回数
    : self.current_pos            : 現在ポジション (マイナスは売りポジ)
    : self.current_average        : 現在ポジションの平均価格 　　(バックテスト時は未対応）
    : self.current_profit         : 現在の利益（0:00からの利益） (バックテスト時は未対応）
    : self.current_profit_unreal  : 現在の含み損益               (バックテスト時は未対応）
    : self.ltp                    : 現在のLTP
    : self.sfd                    : 現在の乖離率
    : self.spotprice              : 現在の現物価格
    : self.server_latency         : 約定履歴の遅延
    : self.server_latency_rate    : 直近の約定遅延が最低値からどの程度上がっているか（ビジーの判断基準）
    : self.server_health          : サーバーのステータス
    : self.is_backtesting         : バックテストモードかどうか

    # 使用できるメンバ関数
    : self._limit_buy( price, size )  : 指値での買い (戻り値はサーバーからのレスポンス)
    : self._limit_sell( price, size ) : 指値での売り (戻り値はサーバーからのレスポンス)
    : self._market_buy( size )        : 成買い       (戻り値はサーバーからのレスポンス)
    : self._market_sell( size )       : 成売り       (戻り値はサーバーからのレスポンス)
    : self._close_position( )         : 現在ポジションのクローズ(成功したら True / 失敗の場合には False)
    : self._cancel_childorder( id )   : 注文キャンセル
    : self._cancel_all_orders()       : 全注文キャンセル
    """

    def initialize(self):
        self._ask = self._bid = 0
        self._exec_history = deque(maxlen=10000)
        self._exec_history_std = 100
        if not self.is_backtesting : self._last_evented_time = time.time()
        else :                       self._last_evented_time = 0
        self._order__buy_price = self._order__sell_price = 0

    #----------------------------------------------------------------------------
    # Websocketのon_message内から呼び出される関数
    # recept_dataを迅速に処理して可能な限り早めにreturnする事（処理時間が長いと約定履歴の取りこぼしが起きます）
    # 売買シグナルを検出した場合にはorder_signal_eventイベントをセットして、実際の売買処理はrealtime_logic()関数で実施
    #----------------------------------------------------------------------------
    def executions(self,recept_data):
        if not self.is_backtesting : start = time.time()
        else :                       start = recept_data[0]['timestamp']

        # 初回の価格初期化
        if self._ask == 0 : self._ask = recept_data[0]['price']
        if self._bid == 0 : self._bid = recept_data[0]['price']

        # 約定履歴の処理
        for i in recept_data:
            current_price = int(i['price'])
            self._exec_history.append(current_price)

            if i['side']=='BUY' : self._ask = current_price
            else                : self._bid = current_price

            if( self._last_evented_time + self._strategy_config['interval'] < start and    # 前回のオーダーからinterval_time秒以上経っている
                (not self.order_signal_event.is_set()) ):                                  # 前回のイベントが処理済み

                # 直近(期間はwindowで指定)の価格の標準偏差に対してeffectで重みづけをして指値位置を決める
                self._order__sell_price = (self._ask+self._bid)/2 + self._exec_history_std * self._strategy_config['effect']
                self._order__buy_price  = (self._ask+self._bid)/2 - self._exec_history_std * self._strategy_config['effect']

                if self.current_pos>0 :   # 現在の建玉がロングであれば、ポジション量に応じて買いの価格を調整
                    self._order__buy_price  -= (self.current_pos * self._strategy_config['penalty'])
                if self.current_pos<0 :   # 現在の建玉がショートであれば、ポジション量に応じて売りの価格を調整
                    self._order__sell_price -= (self.current_pos * self._strategy_config['penalty'])

                # 売買イベントをセット
                self._last_evented_time = start
                self.order_signal_event.set()

    #----------------------------------------------------------------------------
    # self.order_signal_eventが発生したら呼び出される関数
    #----------------------------------------------------------------------------
    def realtime_logic(self):
        # executions受信処理からexecutions()関数内で売買判断されて、イベントが発生し、ここに到達するまでの時間計測
        # おおむね1～6msec程度では到達出来ているようなので、即時性に問題は無し
        if not self.is_backtesting :
            self._logger.debug( '{:.0f}msec after receive exeutions.  {:.0f}msec after trigger'.format((time.time()-self.execution_timestamp)*1000,(time.time()-self._last_evented_time)*1000) )

            self._logger.info( '                      LTP:{:.0f}   ASK:{:.0f}   BID:{:.0f}   STD:{:.1f}'.format(self.ltp,self._order__sell_price,self._order__buy_price,self._exec_history_std) )

        # 最大ロットを超えていなければエントリー処理
        if self.current_pos<=self._strategy_config['max_lot']  :
            self._limit_buy( price=round(self._order__buy_price), size=self._strategy_config['lotsize'] )

        if self.current_pos>=-self._strategy_config['max_lot']  :
            self._limit_sell( price=round(self._order__sell_price), size=self._strategy_config['lotsize'] )


    #----------------------------------------------------------------------------
    # server_healthに関係なく 1 (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):

        # このループで直近約定のばらつきを評価
        exec_list = list(self._exec_history)[-min(len(self._exec_history),self._strategy_config['window']):] # 直近のexec履歴からwindow分
        self._exec_history_std = np.array(exec_list).std()

        if not self.is_backtesting :
            self._logger.info( '                      LTP:{:.0f}  Profit:{:>+8.0f}({:+4.0f}) Position:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    self.ltp, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                    self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        return False
