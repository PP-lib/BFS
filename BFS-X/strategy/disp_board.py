# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time
import math

class MyStrategy(Strategy):
    #----------------------------------------------------------------------------
    # Websocketのon_message内から呼び出される関数
    #----------------------------------------------------------------------------
    def executions(self,recept_data):
        return

    #----------------------------------------------------------------------------
    # self.order_signal_eventが発生したら呼び出される関数
    #----------------------------------------------------------------------------
    def realtime_logic(self):
        return

    #----------------------------------------------------------------------------
    # server_healthに関係なく 1 (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):

        # publicAPIで板情報の取得
        self._logger.info( "-"*30 )
        starttime = time.time()
        value = self._get_board_api()
        self._logger.info( "fetch board info in {:.1f}msec".format((time.time()-starttime)*1000) )
        for i in range(4,-1,-1):
            self._logger.info( "API{}: {:.0f} {:.8f}".format(i,value['asks'][i]['price'], value['asks'][i]['size']) )
        self._logger.info( "      {:.0f}".format(value['mid_price']) )
        for i in range(5):
            self._logger.info( "API{}: {:.0f} {:.8f}".format(i,value['bids'][i]['price'], value['bids'][i]['size']) )

        # websocketで貯めている板情報の取得
        self._logger.info( "-"*30 )
        starttime = time.time()
        value = self._get_board()
        self._logger.info( "fetch board info in {:.1f}msec".format((time.time()-starttime)*1000) )
        
        for i in range(4,-1,-1):
            self._logger.info( "WS {}: {:.0f} {:.8f}".format(i,value['asks'][i]['price'], value['asks'][i]['size']) )
        self._logger.info( "      {:.0f}".format(value['mid_price']) )
        for i in range(5):
            self._logger.info( "WS {}: {:.0f} {:.8f}".format(i,value['bids'][i]['price'], value['bids'][i]['size']) )

        # websocketで貯めている板情報の取得を利用して有効スプレッドを算出
        self._logger.info( "{}".format(self._get_effective_tick(10)) )        # 直近mid_priceより上下に 10BTC の位置

        return False
