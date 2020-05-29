# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time
import math

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0

    def logic(self):
        # ローソク足が変化していたら
        if self._last_candle==self.candle_date:
            return False
        self._last_candle=self.candle_date

        print( '-'*30 )

        # CryptoWatchから取得したローソク足  (cryptowatch_candle分)
        print( self.cryptowatch_candle.tail(3) )
        print( 'length : {}'.format(len(self.cryptowatch_candle)) )
        print( '' )

        # 約定履歴から自炊したローソク足  (timescale秒)
        if len(self.open)>=3 : print( "{}  [o:{} h:{} l:{} c:{}  vol:{:>10.6f}]".format( self.open.index[-3], self.open[-3], self.high[-3], self.low[-3], self.close[-3], self.volume[-3]) )
        if len(self.open)>=2 : print( "{}  [o:{} h:{} l:{} c:{}  vol:{:>10.6f}]".format( self.open.index[-2], self.open[-2], self.high[-2], self.low[-2], self.close[-2], self.volume[-2]) )
        print(                        "{}  [o:{} h:{} l:{} c:{}  vol:{:>10.6f}]".format( self.open.index[-1], self.open[-1], self.high[-1], self.low[-1], self.close[-1], self.volume[-1]) )
        print( '' )

        return

    def loss_cut_check(self):
        return False
