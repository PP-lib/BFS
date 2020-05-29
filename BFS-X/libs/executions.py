# coding: utf-8
from datetime import datetime, timedelta, timezone
import traceback
from sortedcontainers import SortedDict
import random
import warnings
from collections import deque
import time
from dateutil import parser
from threading import Event, Lock
import pandas
pandas.set_option('display.expand_frame_repr', False)
try:
    from libs import realtimeapi_f as realtimeapi
except:
    from libs import realtimeapi

epsilon = 1e-7


def mean(q):
    return sum(q) / (len(q) + epsilon)

# Websocketを受信して1秒足を作り続けるクラス


class SecondCandle:
    def __init__(self, logger, product, timescale, parameters):
        self.candleupdated = Event()
        self.product = product
        self.logger = logger
        self.timescale = timescale
        self._parameters = parameters
        self.lastcandle = datetime.now(timezone(timedelta(hours=9), 'JST'))
        self.lastexecution = []
        self.lastexecutiontime = time.time()
        self.sectimer = time.time()
        self.mid_price = -1
        self.spot_mid_price = -1
        self.spot_price = -1
        self.spot_price_last = -1
        self.spot_price_exec = -1

        # 約定履歴を貯めるバッファ。溢れないように余裕をもって多めにしておく
        # 現状の取引量だと秒あたり100～200約定なので、必要量の2.5～5倍程度を確保している
        self.executions = deque(maxlen=timescale*5000)
        self.RealtimeHandler()
        warnings.simplefilter(action="ignore", category=FutureWarning)

        # レイテンシの計測用バッファ (直近5配信分)
        self.latancy_buf = deque(maxlen=5)

        # 現在足の生成
        self.current_open = 0
        self.current_high = 0
        self.current_low = 0
        self.current_close = 0
        self.current_volume = 0
        self.current_buy_volume = 0
        self.current_sell_volume = 0
        self.current_count = 0
        self.current_buy_count = 0
        self.current_sell_count = 0
        self.current_total_value = 0

        # 板情報の更新中ロック
        self.board_lock = Lock()
        self.spot_board_lock = Lock()

        # 約定履歴更新中ロック
        self.execution_lock = Lock()

        # レイテンシの計測用バッファ更新中ロック
        self.latancy_buf_lock = Lock()

        # 板情報を格納
        self.bids = SortedDict()
        self.asks = SortedDict()
        self.board_age = 0
        self.spot_bids = SortedDict()
        self.spot_asks = SortedDict()

        self.previous_candles = deque(maxlen=3)  # NaNでない秒足のリスト (3本あれば十分)

    @property
    def current_latency(self):
        with self.latancy_buf_lock:
            latency = int(mean(self.latancy_buf)*1000)
        return latency

    def format_date(self, date_line, time_diff):
        exec_date = date_line.replace('T', ' ')[:-1]
        try:
            if len(exec_date) == 19:
                exec_date = exec_date + '.0'
            d = datetime(int(exec_date[0:4]), int(exec_date[5:7]), int(exec_date[8:10]), int(
                exec_date[11:13]), int(exec_date[14:16]), int(exec_date[17:19]), int(exec_date[20:26]), tzinfo=timezone(time_diff, 'JST')) + time_diff
        except Exception as e:
            self._logger.exception("Error while parsing date str : exec_date:{}  {}, {}".format(
                exec_date, e, traceback.print_exc()))
            d = parser.parse(exec_date) + time_diff
        return d

    def random4digit(self):
        return "+{:04}".format(random.randint(0, 9999))

    # executionリストをもとに1秒足のローソクを生成
    def updatecandle(self):

        try:
            start = time.time()
            with self.execution_lock:
                # dequeをリストに
                tmpExecutions = list(self.executions)
                self.raw = pandas.DataFrame([[
                    tick["exec_date"],
                    tick["price"],
                    tick["size"],
                    tick["size"]if tick["side"] == 'BUY'else 0,
                    tick["size"]if tick["side"] == 'SELL'else 0,
                    1 if tick["size"] != 0 else 0,
                    1 if tick["side"] == 'BUY' else 0,
                    1 if tick["side"] == 'SELL' else 0,
                    tick["price"] * tick["size"]
                ] for tick in tmpExecutions], columns=["date", "price", "volume", "buy", "sell", "count", "count_buy", "count_sell", "total_value"])
            self.candle = self.raw.set_index('date').resample(str(self.timescale)+"s").agg({
                "price": "ohlc", "volume": "sum", "buy": "sum", "sell": "sum", "count": "sum", "count_buy": "sum", "count_sell": "sum", "total_value": "sum"})
            self.candle.columns = self.candle.columns.droplevel()

            self.previous_candles.clear()  # NaNでない秒足のリスト
            candle_index = self.candle.index.values
            for i in range(1, len(candle_index)):
                # NaNが自身との等号判定でfalseを返すという性質を利用してNanかどうかを判定
                if self.candle.at[candle_index[i], "open"] != self.candle.at[candle_index[i], "open"]:
                    # その期間に約定履歴が無い場合にはひとつ前の足からコピー
                    self.candle.loc[candle_index[i], [
                        "open", "high", "low", "close"]] = self.candle.at[candle_index[i-1], "close"]
                else:
                    self.previous_candles.append(self.candle.index[i])
            self.lastcandle = self.candle[-1:].index[0]

#            self.logger.log(5, "Conversion elapsed_time:{:.1f}".format((time.time() - start)*1000) + "[msec]")
#            self.logger.log(5, "{}ticks -> {}candles x 1sec".format(len(tmpExecutions),len(self.candle)))
        except:
            pass

    # 負荷軽減のため、ローソク足に変換済みの約定履歴を破棄
    def reduce_exeution_buffer(self):
        if len(self.executions) == 0:
            return

        if len(self.previous_candles) == 0:
            return

        with self.execution_lock:
            while True:
                i = self.executions.popleft()
                if self.previous_candles[0].timestamp() <= i['exec_date'].timestamp():
                    self.executions.appendleft(i)
                    break

    # 板情報から実効Ask/Bid(=指値を入れる基準値)を計算する関数　startpriceから上下サイズ分をみて価格を決める

    def get_effective_tick(self, size_thru, startprice, limitprice):
        try:
            with self.board_lock:
                asks = self.asks.items()
                bids = self.bids.items()

                total = 0
                asks_pos = self.mid_price
                for price, size in asks:
                    if price > startprice or startprice == 0:
                        if startprice == 0:
                            startprice = price
                        total += size
                        asks_pos = price
                        if total > size_thru or price > startprice+limitprice:
                            break

                total = 0
                bids_pos = self.mid_price
                for price, size in reversed(bids):
                    if price < startprice or startprice == 0:
                        if startprice == 0:
                            startprice = price
                        total += size
                        bids_pos = price
                        if total > size_thru or price < startprice-limitprice:
                            break

        except:
            return {'bid': 0, 'ask': 0}

        return {'bid': bids_pos, 'ask': asks_pos}

    # 板情報を返す関数（bFからのレスポンスと同じ形に成型する)
    def get_board(self):
        with self.board_lock:
            asks = self.asks.items()
            bids = self.bids.items()
            bids_dict = [{'price': a[0], 'size':a[1]} for a in list(bids)]
            asks_dict = [{'price': a[0], 'size':a[1]} for a in list(asks)]
        bids_dict.reverse()
        return {'mid_price': self.mid_price, 'bids': bids_dict, 'asks': asks_dict}

    # 板情報を返す関数（bFからのレスポンスと同じ形に成型する)
    def get_spot_board(self):
        with self.spot_board_lock:
            asks = self.spot_asks.items()
            bids = self.spot_bids.items()
            bids_dict = [{'price': a[0], 'size':a[1]} for a in list(bids)]
            asks_dict = [{'price': a[0], 'size':a[1]} for a in list(asks)]
        bids_dict.reverse()
        return {'mid_price': self.spot_mid_price, 'bids': bids_dict, 'asks': asks_dict}

    def RealtimeHandler(self):

        # ハンドラ呼び出し
        def handler(func, *args):
            return func(*args)

        # board(SortedDict)にdの板情報を挿入(削除)
        def update_board(board, d):
            for i in d:
                p, s = i['price'], i['size']
                if s != 0:
                    board[p] = s
                elif p in board:
                    del board[p]

        def check_rollback_exec():
            # 過去データにヒットしていたら
            with self._parameters.executed_order_pending_rollback_lock:
                if self._parameters.executed_order_pending_rollback == True:
                    self._parameters.executed_order_pending_rollback = False

                    # 過去のヒットしなかった約定データを再精査
                    for i in range(len(self._parameters.executed_order_pending_detail)):
                        r = self._parameters.executed_order_pending_detail.popleft()
                        check_execution(r)

        def check_execution(r):
            # 自分が発行したオーダーのリストに当該のidがあれば自分の約定
            if r['child_order_acceptance_id'] in list(self._parameters.childorder_id_list):
                with self._parameters.server_accepted_time_lock:
                    accepted_order = [i for i in self._parameters.server_accepted_time_detail if i['id']
                                      == r['child_order_acceptance_id'] and i['event'] == 'ORDER'][0]
                    apitime = accepted_order['time']
                    if accepted_order == []:
                        accepted_order = {
                            'sendorder': 0, 'accepted': 0, 'ordered': 0}
                    if 'ordered' not in accepted_order:
                        accepted_order['ordered'] = time.time()

                self.logger.info("        EXECUTION: ({:.0f}msec) {} {} price:{} size:{} [sfd:{}]".format((time.time()-apitime)*1000,
                                                                                                          r['child_order_acceptance_id'], r['side'], r['price'], r['size'], r['sfd']))
                self._parameters.sfd_commission += r['sfd']
                if r['sfd'] > 0:
                    self._parameters.sfd_profit += r['sfd']
                if r['sfd'] < 0:
                    self._parameters.sfd_loss += r['sfd']

                if not self._parameters._config['execution_check_with_public_channel']:
                    # 想定ポジション(速報値)を増減させる
                    lotsize = round(r['size'] if r['side'] ==
                                    "BUY" else -r['size'], 8)
                    self._parameters.estimated_position2 += lotsize
                    self._parameters.executed_size[-1] += r['size']    # 取引高
                    self._parameters.executed_size_today += r['size']  # 取引高

                    # とりあえずここでは約定済みリストに入れておいて、後でポジション管理へ回してポジション変化を計算
                    with self._parameters.executed_order_lock:
                        self._parameters.executed_order.append({'id': r['child_order_acceptance_id']+self.random4digit(
                        ), 'price': r["price"], 'lot': lotsize, 'date': r["event_date"], 'timestamp': time.time(),
                            'sendorder': accepted_order['time'], 'accepted': accepted_order['accepted'], 'ordered': accepted_order['ordered']})
                    self._parameters.execution_event.set()

                    if self._parameters.drive_by_executions:      # drive_by_executions がセットされていれば、約定検出でrealtime_logic()を呼び出す
                        self._parameters.logic_execution_event.set()
                        self._parameters.order_signal_event.set()

            else:
                self._parameters.executed_order_pending.append(
                    r['child_order_acceptance_id'])  # オーダーと約定通知が前後したときのために突っ込んで保管しておく
                self._parameters.executed_order_pending_detail.append(
                    r)                        # オーダーと約定通知が前後したときのために突っ込んで保管しておく

        # https://bf-lightning-api.readme.io/docs/realtime-executions
        def on_executions(recept_data):

            self._parameters.execution_timestamp = time.time()
            self._parameters.ltp = recept_data[-1]["price"]

            try:
                # 現在時刻と約定履歴のタイムスタンプの差から配信遅延を計測
                #    参考URL) https://gist.github.com/nagadomi/bbf4df93a4ac2fce10d89e4206e4cb7a
                #             https://twitter.com/ultraistter/status/1046186504370966528
                with self.latancy_buf_lock:
                    latency_sec = datetime.now().timestamp() - \
                        self.format_date(
                            recept_data[-1]["exec_date"], timedelta(hours=0)).timestamp()
                    self.latancy_buf.append(latency_sec)
                    self._parameters.all_latency_history.append(
                        int(latency_sec*1000))
            except:
                pass

            try:
                if self._parameters._strategy_class != None:
                    self._parameters._strategy_class.hit_check(recept_data)
            except Exception as e:
                self.logger.exception(
                    "Error in executions routine : {}, {}".format(e, traceback.print_exc()))

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.execution_handler != None:
                    handler(self._parameters.execution_handler, recept_data)
            except Exception as e:
                self.logger.exception(
                    "Error in executions routine : {}, {}".format(e, traceback.print_exc()))

            with self.execution_lock:
                for i in recept_data:
                    # ローソク足生成のために保管
                    self.executions.append({'exec_date': self.format_date(i["exec_date"], timedelta(hours=9)),
                                            'price': i["price"],
                                            'size': i["size"],
                                            'side': i["side"]})

            ask_top = int(recept_data[0]['price'])
            bid_bottom = int(recept_data[0]['price'])
            self._parameters.execution_counter[-1] += len(recept_data)

            for i in recept_data:
                # 現在足のデータ生成
                self.current_exec_date = self.format_date(
                    i["exec_date"], timedelta(hours=9))
                current_price = int(i['price'])
                current_size = i['size']
                if self.current_open == 0:
                    self.current_open = current_price
                    self.current_high = current_price
                    self.current_low = current_price
                    self.current_close = current_price
                self.current_high = max(current_price, self.current_high)
                self.current_low = min(current_price, self.current_low)
                self.current_close = current_price
                self.current_volume += current_size
                self.current_count += 1
                self.current_total_value += current_price * current_size

                if i['side'] == 'BUY':
                    self.current_buy_volume += current_size
                    self.current_buy_count += 1
                    self._parameters.best_ask = current_price
                else:
                    self.current_sell_volume += current_size
                    self.current_sell_count += 1
                    self._parameters.best_bid = current_price

                # 今回のexecutionsパックの高値低値
                ask_top = max(current_price, ask_top)
                bid_bottom = min(current_price, bid_bottom)

                # Private channel の認証が終わっていなければ publicで判断
                if self._parameters._config['execution_check_with_public_channel'] or not self.realtimeapi.auth_check():
                    # 検索用id
                    buy_acceptance_id = i["buy_child_order_acceptance_id"]
                    buy_acceptance_id_4d = buy_acceptance_id+self.random4digit()

                    sell_acceptance_id = i["sell_child_order_acceptance_id"]
                    sell_acceptance_id_4d = sell_acceptance_id+self.random4digit()

                    # 注文リストに約定履歴と同じオーダー番号があれば約定と判断
                    with self._parameters.order_id_list_lock:
                        checklist = list(
                            self._parameters.childorder_id_list)
                        fHitBuy = True if buy_acceptance_id in checklist else False
                        fHitSell = True if sell_acceptance_id in checklist else False
                    if fHitBuy:
                        # 詳細な発注リストから該当のIDを抜き出し、売買方向も含めて詳細にチェック
                        hitlist = [x for x in self._parameters.childorder_information if x['id'] == buy_acceptance_id and x['side']
                                   == 'BUY' and x['remain'] >= i['size'] and (x['child_order_type'] == 'MARKET' or x['price'] >= i['price'])]
                        if hitlist:
                            # 想定ポジション(速報値)を増減させる
                            self._parameters.estimated_position2 += i['size']
                            # 取引高
                            self._parameters.executed_size[-1] += i['size']
                            # 取引高
                            self._parameters.executed_size_today += i['size']

                            # とりあえずここでは約定済みリストに入れておいて、後でポジション変化を計算
                            accepted_order = [
                                a for a in self._parameters.server_accepted_time_detail if a['id'] == buy_acceptance_id and a['event'] == 'ORDER'][0]
                            if accepted_order == []:
                                accepted_order = {
                                    'sendorder': 0, 'accepted': 0, 'ordered': 0}
                            if 'ordered' not in accepted_order:
                                accepted_order['ordered'] = time.time()
                            with self._parameters.executed_order_lock:
                                self._parameters.executed_order.append(
                                    {'id': buy_acceptance_id_4d, 'price': i["price"], 'lot': i["size"], 'date': i["exec_date"], 'timestamp': time.time(),
                                     'sendorder': accepted_order['time'], 'accepted': accepted_order['accepted'], 'ordered': accepted_order['ordered']})
                            self.logger.debug("          HIT({})*****BUY!!!   ({}) {} price:{:.0f}  size:{:.8f}".format(len(
                                hitlist), self.format_date(i["exec_date"], timedelta(hours=9)), buy_acceptance_id, i["price"], i["size"]))
                            self._parameters.execution_event.set()
                            if self._parameters.drive_by_executions:      # drive_by_executions がセットされていれば、約定検出でrealtime_logic()を呼び出す
                                self._parameters.logic_execution_event.set()
                                self._parameters.order_signal_event.set()
                        else:
                            self.logger.error("          Unexpected  BUY!!!   ({})  price:{:.0f}  size:{:.8f}".format(
                                buy_acceptance_id, i["price"], i["size"]))

                    if fHitSell:
                        # 詳細な発注リストから該当のIDを抜き出し、売買方向も含めて詳細にチェック
                        hitlist = [x for x in self._parameters.childorder_information if x['id'] == sell_acceptance_id and x['side']
                                   == 'SELL' and x['remain'] >= i['size'] and (x['child_order_type'] == 'MARKET' or x['price'] <= i['price'])]
                        if hitlist:
                            # 想定ポジション(速報値)を増減させる
                            self._parameters.estimated_position2 -= i['size']
                            # 取引高
                            self._parameters.executed_size[-1] += i['size']
                            # 取引高
                            self._parameters.executed_size_today += i['size']

                            # とりあえずここでは約定済みリストに入れておいて、後でポジション変化を計算
                            accepted_order = [
                                a for a in self._parameters.server_accepted_time_detail if a['id'] == sell_acceptance_id and a['event'] == 'ORDER'][0]
                            if accepted_order == []:
                                accepted_order = {
                                    'sendorder': 0, 'accepted': 0, 'ordered': 0}
                            if 'ordered' not in accepted_order:
                                accepted_order['ordered'] = time.time()
                            with self._parameters.executed_order_lock:
                                self._parameters.executed_order.append(
                                    {'id': sell_acceptance_id_4d, 'price': i["price"], 'lot': -i["size"], 'date': i["exec_date"], 'timestamp': time.time(),
                                     'sendorder': accepted_order['time'], 'accepted': accepted_order['accepted'], 'ordered': accepted_order['ordered']})
                            self.logger.debug("          HIT({})*****SELL!!!  ({}) {} price:{:.0f}  size:{:.8f}".format(len(
                                hitlist), self.format_date(i["exec_date"], timedelta(hours=9)), sell_acceptance_id, i["price"], i["size"]))
                            self._parameters.execution_event.set()
                            if self._parameters.drive_by_executions:      # drive_by_executions がセットされていれば、約定検出でrealtime_logic()を呼び出す
                                self._parameters.logic_execution_event.set()
                                self._parameters.order_signal_event.set()
                        else:
                            self.logger.error("          Unexpected  SELL!!!  ({})  price:{:.0f}  size:{:.8f}".format(
                                sell_acceptance_id, i["price"], i["size"]))

            # 約定履歴で板を削る
            with self.board_lock:
                asks = self.asks.items()
                for price, size in asks:
                    if price < ask_top:
                        update_board(
                            self.asks, [{'price': price, 'size': 0}])
                    else:
                        break
                bids = self.bids.items()
                for price, size in reversed(bids):
                    if price > bid_bottom:
                        update_board(
                            self.bids, [{'price': price, 'size': 0}])
                    else:
                        break

            if time.time() - self.sectimer > 1:
                self.sectimer = time.time()
                self._parameters.latency_history.append(
                    self.current_latency)  # 約定履歴のレイテンシ

            # 送られてきたexecutionの時間が前回ローソク足更新時の最後の足よりもtimescale進んでいればローソク足の更新作業を行う
            if len(recept_data) > 0 and self.format_date(recept_data[-1]["exec_date"], timedelta(hours=9)).timestamp() - self.lastcandle.timestamp() >= self.timescale:
                self.lastexecutiontime = self._parameters.execution_timestamp
                # ローソク足更新を通知
                self.candleupdated.set()

        # https://bf-lightning-api.readme.io/docs/realtime-board-snapshot
        def on_board_snapshot(recept_data):

            self._parameters.board_timestamp = time.time()
            self.mid_price = int(recept_data['mid_price'])

            # 板スナップショット
            with self.board_lock:
                bids, asks = SortedDict(), SortedDict()  # 空のSortedDictを作って
                update_board(bids, recept_data['bids'])  # すべてのmessageを
                update_board(asks, recept_data['asks'])  # 突っ込む
                self.bids, self.asks = bids, asks
                self.board_age = 0

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.board_updated_handler != None:
                    handler(self._parameters.board_updated_handler)
            except Exception as e:
                self.logger.exception(
                    "Error in board_updated routine : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-board

        def on_board(recept_data):
            check_rollback_exec()

            self._parameters.board_timestamp = time.time()
            self.mid_price = int(recept_data['mid_price'])

            # 板更新情報
            # 取得したデータでスナップショットを更新する
            with self.board_lock:
                update_board(self.bids, recept_data['bids'])  # messageを
                update_board(self.asks, recept_data['asks'])  # 突っ込む
                self.board_age += 1

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.board_updated_handler != None:
                    handler(self._parameters.board_updated_handler)
            except Exception as e:
                self.logger.exception(
                    "Error in board_updated routine : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-child-order-events
        def on_child_order_events(recept_data):

            for r in recept_data:
                try:
                    if r['event_type'] == 'EXECUTION':
                        check_execution(r)
                    elif r['event_type'] == 'ORDER':
                        if r['child_order_acceptance_id'] in list(self._parameters.childorder_id_list):
                            with self._parameters.server_accepted_time_lock:
                                accepted_order = [i for i in self._parameters.server_accepted_time_detail if i['id']
                                                  == r['child_order_acceptance_id'] and i['event'] == 'ORDER'][0]
                                apitime = accepted_order['time']
                                index = self._parameters.server_accepted_time_detail.index(
                                    accepted_order)
                                self._parameters.server_accepted_time_detail[
                                    index]['sendorder'] = accepted_order['time']
                                self._parameters.server_accepted_time_detail[
                                    index]['accepted'] = accepted_order['accepted']
                                self._parameters.server_accepted_time_detail[index]['ordered'] = time.time(
                                )

                            self._parameters.server_order_delay_history.append(
                                [datetime.utcnow()+timedelta(hours=9), (time.time()-apitime)*1000])
                            self.logger.info("        ORDER: ({:.0f}msec) {} {} {} price:{} size:{}  (latency {:.0f}msec)".format((time.time()-apitime)*1000,
                                                                                                                                  r['child_order_acceptance_id'], r['child_order_type'], r['side'], r['price'], r['size'], self.current_latency))
                            self._parameters.ordered_speed_history[-1].append(
                                (time.time()-apitime)*1000)

                            # 詳細な発注リストから該当のIDを抜き出し、発注完了時刻、受付時刻を追記
                            order_list = [
                                x for x in self._parameters.childorder_information if x['id'] == r['child_order_acceptance_id']][0]
                            index = self._parameters.childorder_information.index(
                                order_list)
                            self._parameters.childorder_information[index][
                                'accepted'] = accepted_order['accepted']
                            self._parameters.childorder_information[index][
                                'ordered'] = accepted_order['ordered']

                    elif r['event_type'] == 'ORDER_FAILED':
                        self.logger.debug(r)
                        if r['child_order_acceptance_id'] in list(self._parameters.childorder_id_list):
                            with self._parameters.server_accepted_time_lock:
                                apitime = [i['time'] for i in self._parameters.server_accepted_time_detail if i['id']
                                           == r['child_order_acceptance_id'] and i['event'] == 'ORDER'][0]
                            self.logger.error("        ORDER_FAILED: ({:.0f}msec) {} {}".format(
                                (time.time()-apitime)*1000, r['child_order_acceptance_id'], r['reason']))
                            self._parameters.canceled_child_order.append(
                                r['child_order_acceptance_id'])  # 後でポジション管理へ回して処理

                    elif r['event_type'] == 'EXPIRE':
                        # 詳細な発注リストから該当のIDを抜き出し
                        order_list = [
                            x for x in self._parameters.childorder_information if x['id'] == r['child_order_acceptance_id']]
                        if len(order_list) != 0 and order_list[0]['remain'] != order_list[0]['size']:
                            self._parameters.order_partial_filled_count[-1] += 1

                        if r['child_order_acceptance_id'] in list(self._parameters.childorder_id_list):
                            with self._parameters.server_accepted_time_lock:
                                apitime = [i['time'] for i in self._parameters.server_accepted_time_detail if i['id']
                                           == r['child_order_acceptance_id'] and i['event'] == 'ORDER'][0]
                            self.logger.info("        EXPIRE: ({:.0f}msec) {}".format(
                                (time.time()-apitime)*1000, r['child_order_acceptance_id']))
                            self._parameters.canceled_child_order.append(
                                r['child_order_acceptance_id'])  # 後でポジション管理へ回して処理

                    elif r['event_type'] == 'CANCEL':
                        # 詳細な発注リストから該当のIDを抜き出し
                        order_list = [
                            x for x in self._parameters.childorder_information if x['id'] == r['child_order_acceptance_id']]
                        if len(order_list) != 0 and order_list[0]['remain'] != order_list[0]['size']:
                            self._parameters.order_partial_filled_count[-1] += 1

                        apitime = 0
                        self._parameters.order_not_filled_count[-1] += 1
                        # キャンセルコマンドを発行してキャンセルしたもの
                        if r['child_order_acceptance_id'] in list(self._parameters.cancel_child_id_list):
                            with self._parameters.server_accepted_time_lock:
                                apitime = [i['time'] for i in self._parameters.server_accepted_time_detail if i['id']
                                           == r['child_order_acceptance_id'] and i['event'] == 'CANCEL'][0]
                            self._parameters.server_cancel_delay_history.append(
                                [datetime.utcnow()+timedelta(hours=9), (time.time()-apitime)*1000])
                            self.logger.info("        CANCEL: ({:.0f}msec) {}  (latency {:.0f}msec)".format(
                                (time.time()-apitime)*1000, r['child_order_acceptance_id'], self.current_latency))
                            self._parameters.canceled_speed_history[-1].append(
                                (time.time()-apitime)*1000)

                        # キャンセルコマンドを発行したものでなくても自分が発行したオーダーのリストに当該のidがあれば自分のオーダーのキャンセル
                        if r['child_order_acceptance_id'] in list(self._parameters.childorder_id_list):
                            if apitime == 0:
                                self.logger.info("        CANCEL: {}  (latency {:.0f}msec)".format(
                                    r['child_order_acceptance_id'], self.current_latency))
                            self._parameters.canceled_child_order.append(
                                r['child_order_acceptance_id'])  # 後でポジション管理へ回して処理

                    elif r['event_type'] == 'CANCEL_FAILED':
                        self.logger.debug(r)
                        if r['child_order_acceptance_id'] in list(self._parameters.cancel_child_id_list):
                            with self._parameters.server_accepted_time_lock:
                                apitime = [i['time'] for i in self._parameters.server_accepted_time_detail if i['id']
                                           == r['child_order_acceptance_id'] and i['event'] == 'CANCEL'][0]
                            self.logger.error("        CANCEL_FAILED: ({:.0f}msec) {}".format(  # self.format_date(r['event_date'],timedelta(hours=9)),
                                (time.time()-apitime)*1000,
                                r['child_order_acceptance_id']))
                            self._parameters.canceled_child_order.append(
                                r['child_order_acceptance_id'])  # 後でポジション管理へ回して処理

                except Exception as e:
                    self.logger.info(r)
                    self.logger.exception(
                        "Error in handling child_order_event : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-parent-order-events
        def on_parent_order_events(recept_data):

            for r in recept_data:
                if r['parent_order_acceptance_id'] in list(self._parameters.parentorder_id_list):
                    try:
                        if r['event_type'] == 'ORDER':
                            self.logger.info("      PARENT ORDER: {} {}".format(
                                r['parent_order_acceptance_id'], r['parent_order_type']))

                        elif r['event_type'] == 'ORDER_FAILED':
                            self.logger.debug(r)
                            self.logger.error("      PARENT ORDER_FAILED: {} {}".format(
                                r['parent_order_acceptance_id'], r['reason']))
                            with self._parameters.order_id_list_lock:
                                self._parameters.canceled_parent_order.append(
                                    r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                            try:
                                del self._parameters.parentorder_method_dict[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass
                            try:
                                del self._parameters.parentorder_detail_param[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass

                        elif r['event_type'] == 'CANCEL':
                            self.logger.debug(r)
                            self.logger.info("      PARENT CANCEL: {}".format(
                                r['parent_order_acceptance_id']))
                            with self._parameters.order_id_list_lock:
                                self._parameters.canceled_parent_order.append(
                                    r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                            try:
                                del self._parameters.parentorder_method_dict[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass
                            try:
                                del self._parameters.parentorder_detail_param[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass

                        elif r['event_type'] == 'EXPIRE':
                            self.logger.debug(r)
                            self.logger.info("      PARENT EXPIRE: {}".format(
                                r['parent_order_acceptance_id']))
                            with self._parameters.order_id_list_lock:
                                self._parameters.canceled_parent_order.append(
                                    r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                            try:
                                del self._parameters.parentorder_method_dict[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass
                            try:
                                del self._parameters.parentorder_detail_param[
                                    r['parent_order_acceptance_id']]
                            except:
                                pass

                        elif r['event_type'] == 'COMPLETE':
                            order_method = self._parameters.parentorder_method_dict[
                                r['parent_order_acceptance_id']]
                            if (order_method in ['IFD', 'IFDOCO']) and r['parameter_index'] == 1:
                                self.logger.info("      PARENT COMPLETE (IF CONDITION): {} IDX:{} child_acceptance_id:{}".format(
                                    r['parent_order_acceptance_id'], r['parameter_index'], r['child_order_acceptance_id']))
                            else:
                                self.logger.info("      PARENT COMPLETE: {} IDX:{} child_acceptance_id:{}".format(
                                    r['parent_order_acceptance_id'], r['parameter_index'], r['child_order_acceptance_id']))

                            if order_method == 'SIMPLE':
                                if r['parameter_index'] == 1:
                                    with self._parameters.order_id_list_lock:
                                        self._parameters.canceled_parent_order.append(
                                            r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                                    try:
                                        del self._parameters.parentorder_method_dict[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                                    try:
                                        del self._parameters.parentorder_detail_param[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                            elif order_method == 'IFD':
                                if r['parameter_index'] == 2:
                                    with self._parameters.order_id_list_lock:
                                        self._parameters.canceled_parent_order.append(
                                            r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                                    try:
                                        del self._parameters.parentorder_method_dict[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                                    try:
                                        del self._parameters.parentorder_detail_param[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                            elif order_method == 'OCO':
                                if r['parameter_index'] == 1 or r['parameter_index'] == 2:
                                    with self._parameters.order_id_list_lock:
                                        self._parameters.canceled_parent_order.append(
                                            r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                                    try:
                                        del self._parameters.parentorder_method_dict[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                                    try:
                                        del self._parameters.parentorder_detail_param[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                            elif order_method == 'IFDOCO':
                                if r['parameter_index'] == 2 or r['parameter_index'] == 3:
                                    with self._parameters.order_id_list_lock:
                                        self._parameters.canceled_parent_order.append(
                                            r['parent_order_acceptance_id'])  # 後でポジション管理へ回して処理
                                    try:
                                        del self._parameters.parentorder_method_dict[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass
                                    try:
                                        del self._parameters.parentorder_detail_param[
                                            r['parent_order_acceptance_id']]
                                    except:
                                        pass

                        elif r['event_type'] == 'TRIGGER':
                            self.logger.info("      PARENT TRIGGER: {} IDX:{} child_acceptance_id:{}".format(
                                r['parent_order_acceptance_id'], r['parameter_index'], r['child_order_acceptance_id']))

                            # 発注の詳細データからヒットしたトリガー価格を取得
                            try:
                                child_condition_type = self._parameters.parentorder_detail_param[
                                    r['parent_order_acceptance_id']][r['parameter_index']-1]['condition_type']
                                if child_condition_type == 'MARKET':
                                    order_price = self._parameters.ltp
                                elif child_condition_type == 'LIMIT':
                                    order_price = self._parameters.parentorder_detail_param[
                                        r['parent_order_acceptance_id']][r['parameter_index']-1]['price']
                                elif child_condition_type == 'STOP':
                                    order_price = self._parameters.parentorder_detail_param[
                                        r['parent_order_acceptance_id']][r['parameter_index']-1]['trigger_price']
                                elif child_condition_type == 'STOP_LIMIT':
                                    order_price = self._parameters.parentorder_detail_param[
                                        r['parent_order_acceptance_id']][r['parameter_index']-1]['price']
                                elif child_condition_type == 'TRAIL':
                                    order_price = self._parameters.ltp
                                else:
                                    order_method = self._parameters.parentorder_method_dict[
                                        r['parent_order_acceptance_id']]
                                    self.logger.error("Unknown type : child_order_type:{} child_condition_type:{} order_method:{}\n{}".format(
                                        r['child_order_type'], child_condition_type, order_method, r))
                                    order_price = self._parameters.ltp
                            except:
                                order_price = self._parameters.ltp
                                self.logger.error(
                                    "Can't find parend order detail information : {}".format(r))
                                self.logger.error("{}".format(
                                    self._parameters.parentorder_detail_param))

                            self.logger.info("order_price:{} / {}".format(
                                order_price, self._parameters.parentorder_detail_param[r['parent_order_acceptance_id']][r['parameter_index']-1]))
                            # 子注文をリストに追加 (約定履歴と突き合わせる)
                            with self._parameters.order_id_list_lock:
                                # 重複を防ぐために、リストに無いIDだけを追加
                                if r['child_order_acceptance_id'] not in list(self._parameters.childorder_id_list):
                                    self._parameters.childorder_id_list.append(
                                        r['child_order_acceptance_id'])    # websocketで迅速に照合させるためのリスト
                                    self._parameters.childorder_information.append({'id': r['child_order_acceptance_id'], 'child_order_type': r['child_order_type'], 'remain': r['size'], 'side': r['side'], 'TTE': int(
                                        time.time()), 'price': order_price, 'size': r['size'], 'parent_id': r['parent_order_acceptance_id'], 'sendorder': time.time()})
                                    self._parameters.executed_order_pending_rollback = True
                                    # オーダー時間統計用
                                    with self._parameters.server_accepted_time_lock:
                                        self._parameters.server_accepted_time_detail.append(
                                            {'id': r['child_order_acceptance_id'], 'time': time.time(), 'event': 'ORDER', 'accepted': time.time()})

                    except Exception as e:
                        self.logger.info(r)
                        self.logger.exception("Error in handling parent_order_event : {}, {}".format(
                            e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-ticker
        def on_spot_ticker(recept_data):

            try:
                self.spot_price = int(recept_data["ltp"])
                if self.spot_price_last != self.spot_price:
                    # drive_by_spot_ticker がセットされていれば、Ticker検出(変更時のみ)でrealtime_logic()を呼び出す
                    if self._parameters.drive_by_spot_ticker:
                        self._parameters.spot_ticker_event.set()
                        self._parameters.order_signal_event.set()
                self.spot_price_last = self.spot_price
            except Exception as e:
                self.logger.info(r)
                self.logger.exception(
                    "Error in handling spot_ticker : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-executions
        def on_spot_executions(recept_data):

            try:
                self.spot_price_exec = recept_data[-1]['price']
            except Exception as e:
                self.logger.info(r)
                self.logger.exception(
                    "Error in handling spot_executions : {}, {}".format(e, traceback.print_exc()))

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.spot_execution_handler != None:
                    handler(
                        self._parameters.spot_execution_handler, recept_data)
            except Exception as e:
                self.logger.exception(
                    "Error in spot_executions routine : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-board-snapshot
        def on_spot_board_snapshot(recept_data):

            self.spot_mid_price = int(recept_data['mid_price'])
            # 板スナップショット
            with self.spot_board_lock:
                bids, asks = SortedDict(), SortedDict()  # 空のSortedDictを作って
                update_board(bids, recept_data['bids'])  # すべてのmessageを
                update_board(asks, recept_data['asks'])  # 突っ込む
                self.spot_bids, self.spot_asks = bids, asks

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.spot_board_updated_handler != None:
                    handler(self._parameters.spot_board_updated_handler)
            except Exception as e:
                self.logger.exception(
                    "Error in spot_board_updated routine : {}, {}".format(e, traceback.print_exc()))

        # https://bf-lightning-api.readme.io/docs/realtime-board
        def on_spot_board(recept_data):

            self.spot_mid_price = int(recept_data['mid_price'])
            # 板更新情報
            # 取得したデータでスナップショットを更新する
            with self.spot_board_lock:
                update_board(self.spot_bids,
                             recept_data['bids'])  # messageを
                update_board(self.spot_asks, recept_data['asks'])  # 突っ込む

            try:
                # ストラテジーのハンドラーが登録されていれば呼び出す
                if self._parameters.spot_board_updated_handler != None:
                    handler(self._parameters.spot_board_updated_handler)
            except Exception as e:
                self.logger.exception(
                    "Error in spot_board_updated routine : {}, {}".format(e, traceback.print_exc()))

        # チャンネル登録
        public_handler_mapping = {}
        public_handler_mapping["lightning_executions_{}".format(
            self.product)] = on_executions
        public_handler_mapping["lightning_board_snapshot_{}".format(
            self.product)] = on_board_snapshot
        public_handler_mapping["lightning_board_{}".format(
            self.product)] = on_board
        public_handler_mapping["lightning_ticker_BTC_JPY"] = on_spot_ticker
        if self._parameters.handle_spot_realtime_api:
            public_handler_mapping["lightning_executions_BTC_JPY"] = on_spot_executions
            public_handler_mapping["lightning_board_snapshot_BTC_JPY"] = on_spot_board_snapshot
            public_handler_mapping["lightning_board_BTC_JPY"] = on_spot_board

        private_handler_mapping = {}
        private_handler_mapping["child_order_events"] = on_child_order_events
        private_handler_mapping["parent_order_events"] = on_parent_order_events

        # websocket作成
        self.realtimeapi = realtimeapi.RealtimeAPIWebsocket(
            self.logger, self._parameters, public_handler_mapping, private_handler_mapping)
