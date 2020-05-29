# coding: utf-8
from collections import deque
import pandas
import traceback
import requests
import sys
import time
import signal
import math
import os
from logging import getLogger, ERROR, WARNING, INFO, DEBUG, StreamHandler, FileHandler, Formatter
import json
import websocket
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from threading import Thread, Lock
from libs import cryptowatch
from libs import bfserver
from libs import bforder
from libs import plotgraph
from libs import candlegen
from libs import parameters
try:
    from pybitflyer import pybitflyer_f as pybitflyer
except:
    import pybitflyer
from sortedcontainers import SortedDict
import zipfile
import importlib.machinery as imm
from libs.base_strategy import Strategy
version_str = "Ver6.41"

pandas.set_option('display.expand_frame_repr', False)


# Influx DBとの接続（もしインストールされていれば）
try:
    from influxdb import InfluxDBClient
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except:
    pass

# Discordライブラリの初期化（もしインストールされていれば）
try:
    import discord
    discord_client = discord.Client()
except:
    discord_client = None

try:
    @discord_client.event
    async def on_ready():
        try:
            trade._logger.info('Logged to Discord in as {}'.format(
                discord_client.user.name))
        except Exception as e:
            trade._logger.exception(
                "Error in on_ready routine : {}, {}".format(e, traceback.print_exc()))
except:
    pass

try:
    @discord_client.event
    async def on_message(message):
        try:
            # we do not want the bot to reply to itself
            if message.author == discord_client.user:
                return
            if trade._parameters.on_message_handler != None:
                await trade._strategy.discord_on_message(message)
        except Exception as e:
            trade._logger.exception(
                "Error in on_message routine : {}, {}".format(e, traceback.print_exc()))

    @discord_client.event
    async def on_reaction_add(reaction, user):
        try:
            # we do not want the bot to reply to itself
            if user == discord_client.user:
                return
            if trade._parameters.on_reaction_add_handler != None:
                await trade._strategy.discord_on_reaction_add(reaction, user)
        except Exception as e:
            trade._logger.exception(
                "Error in on_reaction_add routine : {}, {}".format(e, traceback.print_exc()))
except:
    pass


def setup_logger():
    logger = getLogger(__name__)
    logger.setLevel(DEBUG)
    handler = StreamHandler()
    handler.setFormatter(Formatter(
        fmt='%(asctime)s.%(msecs)03d:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    handler.setLevel(INFO)      # Consoleに表示するのはINFO以上
    logger.addHandler(handler)
    return logger


last_day = '00'
console_output_flag = True
file_log_level = ''
log_filename = ''


def update_filehandler(logger, log_folder, console_output, log_level):
    global last_day
    global console_output_flag
    global file_log_level
    global log_filename

    # 日付が変わったら出力ファイルを変更
    day = time.strftime("%d")
    if last_day != day or console_output_flag != console_output or file_log_level != log_level:

        # 登録されているlogger.handlersをすべて除去
        for h in logger.handlers[0:]:
            logger.removeHandler(h)

        # Consoleへの出力ハンドラ（console_output=Falseなら代わりにファイルへ出力する)
        if console_output:
            handler = StreamHandler()
            handler.setFormatter(Formatter(
                fmt='%(asctime)s.%(msecs)03d:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            handler.setLevel(INFO)      # Consoleに表示するのはINFO以上
            logger.addHandler(handler)
        else:
            if os.path.exists(log_folder+'console.txt'):
                os.remove(log_folder+'console.txt')
            handler = FileHandler(log_folder+'console.txt')
            handler.setFormatter(Formatter(
                fmt='%(asctime)s.%(msecs)03d:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            handler.setLevel(INFO)      # Consoleに表示するのはINFO以上
            logger.addHandler(handler)

        # ログファイルへの出力ハンドラ
        previous_filename = log_filename
        log_filename = 'trade' + time.strftime('%Y-%m-%d')

        # ファイルの日付が変わっているときだけ以前のログの圧縮を行う
        if previous_filename == log_filename:
            previous_filename = ''

        fh = FileHandler(log_folder + log_filename + '.log')
        fh.setFormatter(Formatter(
            fmt='%(asctime)s.%(msecs)03d[%(levelname)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        fh.setLevel(ERROR if log_level == 'ERROR' else (
            WARNING if log_level == 'WARNING' else (INFO if log_level == 'INFO' else DEBUG)))
        logger.addHandler(fh)
        last_day = day
        console_output_flag = console_output
        file_log_level = log_level

        logger.info("Initialize logger : BFS-X {}".format(version_str))

        # ログの圧縮を別スレッドで起動
        if previous_filename != '':
            thread_zip = Thread(target=ziplog, args=(
                log_folder, previous_filename))
            thread_zip.start()


def ziplog(log_folder, previous_filename):
    print(log_folder, previous_filename)
    with zipfile.ZipFile(log_folder + previous_filename + '.zip', 'w') as log_zip:
        log_zip.write(log_folder + previous_filename + '.log',
                      arcname=previous_filename + '.log', compress_type=zipfile.ZIP_DEFLATED)
    os.remove(log_folder + previous_filename + '.log')


# 実トレード用クラス


class trade:
    def __init__(self, logger, parameters, strategy_py_file):

        # board(SortedDict)にdの板情報を挿入(削除)
        def update_board(board, d):
            for i in d:
                p, s = i['price'], i['size']
                if s != 0:
                    board[p] = s
                elif p in board:
                    del board[p]

        self._logger = logger
        self._parameters = parameters

        if self.product == 'BTC_JPY':
            self._minimum_order_size = 0.001
        else:
            self._minimum_order_size = 0.01

        if not os.path.exists(self._parameters._strategy['log_folder']):
            os.makedirs(self._parameters._strategy['log_folder'])
        update_filehandler(self._logger, self._parameters._strategy['log_folder'], self._parameters._config['console_output'],
                           self._parameters._strategy['log_level'] if 'log_level' in self._parameters._strategy else 'DEBUG')

        # 動的に MyStrategy を読み込んでクラスを上書きする
        module_name = strategy_py_file.split('.')[0].replace('/', '.')
        module = imm.SourceFileLoader(
            module_name, strategy_py_file).load_module()
        self._logger.info(
            "Load MyStrategy class dynamically: module={}".format(module))
        strategy_class = getattr(module, 'MyStrategy')

        self._parameters._strategy_class = strategy_class(
            logger=self._logger, parent=self)
        self._logger.info('Succeeded setup strategy. logic={}, class={}'.format(
            strategy_py_file, type(self._parameters._strategy_class)))
        self._strategy = self._parameters._strategy_class
        self._strategy.set_strategy_config(
            self._parameters._strategy['parameters'])
        self._parameters.order_signal_event = self._strategy.order_signal_event
        self._parameters.logic_execution_event = self._strategy.execution_event
        self._parameters.spot_ticker_event = self._strategy.spot_ticker_event

        # 売買用クラス
        self._api = pybitflyer.API(
            self._parameters._config['apikey'], self._parameters._config['secret'])
        self._order = bforder.order(
            self._logger, self._api, self._parameters, self)

        # ローソク足生成クラスの作成
        self._candlegen = candlegen.CandleThread(
            logger, self.product, self._parameters._strategy['timescale'], self._parameters._strategy['numOfCandle'], self._parameters)

        # サーバーステータスチェック用クラス
        self._server_status = bfserver.Health(self._logger, self._parameters)

        # CryptoWatchデータ取得クラス
        self.cryptowatch = cryptowatch.CryptoWatch()
        self.lock = Lock()
        self.apilock = Lock()
        self._ctyptowatch_timestamp = 0
        self._ctyptowatch_updatedtime = 0
        if self._parameters.cryptowatch_candle != 0:
            self._fetch_cryptowatch()  # 初回の読み込み

        # 初回の板情報はAPIから読み込んで構築
        recept_data = self._get_board_api()
        self._candlegen.gencandle.secondcandle.mid_price = self._candlegen.gencandle.secondcandle.spot_price = self._candlegen.gencandle.secondcandle.spot_price_exec = recept_data[
            'mid_price']
        with self._candlegen.gencandle.secondcandle.board_lock:
            bids, asks = SortedDict(), SortedDict()  # 空のSortedDictを作って
            update_board(bids, recept_data['bids'])  # すべてのmessageを
            update_board(asks, recept_data['asks'])  # 突っ込む
            self._candlegen.gencandle.secondcandle.bids, self._candlegen.gencandle.secondcandle.asks = bids, asks

        # ポジション履歴のグラフ生成クラス
        self._plot_graph = plotgraph.PositionGraph(
            self._logger, self._api, self._parameters)

        # 初回の初期化動作
        self._strategy.initialize_logic()

        # InfluxDBサーバーとの接続
        try:
            self._influx_client = InfluxDBClient(
                host='kumo.tokyo', port=8085, database='bots', ssl=True, username='bfsuser', password='bfsx')
        except Exception as e:
            self._logger.info(e)
            self._influx_client = None
        if self._influx_client != None:
            Thread(target=self._influx_thread).start()

        # リアルタイムロジック用の関数登録
        try:
            self._parameters.execution_handler = self._strategy.executions
        except:
            pass
        try:
            self._parameters.board_updated_handler = self._strategy.board_updated
        except:
            pass
        try:
            self._parameters.spot_execution_handler = self._strategy.spot_executions
        except:
            pass
        try:
            self._parameters.spot_board_updated_handler = self._strategy.spot_board_updated
        except:
            pass
        try:
            self._parameters.on_message_handler = self._strategy.discord_on_message
        except:
            pass
        try:
            self._parameters.on_reaction_add_handler = self._strategy.discord_on_reaction_add
        except:
            pass

        self._parameters.start_position_thread()

    # ランキングInfluxDBサーバーへ損益を送るスレッド
    def _influx_thread(self):
        self._influx_last_send_minutes = int(time.time()/60)
        while True:
            time.sleep(40)  # 40秒に1回のチェックは適当に送信時刻（秒）がばらけるように
            if self._influx_last_send_minutes == int(time.time()/60):
                continue          # 前回と分が変わっていなければなにもしない
            self._influx_last_send_minutes = int(time.time()/60)
            interval = self._parameters._strategy['ranking_report_interval'] if 'ranking_report_interval' in self._parameters._strategy else 5
            if self._influx_last_send_minutes % interval == 0 or time.strftime("%M") == "23:55" or time.strftime("%M") == "00:05":
                try:
                    if 'ranking_botname' in self._parameters._strategy and 'ranking_discord_id' in self._parameters._strategy:
                        self._logger.info(
                            "sending profit to ranking server  [current profit: {}]".format(int(self._profit)))
                        self._influx_client.write_points([{"measurement": "profit", "tags": {'bot': self._parameters._strategy['ranking_botname'], "uid":int(
                            self._parameters._strategy['ranking_discord_id']), }, "fields":{self._parameters._strategy['ranking_botname']:int(self._profit)}}])
                        self._influx_client.write_points([{"measurement": "ranking", "tags": {'bot': self._parameters._strategy['ranking_botname'], "uid":int(
                            self._parameters._strategy['ranking_discord_id']), }, "fields":{"profit": int(self._profit)}}])
                except Exception as e:
                    self._logger.error(
                        'Failed sending information to InfluxDB: {}'.format(e))

    @property
    def product(self):
        return self._parameters._config['product']

    @property
    def _execution_timestamp(self):
        return self._parameters.execution_timestamp

    @property
    def _board_timestamp(self):
        return self._parameters.board_timestamp

    @property
    def _is_backtesting(self):
        return False

    @property
    def no_trade_period(self):
        return self._parameters.no_trade_period

    @property
    def _candle_date(self):
        return self._candlegen.candle.index[-1]

    @property
    def _candle_date_list(self):
        return self._candlegen.candle.index         # 日本時間のdatetimeクラス群

    @property
    def _exec_date(self):
        return self._candlegen.current_candle['exec_date']

    @property
    def _open(self):
        return self._candlegen.candle['open']

    @property
    def _high(self):
        return self._candlegen.candle['high']

    @property
    def _low(self):
        return self._candlegen.candle['low']

    @property
    def _close(self):
        return self._candlegen.candle['close']

    @property
    def _volume(self):
        return self._candlegen.candle['volume']

    @property
    def _buy_volume(self):
        return self._candlegen.candle['buy']

    @property
    def _sell_volume(self):
        return self._candlegen.candle['sell']

    @property
    def _count(self):
        return self._candlegen.candle['count']

    @property
    def _buy_count(self):
        return self._candlegen.candle['count_buy']

    @property
    def _sell_count(self):
        return self._candlegen.candle['count_sell']

    @property
    def _total_value(self):
        return self._candlegen.candle['total_value']

    @property
    def _pos(self):
        current_position = self._parameters.estimated_position2  # 想定ポジション
        return round(current_position, 8)

    @property
    def _average(self):
        return round(self._parameters.counted_average_price)

    @property
    def _profit(self):
        return self._parameters.estimated_profit+self._profit_unreal

    @property
    def _fixed_profit(self):
        return self._parameters.estimated_profit

    def _reset_profit(self):
        day_fixed = -self._parameters.estimated_profit - self._profit_unreal
        self._parameters.estimated_profit = -self._profit_unreal
        self._order.save_current_profit(False, day_fixed)

    @property
    def _profit_unreal(self):
        return round((self._ltp-self._parameters.counted_average_price)*self._parameters.counted_position)

    @property
    def _server_latency(self):
        return self._parameters.latency_history[-1]

    @property
    def _server_latency_rate(self):
        return self._plot_graph.getLatencyRate()

    @property
    def _server_health(self):
        return self._parameters.server_health

    @property
    def _ltp(self):
        return self._parameters.ltp

    @property
    def _sfd_commission(self):
        return self._parameters.sfd_commission

    @property
    def _sfd(self):
        if self._parameters.ltp >= self.spot_price:
            return round(self._parameters.ltp/self.spot_price*100-100, 3) if self.spot_price != 0 else 0
        else:
            return -round(self.spot_price/self._parameters.ltp*100-100, 3) if self._parameters.ltp != 0 else 0

    @property
    def _spot(self):
        return self.spot_price

    @property
    def _spot_exec(self):
        return self.spot_price_exec

    @property
    def _best_ask(self):
        return self._parameters.best_ask

    @property
    def _best_bid(self):
        return self._parameters.best_bid

    @property
    def _current_candle(self):
        return self._candlegen.current_candle

    @property
    def _from_lastcandle_update(self):
        return self._candlegen.secondsfromlastupdate

    @property
    # Private API の呼出は 5 分間で 500 回を上限とします。上限に達すると呼出を一定時間ブロックします。また、ブロックの解除後も呼出の上限を一定時間引き下げます。
    def _api_count_per_user(self):
        return(500-self._api.LimitRemaining)

    @property
    # 同一 IP アドレスからの API の呼出は 5 分間で 500 回を上限とします。上限に達すると呼出を一定時間ブロックします。また、ブロックの解除後も呼出の上限を一定時間引き下げます。
    def _api_count_per_ip(self):
        return(500-self._server_status._publicapi.LimitRemaining)

    @property
    # Private API のうち、以下の API の呼出(order/cancelall)は 5 分間で合計 300 回を上限とします。上限に達すると、これらの API の呼出を一定時間ブロックします。また、ブロックの解除後も呼出の上限を一定時間引き下げます。
    def _api_order_count_per_user(self):
        return(300-self._api.OrderLimitRemaining)

    @property
    # 0.1 以下の数量の注文は、すべての板の合計で 1 分間で 100 回を上限とします。上限に達するとその後 1 時間は 1 分間で 10 回まで注文を制限します。
    def _api_count2(self):
        return sum(self._parameters.api_counter_small_order)

    def _parentorder(self, order_method, params, time_in_force="GTC"):
        if self._parameters._strategy['close_position'] or self.no_trade_period:
            self._logger.info(
                '          PARENT order will not execute because of close_position flag!!!')
            return ''

        res = self._order.sendparentorder(
            order_method=order_method, params=params, time_in_force=time_in_force)
        self._logger.info(
            '        Send Parent Order [{}]  {})'.format(order_method, res))

        return res

    def _limit_buy(self, price, size, time_in_force="GTC"):
        if round(self._pos, 2) >= 0 and (self._parameters._strategy['close_position'] or self.no_trade_period):
            self._logger.info(
                '          BUY order will not execute because of close_position flag!!!')
            return ''
        id = self._order.buy_order_limit(
            size=size, price=price, time_in_force=time_in_force)
        self._logger.info(
            '        BUY!!!  (price:{:.0f} size:{:.8f}  {})'.format(price, size, id))
        return id

    def _limit_sell(self, price, size, time_in_force="GTC"):
        if round(self._pos, 2) <= 0 and (self._parameters._strategy['close_position'] or self.no_trade_period):
            self._logger.info(
                '          SELL order will not execute because of close_position flag!!!')
            return ''
        id = self._order.sell_order_limit(
            size=size, price=price, time_in_force=time_in_force)
        self._logger.info(
            '        SELL!!! (price:{:.0f} size:{:.8f} {})'.format(price, size, id))
        return id

    def _market_buy(self, size, nocheck=False):
        if round(self._pos, 2) >= 0 and (self._parameters._strategy['close_position'] or self.no_trade_period):
            self._logger.info(
                '          MARKET BUY order will not execute because of close_position flag!!!')
            return ''
        id = self._order.buy_order_market(size=size, nocheck=nocheck)
        self._logger.info(
            '        MARKET BUY!!! (size:{:.8f} {})'.format(size, id))
        return id

    def _market_sell(self, size, nocheck=False):
        if round(self._pos, 2) <= 0 and (self._parameters._strategy['close_position'] or self.no_trade_period):
            self._logger.info(
                '          MARKET SELL order will not execute because of close_position flag!!!')
            return ''
        id = self._order.sell_order_market(size=size, nocheck=nocheck)
        self._logger.info(
            '        MARKET SELL!!! (size:{:.8f} {})'.format(size, id))
        return id

    def _close_position(self):
        if self._pos >= self._minimum_order_size:
            id = self._strategy._market_sell(self._pos)
            self._logger.info('        Emergency SELL!!! ({})'.format(id))
            if ("status" in id or not id or (id and not "JRF" in str(id))):
                return False
            return True
        elif self._pos <= -self._minimum_order_size:
            id = self._strategy._market_buy(-self._pos)
            self._logger.info('        Emergency BUY!!! ({})'.format(id))
            if ("status" in id or not id or (id and not "JRF" in str(id))):
                return False
            return True

    def _cancel_all_orders(self):
        self._logger.info('        Cancel all orders!!! ({})'.format(
            self._order.cancel_all_orders()))

    def _cancel_childorder(self, id):
        self._logger.info('        Cancel child orders!!! [{}] ({})'.format(
            id, self._order.cancel_childorder(id)))

    def _cancel_parentorder(self, id):
        self._logger.info('        Cancel parent orders!!! [{}] ({})'.format(
            id, self._order.cancel_parentorder(id)))

    def _get_effective_tick(self, size_thru, startprice, limitprice):
        return self._candlegen.get_effective_tick(size_thru, startprice, limitprice)

    def _get_board(self):
        return self._candlegen.get_board()

    def _get_spot_board(self):
        return self._candlegen.get_spot_board()

    @property
    def mid_price(self):
        return self._candlegen.mid_price

    @property
    def spot_price(self):
        return self._candlegen.spot_price

    @property
    def spot_price_exec(self):
        return self._candlegen.spot_price_exec

    @property
    def board_age(self):
        return self._candlegen.board_age

    def _get_board_api(self):
        return self._server_status.board()

    def _get_positions(self):
        return [{'id': p['id'][:-5], 'price':int(p['price']), 'size':p['size'], 'side':p['side'], 'timestamp':p['timestamp']} for p in self._parameters.current_position_list]

    @property
    def log_folder(self):
        return self._parameters._strategy['log_folder']

    @property
    def executed_history(self):
        return deepcopy(list(self._parameters.executed_order_history))

    def _fetch_cryptowatch(self, minutes=0):
        # ２重起動の禁止
        if self.apilock.locked():
            return

        with self.apilock:
            if self.product == 'FX_BTC_JPY':
                market = 'bitflyer/btcfxjpy'
            elif self.product == 'BTC_JPY':
                market = 'bitflyer/btcjpy'
            else:
                market = ''

            if market != '':
                candle_minutes = self._parameters.cryptowatch_candle if minutes == 0 else minutes
                # 指定が無い場合には最大数取得（今までと同じ）
                numofcandle = self._parameters._strategy[
                    'cryptowatch_numOfCandle'] if 'cryptowatch_numOfCandle' in self._parameters._strategy else 10000

                if self._ctyptowatch_timestamp == 0 or self._parameters.use_lightning_candle == False:
                    try:
                        # 初回は Cryptowatchで取得
                        self._candle_pool = self.cryptowatch.getCandle(
                            candle_minutes*60, market, numofcandle=numofcandle, fill=self._parameters._strategy['fill_nan'])

                        if self._candle_pool is not None:
                            with self.lock:
                                self._cryptowatch_candle = deepcopy(
                                    self._candle_pool)
                            if self._ctyptowatch_timestamp != self._cryptowatch_candle.index[-1].timestamp():
                                self._ctyptowatch_lastindex = self._cryptowatch_candle.index[-1]
                                self._ctyptowatch_timestamp = self._ctyptowatch_lastindex.timestamp()
                                # Cryptowatchのローソク足が更新されたタイミングを保管（次の取得タイミングを計るため
                                self._ctyptowatch_updatedtime = time.time()

                    except Exception as e:
                        self._logger.exception("Error while fetching cryptowatch candles : {}, {}".format(
                            e, traceback.print_exc()))
                else:
                    try:
                        # lightningAPIからローソク足を取得
                        # 過去のローソク足
                        responce1 = requests.get("https://lightchart.bitflyer.com/api/ohlc?symbol={}&period=m&before={}000".format(
                            self.product, int(datetime.now().timestamp()))).json()
                        # 直近の未確定足を含むローソク足
                        responce2 = requests.get(
                            "https://lightchart.bitflyer.com/api/ohlc?symbol={}&period=m".format(self.product)).json()
                        # それぞれをターゲットの長さにリサンプリング
                        candle1 = pandas.DataFrame([[datetime.fromtimestamp(candle[0]/1000, timezone(timedelta(hours=9), 'JST')), candle[1], candle[2], candle[3], candle[4], candle[5]] for candle in responce1], columns=[
                                                   "date", "open", "high", "low", "close", "volume"]).set_index('date').resample(str(candle_minutes*60)+"s").agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "sum"})
                        candle2 = pandas.DataFrame([[datetime.fromtimestamp(candle[0]/1000, timezone(timedelta(hours=9), 'JST')), candle[1], candle[2], candle[3], candle[4], candle[5]] for candle in responce2], columns=[
                                                   "date", "open", "high", "low", "close", "volume"]).set_index('date').resample(str(candle_minutes*60)+"s").agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "sum"})
                        # その後合成（両方に含まれる足のボリュームが足されないようにvolumは"max"でリサンプリング
                        candle = candle1.append(candle2).resample(str(candle_minutes*60)+"s").agg({
                            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "max"})
                        # 前回までで書き込み済みの足の位置を探す
                        lastpos = candle.index.get_loc(
                            self._ctyptowatch_lastindex)
                        # candle_poolの最後の足（未確定）をカット
                        self._candle_pool = self._candle_pool[:-1]
                        # APIから取得したローソク足を継ぎ足す
                        self._candle_pool = self._candle_pool.append(
                            candle[lastpos:])
                        # 必要な長さだけにカットする
                        self._candle_pool = self._candle_pool[-min(
                            numofcandle, len(self._candle_pool)):]

                        if self._parameters._strategy['fill_nan'] == True:
                            # 欠損データの補完(4時のメンテナンス時など）
                            candle_index = self._candle_pool.index.values
                            for i in range(1, len(candle_index)):
                                # NaNが自身との等号判定でfalseを返すという性質を利用してNanかどうかを判定
                                if self._candle_pool.at[candle_index[i], "open"] != self._candle_pool.at[candle_index[i], "open"]:
                                    # その期間に約定履歴が無い場合にはひとつ前の足からコピー
                                    self._candle_pool.loc[candle_index[i], [
                                        "open", "high", "low", "close"]] = self._candle_pool.at[candle_index[i-1], "close"]
                        else:
                            # 欠損データの削除(4時のメンテナンス時など）
                            self._candle_pool = self._candle_pool.dropna()

                        self._logger.info("fetch from lightning API {}".format(
                            self._candle_pool.index[-1]))

                        if self._ctyptowatch_lastindex != self._candle_pool.index[-1]:
                            self._logger.debug(
                                "fetch from lightning API responce1 : {}".format(responce1))
                            self._logger.debug(
                                "fetch from lightning API responce2 : {}".format(responce2))
                            with self.lock:
                                self._cryptowatch_candle = deepcopy(
                                    self._candle_pool)
                            self._ctyptowatch_lastindex = self._cryptowatch_candle.index[-1]
                            self._ctyptowatch_timestamp = self._ctyptowatch_lastindex.timestamp()
                            self._ctyptowatch_updatedtime = time.time()

                    except Exception as e:
                        self._logger.exception("Error while fetching lightning API candles : {}, {}".format(
                            e, traceback.print_exc()))

                        # エラーの時には Cryptowatchで取得
                        self._candle_pool = self.cryptowatch.getCandle(
                            candle_minutes*60, market, numofcandle=numofcandle, fill=self._parameters._strategy['fill_nan'])

                        if self._candle_pool is not None:
                            with self.lock:
                                self._cryptowatch_candle = deepcopy(
                                    self._candle_pool)
                            if self._ctyptowatch_timestamp != self._cryptowatch_candle.index[-1].timestamp():
                                self._ctyptowatch_lastindex = self._cryptowatch_candle.index[-1]
                                self._ctyptowatch_timestamp = self._ctyptowatch_lastindex.timestamp()
                                # Cryptowatchのローソク足が更新されたタイミングを保管（次の取得タイミングを計るため
                                self._ctyptowatch_updatedtime = time.time()

    def _get_cryptowatch(self):
        with self.lock:
            candle = deepcopy(self._cryptowatch_candle)
        return candle

    def _send_discord(self, message, image_file=None):
        try:
            if self._parameters._strategy['position_discord_webhooks'] != '':
                payload = {'content': ' {} '.format(message)}
                if image_file == None:
                    r = requests.post(
                        self._parameters._strategy['position_discord_webhooks'], data=payload, timeout=10)
                else:
                    try:
                        file = {'imageFile': open(image_file, "rb")}
                        r = requests.post(
                            self._parameters._strategy['position_discord_webhooks'], data=payload, files=file, timeout=10)
                    except:
                        r = requests.post(
                            self._parameters._strategy['position_discord_webhooks'], data=payload, timeout=10)
                if r.status_code == 204:
                    # 正常終了
                    return
                elif r.status_code == 404:
                    self._logger.error('Discord URL is not exist')
        except Exception as e:
            self._logger.error('Failed sending image to Discord: {}'.format(e))
            time.sleep(1)

    def _get_balance(self, refresh):
        if refresh:
            try:
                positions = self._api.getbalance()
                for pos in positions:
                    if 'currency_code' in pos and pos['currency_code'] == 'JPY':
                        self._parameters.balance = pos
            except:
                pass

        return self._parameters.balance

    def _getcollateral_api(self):
        return self._order._getcollateral_api()

    @property
    def _initial_collateral(self):
        return self._plot_graph._initial_collateral

    @property
    def _ordered_list(self):
        order_info = deepcopy(
            list(self._parameters.childorder_information))
        return order_info

    @property
    def _parentorder_ordered_list(self):
        order_info = deepcopy(list(self._parameters.parentorder_id_list))
        return order_info

    def run(self):
        # 最初の足が確定する瞬間まで待機にはいる
        self._logger.info('Waiting First Candle')
        self._candlegen.waitupdate()

        last_check_position = 0
        self.position_diff_history = deque([0], maxlen=500)

        pending_time = self.api_pending_time = time.time()
        current_sec = 0
        current_min = 0

        if self._strategy.sim_mode == False:
            self._order._getpositions_api()
        while True:
            # リアルタイムロジックのストラテジーのハンドラーが登録されていればイベントでrealtime_logic()を呼び出す
            if self._parameters.execution_handler != None:
                if self._strategy.order_signal_event.wait(self._parameters._strategy['logic_loop_period']):
                    if time.time() > pending_time and time.time() > self.api_pending_time:
                        # サーバーが取引可能なステータスで無ければ取引しない
                        if self._parameters.server_health not in self._parameters._strategy['normal_state']:
                            self._logger.info('          Server busy. No order.  Status{}'.format(
                                self._parameters.server_health))
                        else:
                            # 売買処理
                            try:
                                self._strategy.realtime_logic()
                            except Exception as e:
                                self._logger.exception(
                                    "Error in realtime_logic routine : {}, {}".format(e, traceback.print_exc()))

                    self._strategy.order_signal_event.clear()

            else:
                # logic_loop_period秒経過するか、ローソク足確定の2秒程度前までループ (2秒前にループを抜けるのはローソク足確定前にサーバーステータスチェックのapiなど呼び出しを済ませておいて、ローソク足確定後すぐに取引に入りたいから）
                start_time = int(time.time(
                )/self._parameters._strategy['logic_loop_period'])*self._parameters._strategy['logic_loop_period']
                while (time.time()-start_time) < self._parameters._strategy['logic_loop_period'] and (self._candlegen.secondsfromlastupdate < self._parameters._strategy['timescale']-2 or self._parameters._strategy['timescale'] <= 3):
                    # 1秒ごとに
                    if self._parameters.execution_event.wait(1) == True:
                        # 約定済みリストと発注済みリストを突き合わせて現在ポジを計算
                        self._order.update_current_position()

            # 各種ステータスチェック
            # 約定済みリストと発注済みリストを突き合わせて現在ポジを計算
            self._order.update_current_position()

            # 以下は1秒に1回だけ実施
            if current_sec != int(time.time()):
                # 前回の問い合わせからinterval_health_check(秒)経っていればサーバーヘルスを取得するスレッドを起動
                if (time.time()-self._server_status._timelast) > self._parameters._config['interval_health_check']:
                    server_healh_check_thread = Thread(
                        target=self._server_status.status, args=())               # サーバーのステータスチェック
                    server_healh_check_thread.start()

                self._candlegen.checkactive()

            # リアルタイムロジックのストラテジーでなければローソク足確定のタイミングでまで待つ
            if self._parameters.execution_handler == None:
                # ローソク足確定の2秒以内前であればトリガー待ちにはいってターゲットの足が確定する瞬間まで待機にはいる
                if self._candlegen.secondsfromlastupdate > self._parameters._strategy['timescale']-3:
                    self._candlegen.waitupdate()

                if self._parameters.execution_event.is_set():                  # ここまでに約定済みのイベントがあれば
                    # 約定済みリストと発注済みリストを突き合わせて現在ポジを計算
                    self._order.update_current_position()

            if time.time() > pending_time:
                current_position = self._pos

                if current_sec != int(time.time()):  # 1秒に1回だけ実施
                    # ロスカットチェック
                    try:
                        if self._strategy.loss_cut_check():
                            # ポジションがhetpositionsに反映されるまでウェイト
                            pending_time = time.time(
                            )+parameters._strategy['emergency_wait']
                    except Exception as e:
                        self._logger.exception(
                            "Error in loss_cut_check routine: {}, {}".format(e, traceback.print_exc()))

                # 急騰時に含み損ならば緊急クローズ
                if((self._parameters.server_health in self._parameters._strategy['emergency_state'] or
                    self._plot_graph.getLatencyRate() > self._parameters._strategy['latency_limit'])
                        and (self._ltp-self._parameters.counted_average_price)*current_position < 0):
                    self._logger.info('          Emergency close.  Status{}  Delay{}msec'.format(
                        self._parameters.server_health, self._plot_graph.getLatencyRate()))
                    if self._close_position():
                        # ポジションがhetpositionsに反映されるまでウェイト
                        pending_time = time.time(
                        )+parameters._strategy['emergency_wait']

                # サーバーが取引可能なステータスで無ければ取引しない
                elif self._parameters.server_health not in self._parameters._strategy['normal_state']:
                    self._logger.info('          Server busy. No order.  Status{}'.format(
                        self._parameters.server_health))

                # pending_time の待機
                elif time.time() < pending_time:
                    pass

                # api_pending_time の待機
                elif time.time() < self.api_pending_time:
                    pass

                # close_positionモードで最後の残りかすは成りでクローズ
                elif self._parameters._strategy['close_position'] and abs(current_position) < self._parameters.close_lot and abs(current_position) >= self._minimum_order_size:
                    self._logger.info('          Position Close:{:.3f} ({})'.format(
                        current_position, self._close_position()))
                    # ポジションがhetpositionsに反映されるまでウェイト
                    pending_time = time.time(
                    )+parameters._strategy['emergency_wait']

                # リアルタイムロジックのストラテジーでなければローソク足確定のタイミングでlogic()を呼び出す
                elif self._parameters.execution_handler == None:
                    # 売買判断
                    try:
                        self._strategy.logic()
                    except Exception as e:
                        self._logger.exception(
                            "Error in logic routine : {}, {}".format(e, traceback.print_exc()))

            else:
                # 緊急クローズ後の保留期間
                self._logger.info('          Pending next {:.1f}sec'.format(
                    pending_time-time.time()))

            # Public APIの 5分間のapi残が10未満の場合 api_pending_time の待機
            if self._server_status._publicapi.LimitRemaining < 10:
                self._logger.error('          Public API counter Remaining : {:.0f}'.format(
                    self._server_status._publicapi.LimitRemaining))
                self.api_pending_time = time.time(
                )+self._server_status._publicapi.LimitPeriod  # api回数制限までノートレードで待機
                self._server_status._publicapi.LimitRemaining = 500

            # 5分間のapi残が10未満の場合 api_pending_time の待機
            if self._api.LimitRemaining < 10:
                self._logger.error('API counter Remaining : {:.0f}'.format(
                    self._api.LimitRemaining))
                self.api_pending_time = time.time()+self._api.LimitPeriod  # api回数制限までノートレードで待機
                self._api.LimitRemaining = 500

            # 5分間のapi残が10未満の場合 api_pending_time の待機
            if self._api.OrderLimitRemaining < 10:
                self._logger.error('API order counter Remaining : {:.0f}'.format(
                    self._api.OrderLimitRemaining))
                self.api_pending_time = time.time()+self._api.OrderLimitPeriod  # api回数制限までノートレードで待機
                self._api.OrderLimitRemaining = 300

            # 1分間の0.1以下の注文回数がapi_limit2を超えた場合 api_pending_time の待機
            if self._api_count2 > self._parameters._config['api_limit2']:
                self._logger.error(
                    'API2 counter : {:.0f}'.format(self._api_count2))
                # api回数制限が落ち着くまでノートレードで待機
                self.api_pending_time = time.time(
                ) + self._parameters._config['api_pending_time']

            # api_pending_time の待機
            if time.time() < self.api_pending_time:
                if self._parameters.close_position_while_no_trade == True:
                    self._order.update_current_position()  # 約定済みリストと発注済みリストを突き合わせて現在ポジを計算
                    self._close_position()    # 全ポジクローズ
                    time.sleep(20)            # 反映待ち
                self._logger.info('          API Pending next {:.1f}sec'.format(
                    self.api_pending_time-time.time()))

            # 定期的にCryptowatchからデータを取得(別スレッドにて)
            if self._parameters.cryptowatch_candle != 0:
                # ローソク足の変わる（であろう）ちょっと前から何回か読み続ける
                ctime = (time.time()-self._ctyptowatch_timestamp + 0.5)
                self._logger.debug(
                    "{:.1f} / {:.1f}".format(ctime, self._parameters.cryptowatch_candle*60))
                if(time.time()-self._ctyptowatch_updatedtime >= self._parameters.cryptowatch_candle*60 or ctime > self._parameters.cryptowatch_candle*60):
                    Thread(target=self._fetch_cryptowatch, args=()).start()

            # 定期的に発注済みリストをサーバーから取得
            if current_min != int(time.time()/60):  # 1分に1回
                thread_o = Thread(target=self._order.getchildorders, args=())
                thread_o.start()
#                self._order.save_current_profit(False, 0)

            # ポジション履歴グラフ生成
            self._plot_graph.notify_position_change(self._ltp)

            # loggerのファイルハンドラ更新(日付更新でログを切り替える)
            update_filehandler(self._logger, self._parameters._strategy['log_folder'], self._parameters._config['console_output'],
                               self._parameters._strategy['log_level'] if 'log_level' in self._parameters._strategy else 'DEBUG')

            # 定期的にパラメータの再読み込み
            if self._parameters.renew():
                self._strategy.set_strategy_config(
                    self._parameters._strategy['parameters'])

            # 30秒に一度、実際のAPIから取得したポジションを表示
            if last_check_position > int(time.time()) % 30 and self._strategy.sim_mode == False and self._parameters.adjust_position_with_api:
                base_position = self._parameters._config[
                    'base_position'] if 'base_position' in self._parameters._config else 0
                actual = self._order._getpositions_api() - base_position
                self._logger.info('(Diff:{:.8f})Actual Position : {:.8f}   Estimated Position  {:.8f}  Counted Position  {:.8f}'.format(
                    actual-self._pos, actual, self._pos, self._parameters.counted_position))

                # ズレの履歴を保存
                self.position_diff_history.append(round(actual-self._pos, 8))

                # 4度続けてポジションがズレていれば成売買で補正を行う
                if max(list(self.position_diff_history)[-4:]) == min(list(self.position_diff_history)[-4:]) and abs(actual-self._pos) >= self._minimum_order_size:
                    if actual-self._pos < 0:
                        id = self._strategy._market_buy(
                            self._pos-actual, nocheck=True)
                    else:
                        id = self._strategy._market_sell(
                            actual-self._pos, nocheck=True)
                    self._logger.info(
                        'Adjust Position : {:.8f}  (id:{})'.format(actual-self._pos, id))
            last_check_position = int(time.time()) % 30

            current_sec = int(time.time())
            current_min = int(time.time()/60)


# ^Cが押されたときに行う停止処理
def quit_loop(signal=signal.SIGINT, frame=0):
    logger.info('Stop bot because of keyboard interrupt')

    trade._order.update_current_position()
    trade._candlegen.stopthread

    retry = 3
    logger.info("Parent orders {}".format(parameters.parentorder_id_list))
    while parameters.parentorder_id_list and retry > 0:  # 発注済みのオーダーがすべてなくなるまで（中断時のポジずれ対策）
        # 発注済みの注文をすべてキャンセルする
        parentorder_id_list = deepcopy(parameters.parentorder_id_list)
        for parent_id in parentorder_id_list:
            trade._cancel_parentorder(parent_id)
            time.sleep(0.5)
        time.sleep(1)
        trade._order.update_current_position()
        retry -= 1

    retry = 3
    logger.info("Child orders {}".format(parameters.childorder_id_list))
    while parameters.childorder_id_list and retry > 0:  # 発注済みのオーダーがすべてなくなるまで（中断時のポジずれ対策）
        # 発注済みの注文をすべてキャンセルする
        childorder_id_list = deepcopy(parameters.childorder_id_list)
        for child_id in childorder_id_list:
            trade._cancel_childorder(child_id)
            time.sleep(0.5)

        time.sleep(3)
        old = parameters.estimated_position
        # 約定済みリストと発注済みリストを突き合わせて現在ポジを計算
        trade._order.update_current_position()
        logger.info(
            "          Position {:.4f} -> {:.4f}".format(old, parameters.estimated_position))
        retry -= 1

    # 終了直前の損益を更新
    trade._plot_graph._profit_all_history_append(trade._ltp)

    os._exit(0)


if __name__ == "__main__":
    # ^Cが押されたときのハンドラを登録
    signal.signal(signal.SIGINT, quit_loop)

    # ロガーの初期化
    logger = setup_logger()

    # パラメータ管理クラス
    parameters = parameters.Parameters(logger)

    # python trade.py
    if len(sys.argv) == 1:
        # configファイル読み込み
        parameters.load_config_file('trade.yaml')

    # python trade.py trade.yaml
    elif len(sys.argv) == 2:
        # configファイル読み込み
        parameters.load_config_file(sys.argv[1])

    # python trade.py strategy/strategy.py strategy/strategy.yaml
    elif len(sys.argv) == 3:
        # configファイル読み込み
        parameters.load_config_file('trade.yaml')
        # strategy_configファイル読み込み
        parameters.strategy_file = sys.argv[1]
        parameters.strategy_config_file = sys.argv[2]

    # python trade.py trade.yaml strategy/strategy.py strategy/strategy.yaml
    elif len(sys.argv) == 4:
        # configファイル読み込み
        parameters.load_config_file(sys.argv[1])
        # strategy_configファイル読み込み
        parameters.strategy_file = sys.argv[2]
        parameters.strategy_config_file = sys.argv[3]

    parameters.load_strategy_config_file(parameters.strategy_config_file)

    trade = trade(logger, parameters, parameters.strategy_file)

    Thread(target=trade.run).start()

    if 'discord_bot_token' in trade._parameters._strategy:
        if discord_client != None:
            logger.info('Start Discord bot')
            try:
                discord_client.loop.run_until_complete(discord_client.start(
                    trade._parameters._strategy['discord_bot_token']))
            except KeyboardInterrupt:
                logger.info("Received exit sig")
                quit_loop()
        else:
            logger.error('Discord bot is not active.')

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received exit sig")
            break

    quit_loop()
