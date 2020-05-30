# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time
import math

class MyStrategy(Strategy):
    #----------------------------------------------------------------------------
    # 起動時に呼ばれる関数
    #----------------------------------------------------------------------------
    def initialize(self):
        self._ask = self._bid = 0
        if not self.is_backtesting : self._last_evented_time = time.time()
        else :                       self._last_evented_time = 0
        self._ordered_id_list = deque(maxlen=100)       # 発注済みID
        self._ordered_id_list.append( {} )
        self._buy_volume_list = deque(maxlen=1000)      # 買いボリューム計算用
        self._buy_volume_list.append(0)
        self._sell_volume_list = deque(maxlen=1000)     # 売りボリューム計算用
        self._sell_volume_list.append(0)

    #----------------------------------------------------------------------------
    # Websocketのon_message内から呼び出される関数
    #----------------------------------------------------------------------------
    def executions(self,recept_data):
        if not self.is_backtesting : start = time.time()
        else :                       start = recept_data[0]['timestamp']

        # 初回の初期化
        if self._ask == 0 : self._ask = recept_data[0]['price']
        if self._bid == 0 : self._bid = recept_data[0]['price']

        # 約定履歴の処理
        for i in recept_data:
            if i['side']=='BUY' :
                self._ask = int(i['price'])
                self._buy_volume_list[-1] += i['size']
            else:
                self._bid = int(i['price'])
                self._sell_volume_list[-1] += i['size']

        # 前回のオーダーからinterval_time秒以上経っていたらイベントをセット
        if( self._last_evented_time + self._strategy_config['interval'] < start and (not self.order_signal_event.is_set()) ):
            self._last_evented_time = start
            self.order_signal_event.set()

    #----------------------------------------------------------------------------
    # self.order_signal_eventが発生したら呼び出される関数
    #----------------------------------------------------------------------------
    def realtime_logic(self):

        # 売りの取引高と買いの取引高の差分を求める
        buy_volume = sum(self._buy_volume_list)
        sell_volume = sum(self._sell_volume_list)
        vol_rate = math.sqrt(buy_volume) - math.sqrt(sell_volume)

        # 稼働状況のログ
        if not self.is_backtesting :
            self._logger.info( '            Vol{:+3.1f} LTP:{:.0f} Profit:{:>+7.0f} Pos:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    vol_rate, self.ltp, self.current_profit, self.current_pos, self.api_count,
                    self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # 売買高の差が指定値以下であればエントリーしない
        if math.fabs(vol_rate) < self._strategy_config['volume_th'] :
            return False

        id = ''
        if vol_rate > 0 :
            # 現在ポジがmaxに近づくにつれて発注サイズを減らしてく
            size = math.tanh(self._strategy_config['lotsize'] * (self._strategy_config['max_lot'] - max(0,self.current_pos)) / self._strategy_config['max_lot'])
            if size > 0.01 :
                responce = self._limit_buy( price=self._bid-self._strategy_config['depth'], size=size )
                if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        if vol_rate < 0 :
            # 現在ポジがmaxに近づくにつれて発注サイズを減らしてく
            size = math.tanh(self._strategy_config['lotsize'] * (self._strategy_config['max_lot'] + min(0,self.current_pos)) / self._strategy_config['max_lot'])
            if size > 0.01 :
                responce = self._limit_sell( price=self._ask+self._strategy_config['depth'], size=size )
                if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        # オーダーした場合にはidをdictに保存しておく
        if id!='' : self._ordered_id_list[-1][id]=1

        return (id!='')

    #----------------------------------------------------------------------------
    # server_healthに関係なく 1 (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):
        while len(self._ordered_id_list)>self._strategy_config['cancel_time'] : # cancel_time 個以上のキューが有れば、
            id_dict =  self._ordered_id_list.popleft()                          # キューから一番古いものを取り出して
            if id_dict!={} :                                                   # オーダーデータがあればキャンセル実行
                for id,val in id_dict.items() :     # dictに入っているid全てを
                    self._cancel_childorder( id )   # 順次キャンセル発行

        # 時間経過管理用のキューをシフト
        self._ordered_id_list.append( {} )
        self._buy_volume_list.append( 0 )
        self._sell_volume_list.append( 0 )

        while len(self._buy_volume_list)>self._strategy_config['volume_period'] :   # volume_period以上のものは
            info = self._buy_volume_list.popleft()                                  # 取り出して捨てる
        while len(self._sell_volume_list)>self._strategy_config['volume_period'] :  # volume_period以上のものは
            info = self._sell_volume_list.popleft()                                 # 取り出して捨てる

        return False