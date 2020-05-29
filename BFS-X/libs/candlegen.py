# coding: utf-8
from libs import executions
from datetime import datetime, timedelta, timezone
from collections import deque
import time
from threading import Event, Thread
import pandas
import numpy
pandas.set_option('display.expand_frame_repr', False)


# SecondCandleクラスを使ってターゲットの長さの足を作り続けるクラス


class GenerateTargetCandle:
    def __init__(self, logger, product, timescale, candlelength, parameters):
        self.candleupdated = Event()
        self.logger = logger
        self.timescale = timescale
        self.candlelength = candlelength
        self._parameters = parameters
        self.candle_pool = pandas.DataFrame()
        self.secondcandle = executions.SecondCandle(
            logger=logger, product=product, timescale=1, parameters=parameters)
        self.lastcandle = datetime.now(timezone(timedelta(hours=9), 'JST'))
        self.running = True
        self.stopflag = False
        while not self.secondcandle.executions:
            self.logger.info("Waiting data from Websocket")
            time.sleep(1)
        self.logger.info("Websocket started")
        self._current_ohlc = {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'buy': 0, 'sell': 0,
                              'count': 0, 'count_buy': 0, 'count_sell': 0, 'total_value': 0}
        self.wdt = time.time()

    @property
    def current_ohlc(self):
        self._current_ohlc = {'exec_date': self.secondcandle.current_exec_date,
                              'open': self.secondcandle.current_open,
                              'high': self.secondcandle.current_high,
                              'low': self.secondcandle.current_low,
                              'close': self.secondcandle.current_close,
                              'volume': self.secondcandle.current_volume,
                              'buy': self.secondcandle.current_buy_volume,
                              'sell': self.secondcandle.current_sell_volume,
                              'count': self.secondcandle.current_count,
                              'count_buy': self.secondcandle.current_buy_count,
                              'count_sell': self.secondcandle.current_sell_count,
                              'total_value': self.secondcandle.current_total_value
                              }
        return self._current_ohlc

    @property
    def lastexecutiontime(self):
        return self.secondcandle.lastexecutiontime

    def secondsfromlastupdate(self):
        if len(self.candle_pool) == 0:
            return 0

        tmp = self.candle_pool.index.values
        if type(tmp[-1]) == numpy.datetime64:
            # dfのtimestamp型をepocに変換
            candle_pool_epoc = int(tmp[-1].astype(numpy.int64) / 1000000000)
        else:
            candle_pool_epoc = tmp[-1].timestamp()
        lastcandle_epoc = self.lastcandle.timestamp()
        diff = candle_pool_epoc - lastcandle_epoc

#        self.logger.info( '{}-{} = {}'.format(tmp[-1],self.lastcandle,diff) )
        return diff

    @property
    def current_latency(self):
        return self.secondcandle.current_latency

    @property
    def mid_price(self):
        return self.secondcandle.mid_price

    @property
    def spot_price(self):
        return self.secondcandle.spot_price

    @property
    def spot_price_exec(self):
        return self.secondcandle.spot_price_exec

    @property
    def board_age(self):
        return self.secondcandle.board_age

    def main_loop(self):

        # 最初の1秒足が確定する瞬間まで待つ
        while not self.secondcandle.candleupdated.wait(10):
            self.logger.info("Wait first candle again")
            continue
        self.secondcandle.updatecandle()
        # 最初の一秒足の一番最後の足の時間を記憶
        lastdate = self.secondcandle.candle[-1:].index[0]
        self.secondcandle.candleupdated.clear()

        lastsecond = -1
        # timescaleにゼロが設定されている場合にはローソク足を生成しない（低負荷・高速運用）
        if self.timescale == 0:
            self.candle = self.secondcandle.candle  # ダミーとして1秒足の初回のデータを入れておく
            self.candleupdated.set()
            while not self.stopflag:
                time.sleep(0.5)
                nowsecond = datetime.now().second
                if lastsecond != nowsecond:
                    self._parameters.api_counter.append(
                        0)  # apiカウンターを1秒ごとにシフトさせる
                    self._parameters.api_counter_small_order.append(
                        0)  # apiカウンターを1秒ごとにシフトさせる
                    self._parameters.execution_counter.append(0)
                    self._parameters.api_sendorder_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.ordered_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.api_cancel_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.canceled_speed_history.append(
                        deque(maxlen=10))
                    lastsecond = nowsecond
                self.wdt = time.time()
            self.running = False
            return

        while not self.stopflag:
            # 1秒足が確定する瞬間まで待つ
            while not self.secondcandle.candleupdated.wait(0.5):
                if self._parameters.renew_candle_everysecond:
                    dummy_exec = {'exec_date': datetime.now(tzinfo=timezone(timedelta(hours=9), 'JST')
                                                            )+timedelta(hours=9), 'price': self.secondcandle.executions[-1]['price'], 'size': 0, 'side': 'NONE'}
                    self.secondcandle.executions.append(dummy_exec)
                nowsecond = datetime.now().second
                if lastsecond != nowsecond:
                    self._parameters.api_counter.append(
                        0)  # apiカウンターを1秒ごとにシフトさせる
                    self._parameters.api_counter_small_order.append(
                        0)  # apiカウンターを1秒ごとにシフトさせる
                    self._parameters.execution_counter.append(0)
                    self._parameters.api_sendorder_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.ordered_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.api_cancel_speed_history.append(
                        deque(maxlen=10))
                    self._parameters.canceled_speed_history.append(
                        deque(maxlen=10))
                    lastsecond = nowsecond
                    if nowsecond % 10 == 0 or self._parameters.renew_candle_everysecond:
                        break
            self.secondcandle.updatecandle()

            try:
                lastpos = 0 if lastdate == "" else self.secondcandle.candle.index.get_loc(
                    lastdate)  # 前回までで書き込み済みの足の位置を探す
            except:
                self.logger.info(
                    "================================= can't find lastdate = {}".format(lastdate))
                self.logger.info("secondcandle.index = {}".format(
                    self.secondcandle.candle.index))
                lastpos = 0
            # 追加分(前回書き込み済み以降)だけの足を生成
            latestCandle = self.secondcandle.candle[lastpos:]

            # 負荷軽減のため、不要な変換済みの約定履歴を破棄
            self.secondcandle.reduce_exeution_buffer()
            self.secondcandle.candleupdated.clear()                      # １秒足のローソク足取得完了

            # 一番最後の足（未確定足）を記憶
            lastdate = self.secondcandle.candle[-1:].index[0]

            # candle_poolの最後の足（未確定）をカット
            self.candle_pool = self.candle_pool[:-1]
            self.candle_pool = self.candle_pool.append(
                latestCandle)   # candle_poolに追加 (確定足のみが入っている)

            # 必要な長さだけにカットする
            length = min((self.candlelength*self.timescale) +
                         2, len(self.candle_pool))
            self.candle_pool = self.candle_pool[-length:]

            # 前回ローソク足更新時の最後の足からtimescale進んだ足が入っていればローソク足の更新作業を行う
            if self.secondsfromlastupdate() >= self.timescale:
                # 現在足の更新
                self._current_ohlc = {'exec_date': self.secondcandle.current_exec_date,
                                      'open': self.secondcandle.current_open,
                                      'high': self.secondcandle.current_high,
                                      'low': self.secondcandle.current_low,
                                      'close': self.secondcandle.current_close,
                                      'volume': self.secondcandle.current_volume,
                                      'buy': self.secondcandle.current_buy_volume,
                                      'sell': self.secondcandle.current_sell_volume,
                                      'count': self.secondcandle.current_count,
                                      'count_buy': self.secondcandle.current_buy_count,
                                      'count_sell': self.secondcandle.current_sell_count,
                                      'total_value': self.secondcandle.current_total_value}
                self.secondcandle.current_open = self.secondcandle.current_close
                self.secondcandle.current_high = self.secondcandle.current_close
                self.secondcandle.current_low = self.secondcandle.current_close
                self.secondcandle.current_volume = 0
                self.secondcandle.current_buy_volume = 0
                self.secondcandle.current_sell_volume = 0
                self.secondcandle.current_count = 0
                self.secondcandle.current_buy_count = 0
                self.secondcandle.current_sell_count = 0
                self.secondcandle.current_total_value = 0

                # １秒足からターゲットの秒数の足を生成
                self.candle = self.candle_pool.resample(str(self.timescale)+"s").agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "sum", "buy": "sum", "sell": "sum",
                                                                                      "count": "sum", "count_buy": "sum", "count_sell": "sum", "total_value": "sum"})
                candle_timestamp = self.candle[-1:].index[0]

                # candleの最後の足（未確定）をカット
                self.candle = self.candle[:-1]

                # 必要な長さだけにカットする
                length = min(self.candlelength, len(self.candle))
                self.candle = self.candle[-length:]

                if self.lastcandle != candle_timestamp:
                    self.lastcandle = candle_timestamp
                    self.candleupdated.set()

            # 稼働確認用 WatchDogTimer
            self.wdt = time.time()

        self.running = False

# GenerateTargetCandleクラスをスレッドとして起動してコントロールするクラス
#    スレッドが停止している場合に再稼働させる機能つき


class CandleThread:
    def __init__(self, logger, product, timescale, candlelength, parameters):
        self.logger = logger
        self.product = product
        self.timescale = timescale
        self.candlelength = candlelength
        self._parameters = parameters
        self.__startwebsock()

    def __startwebsock(self):
        self.gencandle = GenerateTargetCandle(
            self.logger, self.product, self.timescale, self.candlelength, self._parameters)
        self.candle_thread = Thread(target=self.gencandle.main_loop)
        self.candle_thread.start()

    @property
    def candle(self):
        return self.gencandle.candle

    @property
    def secondsfromlastupdate(self):
        return self.gencandle.secondsfromlastupdate()

    @property
    def current_latency(self):
        return self.gencandle.current_latency

    @property
    def current_candle(self):
        return self.gencandle.current_ohlc

    def get_effective_tick(self, size_thru, startprice, limitprice):
        return self.gencandle.secondcandle.get_effective_tick(size_thru, startprice, limitprice)

    def get_board(self):
        return self.gencandle.secondcandle.get_board()

    def get_spot_board(self):
        return self.gencandle.secondcandle.get_spot_board()

    @property
    def mid_price(self):
        return self.gencandle.mid_price

    @property
    def spot_price(self):
        return self.gencandle.spot_price

    @property
    def spot_price_exec(self):
        return self.gencandle.spot_price_exec

    @property
    def board_age(self):
        return self.gencandle.board_age

    def checkactive(self):
        if time.time()-self.gencandle.wdt > 20:         # WatchDogTimerでチェック
            #            self.gencandle.stopflag = True               # 念のため停止指示
            self.logger.error("Candle Thread is Stopped!!!!")
#            self.gencandle = None
#            self.logger.info( "Thread is Destroyed" )
#            time.sleep(10)
#            self.__startwebsock()
#            self.logger.info( "Thread is Rebooted" )

    def clearevent(self):
        self.gencandle.candleupdated.clear()

    def waitupdate(self):
        if self.timescale == 0 and hasattr(self.gencandle, "candle"):
            return

        counter = 0
        # candleupdateのイベントが発生するまで待つ (10秒に1回activecheck)
        while self.gencandle.candleupdated.wait(0.5) == False:
            counter = (counter+1) % 20
            if counter == 0:
                self.checkactive()
        self.logger.debug("{:.3f}msec from last execution received".format(
            (time.time() - self.gencandle.lastexecutiontime)*1000))
        self.clearevent()

    def stopthread(self):
        self.logger.info("Stopping thread")
        self.gencandle.stopflag = True
        self.gencandle.secondcandle.candleupdated.set()
        while self.gencandle.running:
            time.sleep(1)
            self.logger.info("Waiting Thread stop")
        self.logger.info("Thread stopped")
