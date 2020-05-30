# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import talib as ta
import numpy as np
import math

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

     # 直近の確定足時刻
    _last_candle = 0
    _ordered_id_list = deque(['']*3, maxlen=3)  # logic_loop_periodが5であれば、発注後5*3=15秒でキャンセル発行

    #----------------------------------------------------------------------------
    # trade.yamlで指定したlogic_loop_period（秒）ごとに回ってくるロジック部
    # (server_health が normal_state の時のみ)
    # 売買が発生したら戻り値をTrueに
    #----------------------------------------------------------------------------
    def logic(self):

        # 同じ確定足で何度も取引しないためにcandle_dateが変わっていなければ取引しない
        if self._last_candle==self.candle_date:
            return False
        self._last_candle=self.candle_date

        if len(self.close) <= self._strategy_config['mfi_period'] :
            if not self.is_backtesting :
                self._logger.info( 'Waiting candles.  {}/{}'.format(len(self.close),self._strategy_config['mfi_period']) )
            return False

        id = ''
        # 指数の計算
        h = np.array(self.high)
        l = np.array(self.low)
        c = np.array(self.close)
        v = np.array(self.volume)
        mfi = ta.MFI(h, l, c, v, self._strategy_config['mfi_period'])*2-100

        if not self.is_backtesting :
            self._logger.info( '[{} LTP:{:.0f}] MFI:{:>7.2f} B/S:{:>+4.2f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                self.exec_date, self.ltp, mfi[-1], self.vol_rate(), self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # MAX_LOTに近づくと指値を離して約定しづらくする
        buyprice  = self.ltp - max(0,int(self._strategy_config['position_slide']*self.current_pos/self._strategy_config['max_lot']))-self._strategy_config['depth']
        sellprice = self.ltp - min(0,int(self._strategy_config['position_slide']*self.current_pos/self._strategy_config['max_lot']))+self._strategy_config['depth']

        # 閾値を超えていれば売買
        if self.current_pos<=self._strategy_config['max_lot'] and mfi[-1] < -self._strategy_config['mfi_limit'] :
            responce = self._limit_buy( price=buyprice, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']
        if self.current_pos>=-self._strategy_config['max_lot'] and mfi[-1] > self._strategy_config['mfi_limit'] :
            responce = self._limit_sell( price=sellprice, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']
        self._ordered_id_list.append( id )

        # 一定時間が経ったオーダーをキャンセル発行
        if self._ordered_id_list[0]!='' :
            self._cancel_childorder( self._ordered_id_list[0] )

        return (id!='')

    #----------------------------------------------------------------------------
    # server_healthに関係なく logic_loop_period (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):

        # マイナスポジで大きな買いが入った場合には成でクローズ
        if self.current_pos<0 and self.vol_rate()>self._strategy_config['volume_limit'] :
            return self._close_position()

        # プラスポジで大きな売りが入った場合には成でクローズ
        if self.current_pos>0 and self.vol_rate()<-self._strategy_config['volume_limit'] :
            return self._close_position()

        return False

    def vol_rate(self):
        vol_rate = math.fabs(math.sqrt(self.buy_volume[-1]) - math.sqrt(self.sell_volume[-1]))
        if self.buy_volume[-1] < self.sell_volume[-1] :
            vol_rate = -vol_rate
        return vol_rate
