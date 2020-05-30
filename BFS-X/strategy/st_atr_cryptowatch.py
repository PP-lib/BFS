# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import numpy
import talib
import copy

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0
        self._last_close = 0
        self._last_xATR = 0
        self._last_nLoss = 0
        self._last_xATRTrailingStop = 0

    def logic(self):
        # cryptowatchから取得 (最後のは未確定なので捨てる）
        cw_candles = copy.deepcopy(self.cryptowatch_candle[:-1])

        # CryptoWatchから取得したローソク足が前回と変わっていなかったら何もせずに終了
        if self._last_candle == cw_candles.index[-1] : return
        self._last_candle = cw_candles.index[-1]

        # 必要なローソク足の本数を決める
        req = self._strategy_config['buffersize']

        # Cryptowatchからの取得ローソク足からnumpy配列を生成
        h = numpy.array(cw_candles["high"],dtype='f8')[-self._strategy_config['nATRPeriod']*req:]
        l = numpy.array(cw_candles["low"],dtype='f8')[-self._strategy_config['nATRPeriod']*req:]
        c = numpy.array(cw_candles["close"],dtype='f8')[-self._strategy_config['nATRPeriod']*req:]

        # ATRとnLossの計算
        xATR = talib.ATR(h, l, c, self._strategy_config['nATRPeriod'])
        nLoss = self._strategy_config['nATRMultip'] * xATR

        # xATRTrailingStopの計算
        xATRTrailingStop = [0]*self._strategy_config['nATRPeriod']*req    # 初期値の準備
        for i in range(self._strategy_config['nATRPeriod']*req) :
            if c[i] > xATRTrailingStop[i-1] and c[i-1] > xATRTrailingStop[i-1]   : xATRTrailingStop[i] = max(xATRTrailingStop[i-1],c[i]-nLoss[i])
            elif c[i] < xATRTrailingStop[i-1] and c[i-1] < xATRTrailingStop[i-1] : xATRTrailingStop[i] = min(xATRTrailingStop[i-1],c[i]+nLoss[i])
            elif c[i] > xATRTrailingStop[i-1]                                    : xATRTrailingStop[i] = c[i]-nLoss[i]
            else                                                                 : xATRTrailingStop[i] = c[i]+nLoss[i]

        # loss_cut_check関数内でのステータス表示用に保管
        self._last_close = c[-1]
        self._last_xATR = xATR[-1]
        self._last_nLoss = nLoss[-1]
        self._last_xATRTrailingStop = xATRTrailingStop[-1]

        # Close価格がxATRTrailingStopを超えたらロング
        if self.current_pos<=0 and c[-1]>xATRTrailingStop[-1] :
            self._logger.info( "{}  Close:{:.0f} ATR:{:>4.0f} nLoss:{:>5.0f} Stop:{:.0f}  BUY".format(self._last_candle,c[-1],xATR[-1],nLoss[-1],xATRTrailingStop[-1]) )
            self._market_buy( size=self._strategy_config['lotsize']-self.current_pos )     # 現在ポジをプラスしてドテンロング

        # Close価格がxATRTrailingStopを下回ったらショート
        if self.current_pos>=0 and c[-1]<xATRTrailingStop[-1] :
            self._logger.info( "{}  Close:{:.0f} ATR:{:>4.0f} nLoss:{:>5.0f} Stop:{:.0f}  SELL".format(self._last_candle,c[-1],xATR[-1],nLoss[-1],xATRTrailingStop[-1]) )
            self._market_sell( size=self._strategy_config['lotsize']+self.current_pos )    # 現在ポジをプラスしてドテンショート

    def loss_cut_check(self):
        if not self.is_backtesting : 
            self._logger.info( "      {} Close:{:.0f} ATR:{:>4.0f} nLoss:{:>5.0f} Stop:{:.0f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}".format(
                 self._last_candle,self._last_close,self._last_xATR,self._last_nLoss,self._last_xATRTrailingStop,
                 self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                 self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))
        return False


"""
https://jp.tradingview.com/script/DW1GWSWQ-ATR-Strategy-Back-test/


strategy(title="ATR Strategy", overlay = true,  commission_type=strategy.commission.percent,commission_value=0.075)
//credits to HPotter for the orginal code
nATRPeriod = input(5)
nATRMultip = input(3.5)
xATR = atr(nATRPeriod)
nLoss = nATRMultip * xATR
xATRTrailingStop = iff(close > nz(xATRTrailingStop[1], 0) and close[1] > nz(xATRTrailingStop[1], 0), max(nz(xATRTrailingStop[1]), close - nLoss),
                    iff(close < nz(xATRTrailingStop[1], 0) and close[1] < nz(xATRTrailingStop[1], 0), min(nz(xATRTrailingStop[1]), close + nLoss), 
                        iff(close > nz(xATRTrailingStop[1], 0), close - nLoss, close + nLoss)))
pos =    iff(close[1] < nz(xATRTrailingStop[1], 0) and close > nz(xATRTrailingStop[1], 0), 1,
        iff(close[1] > nz(xATRTrailingStop[1], 0) and close < nz(xATRTrailingStop[1], 0), -1, nz(pos[1], 0))) 
color = pos == -1 ? red: pos == 1 ? green : blue 
plot(xATRTrailingStop, color=color, title="ATR Trailing Stop")

barbuy = close > xATRTrailingStop 
barsell = close < xATRTrailingStop 

strategy.entry("Long", strategy.long, when = barbuy) 
strategy.entry("Short", strategy.short, when = barsell) 

barcolor(barbuy? green:red)
"""
