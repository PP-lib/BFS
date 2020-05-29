# coding: utf-8
import json
import traceback
from collections import deque
import requests
import time
from threading import Event, Thread, Lock
from datetime import datetime, timedelta
from datetime import time as datetime_time
import copy
import yaml
import os
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM


class Parameters():
    def __init__(self, logger):
        self._logger = logger

        self.strategy_file = ''
        self.strategy_config_file = ''
        self._strategy = {}
        self._config = {}
        self._strategy_class = None

        # 複数のクラスからアクセスされる変数をここに置いています
        self.latency_history = deque([0], maxlen=600)
        self.superbusy_happend = False

        self.parentorder_id_list = deque(maxlen=1000)     # 発行済みの親注文ID（照合用のリスト）
        self.parentorder_method_dict = {}
        self.parentorder_detail_param = {}

        self.childorder_id_list = deque(maxlen=1000)     # 発行済みの子注文ID（照合用のリスト）
        self.childorder_information = deque(maxlen=1000)  # 発行済みの親注文IDとサイズ

        self.order_id_list_lock = Lock()

        # 約定判定済みのIDとサイズと価格 →　後でポジション管理へ回して処理
        self.executed_order = deque(maxlen=500)
        self.executed_order_lock = Lock()
        self.executed_order_history = deque(maxlen=100)  # 処理済みのデータ
        # キャンセル済みのID →　後でポジション管理へ回して処理
        self.canceled_child_order = deque(maxlen=500)
        self.canceled_parent_order = deque(
            maxlen=500)    # キャンセル済みのID →　後でポジション管理へ回して処理

        # 自分以外の約定を突っ込んでおく（acceptance_idをもらうよりも先にchild_orderイベントが来た場合の対応用）
        self.executed_order_pending = deque(maxlen=100)
        # 自分以外の約定を突っ込んでおく（acceptance_idをもらうよりも先にchild_orderイベントが来た場合の対応用）
        self.executed_order_pending_detail = deque(maxlen=100)
        self.executed_order_pending_rollback = False
        self.executed_order_pending_rollback_lock = Lock()

        self.server_accepted_time_lock = Lock()
        # acceptance_id をキーにしてオーダーやキャンセルの時刻を入れておく辞書（板乗り時間計測用）
        self.server_accepted_time_detail = deque(maxlen=2000)
        # acceptance_id だけを突っ込んでおく（該非判定用）
        self.cancel_child_id_list = deque(maxlen=200)

        self.childorders = []                    # 定期的にapiから取得するオーダーリスト

        self._estimated_position = 0             # 上記から推定されるポジション
        self.estimated_position2 = 0             # 上記から推定されるポジション
        self.estimated_profit = 0                # 計算上の利益(確定利益のみ)
        self.estimated_profit_unrealized = 0     # 計算上の利益(含み損益)

        self.current_position_list = deque(maxlen=2000)  # 建玉のリスト
        self.counted_position = 0                # 建玉のリストを集計したポジション
        self.counted_average_price = 0           # 建玉のリストを集計したポジション

        self.ltp = 0                             # LTP
        self.best_ask = 0                        # best_bid
        self.best_bid = 0                        # best_ask

        # mm関連
        self.execution_handler = None
        self.board_updated_handler = None
        self.spot_execution_handler = None
        self.spot_board_updated_handler = None
        self.execution_timestamp = time.time()
        self.board_timestamp = time.time()
        self.drive_by_executions = False
        self.drive_by_spot_ticker = False
        self.handle_spot_realtime_api = False

        self.ordered_count = deque([0], maxlen=61)               # 出した指値の数
        self.order_filled_count = deque([0], maxlen=61)         # 完全約定された数
        self.order_not_filled_count = deque([0], maxlen=61)     # 全く約定しなかった数
        self.order_partial_filled_count = deque([0], maxlen=61)  # 部分的に約定した数
        self.order_taked = deque([0], maxlen=61)                # 成り行きで約定した数
        self.order_retry_count = deque([0], maxlen=61)          # オーダーリトライの回数
        self.executed_size = deque([0], maxlen=61)              # 取引高
        self.executed_size_today = 0                           # 取引高

        self.execution_event = Event()
        self.execution_event.clear()

        self.api_sendorder_speed = deque(maxlen=5000)  # api速度 (プロット用・毎時クリア)
        self.api_getorder_speed = deque(maxlen=5000)  # api速度 (プロット用・毎時クリア)
        self.api_cancel_speed = deque(maxlen=5000)    # api速度 (プロット用・毎時クリア)

        self.execution_counter = deque(maxlen=60)  # api速度 (統計用・直近1分)
        self.api_sendorder_speed_history = deque(maxlen=60)  # api速度 (統計用・直近1分)
        self.ordered_speed_history = deque(maxlen=60)  # api速度 (統計用・直近1分)
        self.api_cancel_speed_history = deque(maxlen=60)  # api速度 (統計用・直近1分)
        self.canceled_speed_history = deque(maxlen=60)  # api速度 (統計用・直近1分)

        self.execution_counter.append(0)
        self.api_sendorder_speed_history.append(deque(maxlen=10))
        self.ordered_speed_history.append(deque(maxlen=10))
        self.api_cancel_speed_history.append(deque(maxlen=10))
        self.canceled_speed_history.append(deque(maxlen=10))

        self.all_latency_history = deque(maxlen=100000)
        self.server_latency_history = deque(maxlen=4000)
        self.server_order_delay_history = deque(maxlen=4000)
        self.server_cancel_delay_history = deque(maxlen=4000)
        self.slipage_history = deque(maxlen=20000)  # 約定時のオーダー価格との差

        # apiアクセス回数カウンター(300秒の累積アクセス数)
        self.api_counter = deque([0]*300, maxlen=300)
        self.api_counter_small_order = deque(
            [0]*60, maxlen=60)       # apiアクセス回数カウンター(60秒の累積アクセス数)

        # Cryptowatch
        self.cryptowatch_candle = 0
        self.use_lightning_candle = False

        # 現在がno_trade期間かどうか
        self.no_trade_period = False

        # リトライカウンター
        self.order_retry = 30
        self.cancel_retry = 10

        # Adjust Position
        self.adjust_position_with_api = False

        # Check cross trade
        self.check_cross_trade = True

        # 約定履歴が無い区間もダミーのローソク足を生成してlogic()を呼ぶかどうか
        self.renew_candle_everysecond = False

        self.server_health = "OTHER"

        self.collateral = {"collateral": 0, "open_position_pnl": 0,
                           "require_collateral": 0, "keep_rate": 0}

        self.balance = {"currency_code": "JPY", "amount": 0, "available": 0}

        self.position_event = Event()

        self.sfd_commission = 0
        self.sfd_profit = 0
        self.sfd_loss = 0

        # discord bot関連
        self.on_message_handler = None
        self.on_reaction_add_handler = None

    def start_position_thread(self):
        # ポジションをUDPで送信するスレッドで起動
        self.position_thread = Thread(target=self.send_position)
        self.position_thread.start()

    def send_position(self):
        self._logger.info("Start position thread")
        self.socket = socket(AF_INET, SOCK_DGRAM)
        while True:
            self.position_event.wait(10)
            self.position_event.clear()
            base_position = self._config['base_position'] if 'base_position' in self._config else 0
            message = "{:>10} : {:>15.8f} : {:>15.8f} : {:>+9.0f} : {:>3} : {:>3} : {}".format(
                self._config['product'][:10],
                self._strategy_class.current_pos,
                base_position,
                self._strategy_class.current_profit,
                self._strategy_class.api_count,
                self._strategy_class.api_count2,
                self.strategy_config_file)
            if 'pos_server' in self._config and self._config['pos_server'] != None:
                self.socket.sendto(message.encode(
                    'utf-8'), (self._config['pos_server'][0], self._config['pos_server'][1]))

    def load_config_file(self, config_file):
        self._config_file = config_file

        config = yaml.safe_load(
            open(self._config_file, 'r', encoding='utf-8_sig'))

        # execution_check_with_public_channelのデフォルトはFalse
        if 'execution_check_with_public_channel' not in config:
            config['execution_check_with_public_channel'] = False

        for key, value in config.items():
            if key != 'apikey' and key != 'secret' and (not 'strategy_' in key):
                if key in self._config:
                    if self._config[key] != config[key]:
                        self._logger.info("{:<40} ; {} -> {}".format(
                            "Parameter Changed [{}]".format(key), self._config[key], config[key]))
                else:
                    self._logger.info("{:<40} ; {}".format(
                        "Current Parameter [{}]".format(key), config[key]))
        for key, value in self._config.items():
            if key != 'apikey' and key != 'secret' and key != 'created_at':
                if not key in config:
                    self._logger.info(
                        "{:<40} ; ({}) -> none".format("Parameter Deleted [{}]".format(key), self._config[key]))

        self._logger.info(
            "Load bot configfile: config = {}".format(self._config_file))

        self._config = copy.deepcopy(config)

        self.adjust_position_with_api = False
        if 'adjust_position_with_api' in self._config:
            self.adjust_position_with_api = self._config['adjust_position_with_api']

        self.check_cross_trade = True
        if 'check_cross_trade' in self._config:
            self.check_cross_trade = self._config['check_cross_trade']

        if self.strategy_file == '':
            self.strategy_file = self._config['strategy_py']

        if self.strategy_config_file == '':
            self.strategy_config_file = self._config['strategy_yaml']

        # strategy config の timestamp を記憶(auto reloadのため)
        self._config['created_at'] = os.path.getmtime(self._config_file)

    def load_strategy_config_file(self, strategy_config_file):
        self.strategy_config_file = strategy_config_file

        strategy_config = yaml.safe_load(
            open(self.strategy_config_file, 'r', encoding='utf-8_sig'))

        if 'handle_spot_realtime_api' in strategy_config:
            self.handle_spot_realtime_api = strategy_config['handle_spot_realtime_api']
        if 'use_lightning_candle' in strategy_config:
            self.use_lightning_candle = strategy_config['use_lightning_candle']
        if 'drive_by_spot_ticker' in strategy_config:
            self.drive_by_spot_ticker = strategy_config['drive_by_spot_ticker']
        if 'drive_by_executions' in strategy_config:
            self.drive_by_executions = strategy_config['drive_by_executions']
        if 'order_retry' in strategy_config:
            self.order_retry = strategy_config['order_retry']
        if 'cancel_retry' in strategy_config:
            self.cancel_retry = strategy_config['cancel_retry']

        if 'cryptowatch_candle' in strategy_config:
            self.cryptowatch_candle = strategy_config['cryptowatch_candle']

        # close_position_while_no_tradeのデフォルトはTrue
        if 'close_position_while_no_trade' in strategy_config:
            self.close_position_while_no_trade = strategy_config['close_position_while_no_trade']
        else:
            self.close_position_while_no_trade = True

        # logic_loop_periodのデフォルトは1秒
        if 'logic_loop_period' not in strategy_config:
            strategy_config['logic_loop_period'] = 1

        # renew_candle_everysecondのデフォルトはFalse
        if 'renew_candle_everysecond' in strategy_config:
            self.renew_candle_everysecond = strategy_config['renew_candle_everysecond']
        else:
            self.renew_candle_everysecond = False

        for key, value in strategy_config.items():
            if key in self._strategy:
                if self._strategy[key] != strategy_config[key]:
                    if key == 'parameters':
                        for param_key, param_value in strategy_config[key].items():
                            if param_key in self._strategy[key]:
                                if self._strategy[key][param_key] != strategy_config[key][param_key]:
                                    self._parameter_message(True, "[parameters]{:<40} ; {} -> {}".format("Parameter Changed [{}]".format(
                                        param_key), self._strategy[key][param_key], strategy_config[key][param_key]))
                            else:
                                self._parameter_message(True, "[parameters]{:<40} ; {}".format(
                                    "Current Parameter [{}]".format(param_key), strategy_config[key][param_key]))
                    else:
                        self._parameter_message(True, "{:<40} ; {} -> {}".format(
                            "Parameter Changed [{}]".format(key), self._strategy[key], strategy_config[key]))
            else:
                self._parameter_message(True, "{:<40} ; {}".format(
                    "Current Parameter [{}]".format(key), strategy_config[key]))

        for key, value in self._strategy.items():
            if key != 'created_at':
                if not key in strategy_config:
                    self._parameter_message(True, "{:<40} ; ({}) -> none".format(
                        "Parameter Deleted [{}]".format(key), self._strategy[key]))

        self._strategy = copy.deepcopy(strategy_config)

        # strategy config の timestamp を記憶(auto reloadのため)
        self._strategy['created_at'] = os.path.getmtime(
            self.strategy_config_file)

        # lotsizeからクローズロットを計算
        if 'parameters' in self._strategy and self._strategy['parameters'] != None and 'lotsize' in self._strategy['parameters']:
            self.close_lot = self._strategy['parameters']['lotsize']*3
        else:
            self.close_lot = 1

        self._logger.info("Load strategy configfile: config = {}".format(
            self.strategy_config_file))

        self._parameter_message_send()

    _message = ''

    def _parameter_message(self, discord_send, message):
        if discord_send == True and (not 'http' in message) and (not 'discord_bot_token' in message):
            self._logger.info(message)
            self._message += message + '\n'
        else:
            self._logger.debug(message)

    def _parameter_message_send(self):
        try:
            webhooks = self._strategy['position_discord_webhooks'] if 'position_discord_webhooks' in self._strategy else ''
            if webhooks != '' and self._message != '':
                payload = {'content': '{} {}\n{}'.format((datetime.utcnow(
                )+timedelta(hours=9)).strftime('%H:%M:%S'), self.strategy_config_file, self._message)}
                requests.post(webhooks, data=payload, timeout=10)
        except Exception as e:
            self._logger.error(
                'Failed sending status to Discord: {}'.format(e))
            time.sleep(1)
        self._message = ''

    def renew(self):
        updated = False
        if self._config['created_at'] != os.path.getmtime(self._config_file):
            self.load_config_file(self._config_file)
            self.load_strategy_config_file(self.strategy_config_file)
            updated = True

        if self._strategy['created_at'] != os.path.getmtime(self.strategy_config_file):
            self.load_strategy_config_file(self.strategy_config_file)
            updated = True

        # トレード中断期間であれば、強制的にclose_positionモードとする
        if self.check_no_trade_period():
            self.no_trade_period = True
            if self.close_position_while_no_trade == True:
                self._strategy['close_position'] = True
                self._strategy['emergency_wait'] = 10
        # トレード中断期間からの復帰時にはパラメータを読み直す
        elif self.no_trade_period == True:
            self.no_trade_period = False
            self.load_strategy_config_file(self.strategy_config_file)

        if 'parameters' in self._strategy and self._strategy['parameters'] != None and 'lotsize' in self._strategy['parameters']:
            self.close_lot = self._strategy['parameters']['lotsize']*3
        else:
            self.close_lot = 1

        return updated

    def check_no_trade_period(self):
        # 現在時刻が範囲内かどうか　https://codeday.me/jp/qa/20190219/264470.html
        def time_in_range(start, end, x):
            """Return true if x is in the range [start, end]"""
            if start <= end:
                return start <= x <= end
            else:
                return start <= x or x <= end

        within_period = False
        now = datetime_time((datetime.utcnow()+timedelta(hours=9)).hour,
                            (datetime.utcnow()+timedelta(hours=9)).minute, 0)
        weekday = (datetime.utcnow()+timedelta(hours=9)).weekday()
        if 'no_trade' in self._config:
            try:
                if self._config['no_trade'] != None:
                    for p in self._config['no_trade']:
                        start = datetime_time(
                            int(p['period'][0:2]), int(p['period'][3:5]),  0)
                        end = datetime_time(
                            int(p['period'][6:8]), int(p['period'][9:11]), 0)
                        if (len(p['period']) <= 11 or int(p['period'][12]) == weekday) and time_in_range(start, end, now):
                            self._logger.info(
                                'no_trade period : {}'.format(p['period']))
                            within_period = True
            except Exception as e:
                self._logger.error(
                    'no_trade period is not correct: {}'.format(e))
                self._logger.info('no_trade : {}'.format(
                    self._config['no_trade']))

        return within_period

    @property
    def estimated_position(self):
        return self._estimated_position

    @estimated_position.setter
    def estimated_position(self, pos):
        self._estimated_position = pos
        self.position_event.set()
