# coding: utf-8
import time
from datetime import datetime, timedelta
from dateutil import parser
import csv
import os
import traceback
from copy import deepcopy


class order:
    def __init__(self, logger, api, parameters, parent, server_mode=False):
        self._logger = logger
        self._api = api
        self._parameters = parameters
        self._parent = parent
        self._product_code = parameters._config['product']
        if server_mode == False:
            self._restore_position()
            self.update_current_position()
        self._last_ordered_time = time.time()
        self._minutes_counter = 0

    # 停止・再起動しても現在ポジを保持するためのポジ情報保管ファイル
    def __position_csvfilename(self):
        return self._parameters._strategy['log_folder']+"position.csv"

    def __calc_pofit(self, open_price, close_price, qty, id, exec_date):
        return round((open_price-close_price)*qty, 8)

    def _save_position(self, position, profit):
        with open(self.__position_csvfilename(), 'a') as positionhistoryfile:
            positionhistorycsv = csv.writer(
                positionhistoryfile, lineterminator='\n')
            positionhistorycsv.writerow([(datetime.utcnow()+timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S"),
                                         position['id'], position['price'], position['size'], position['side'], profit, self._parameters.estimated_profit])

#    def is_order_expired(self):
#        return (time.time()-self._last_ordered_time > self._parameters._strategy['minutes_to_expire']*60)

    def _restore_position(self):
        self._parameters.current_position_list.clear()
        if os.path.exists(self.__position_csvfilename()):
            try:
                with open(self.__position_csvfilename(), 'r') as positionhistoryfile:
                    profit = 0
                    profit_total_from_file = 0
                    self._parameters.estimated_profit = 0
                    positionhistorycsv = csv.reader(positionhistoryfile)
                    for p in positionhistorycsv:

                        idx = -1
                        for i in range(len(self._parameters.current_position_list)):
                            if ('id', p[1]) in self._parameters.current_position_list[i].items():
                                idx = i

                        if p[4] == 'BUY':
                            if idx == -1:
                                self._parameters.current_position_list.append({'id': p[1], 'price': float(
                                    p[2]), 'size': float(p[3]), 'side': 'BUY', 'timestamp': time.time()})
                            else:
                                # 部分約定により変化したポジションを更新
                                # 念のため価格のチェック（違うはずは無い）
                                if self._parameters.current_position_list[idx]['price'] != float(p[2]):
                                    self._logger.error(
                                        'UPDATE ERR1 {}'.format(p))
                                # 念のため売り/買いのチェック（違うはずは無い）
                                elif self._parameters.current_position_list[idx]['side'] != p[4]:
                                    self._logger.error(
                                        'UPDATE ERR2 {}'.format(p))
                                else:
                                    self._parameters.current_position_list[idx]['size'] = float(
                                        p[3])

                        elif p[4] == 'SELL':
                            if idx == -1:
                                self._parameters.current_position_list.append({'id': p[1], 'price': float(
                                    p[2]), 'size': float(p[3]), 'side': 'SELL', 'timestamp': time.time()})
                            else:
                                # 部分約定により変化したポジションを更新
                                # 念のため価格のチェック（違うはずは無い）
                                if self._parameters.current_position_list[idx]['price'] != float(p[2]):
                                    self._logger.error(
                                        'UPDATE ERR3 {}'.format(p))
                                # 念のため売り/買いのチェック（違うはずは無い）
                                elif self._parameters.current_position_list[idx]['side'] != p[4]:
                                    self._logger.error(
                                        'UPDATE ERR4 {}'.format(p))
                                else:
                                    self._parameters.current_position_list[idx]['size'] = float(
                                        p[3])

                        elif p[4] == 'CLEAR':
                            if idx == -1:
                                # クリアすべきポジションが無い??
                                self._logger.error('ERROR       {}'.format(p))
                            else:
                                self._parameters.current_position_list.rotate(
                                    -idx)
                                self._parameters.current_position_list.popleft()
                                self._parameters.current_position_list.rotate(
                                    idx)
                        elif p[4] == 'PROFIT':
                            profit = int(p[5])
                            profit_total_from_file = int(p[6])
                            self._parameters.estimated_profit += profit
                            if self._parameters.estimated_profit != profit_total_from_file and not self._parameters._strategy_class.sim_mode:
                                self._logger.error('ERROR      Profit:{:>3} Total:{:>5}/{:>5}   {}'.format(
                                    profit, profit_total_from_file, self._parameters.estimated_profit, p))
                            self._parameters._strategy_class.current_profit = self._parameters.estimated_profit

                aveprice, possize = self.count_current_position()
                self._parameters.estimated_position = possize
                self._parameters.estimated_position2 = possize

                # 建玉のリストを表示
                self._logger.info(
                    "averageprice {:.0f}   avepos {:.4f}".format(aveprice, possize))
                self._logger.info(
                    "current profit {:+.0f}".format(self._parameters.estimated_profit))
                rest = list(self._parameters.current_position_list)
                if len(rest) > 0:
                    self._logger.info('Restored position List :')
                    for r in rest:
                        self._logger.info("    {}".format(r))
            except Exception as e:
                self._logger.exception("Error while restoreing position history : {}, {}".format(
                    e, traceback.print_exc()))

    # ChartCreator用のデータ書き出し
    def _write_exec_history(self, id, side, order_time, order_price, order_size, action, exec_time, exec_price, exec_size):
        with open(self._parameters._strategy['log_folder']+"position.json", 'a') as exechistoryfile:
            exechistoryfile.write('"{}":{{"type":"Limit","side": "{}","execs":[["order",{},{},{}],["{}",{},{},{}]]}},\n'.format(
                id, side, order_time, order_price, order_size, action, exec_time, exec_price, exec_size))

    def format_date(self, date_line, time_diff):
        exec_date = date_line.replace('T', ' ')
        try:
            if len(exec_date) == 19:
                exec_date = exec_date + '.0'
            d = datetime(int(exec_date[0:4]), int(exec_date[5:7]), int(exec_date[8:10]), int(
                exec_date[11:13]), int(exec_date[14:16]), int(exec_date[17:19]), int(exec_date[20:26]), ) + time_diff
        except Exception as e:
            self._logger.exception("Error while parsing date str : exec_date:{}  {}, {}".format(
                exec_date, e, traceback.print_exc()))
            d = parser.parse(exec_date) + time_diff
        return d

    def save_current_profit(self, delflag, profit=0):
        if delflag:
            try:
                os.remove(self.__position_csvfilename())
            except:
                pass
            self._save_position({'id': '', 'price': 0, 'size': 0, 'side': 'PROFIT'}, round(
                self._parameters._strategy_class.current_fixed_profit))
        else:
            self._save_position(
                {'id': '', 'price': 0, 'size': 0, 'side': 'PROFIT'}, round(profit))

    def update_current_position(self):
        self._parameters.execution_event.clear()

        old = self._parameters.estimated_position
        # minutes_to_expire経過後1分経ったオーダーは削除
        time_to_exprire = time.time(
        ) - self._parameters._strategy['minutes_to_expire']*60 - 60

        while True:

            # websocketで約定HITリストに入れられた約定履歴を順に処理
            with self._parameters.executed_order_lock:
                if len(self._parameters.executed_order) > 0:
                    execute = self._parameters.executed_order.popleft()
                    self._parameters.executed_order_history.append(
                        deepcopy(execute))  # ヒストリに入れておく
#                    self._logger.log(5, 'exec_data {}'.format(str(execute)) )
                else:
                    execute = {}

            exec_treated = False
            # 自分の発注情報を順に確認
            for i in range(len(self._parameters.childorder_information)):
                # 発注リスト
                order = self._parameters.childorder_information.popleft()

                # IDが合致していたら
                if execute != {} and order['id'] == execute['id'][:-5]:
                    exec_treated = True
                    # 発注IDリストの削除・増減処理
                    if round(order['remain']-abs(execute['lot']), 9) > 0:
                        # 部分約定の場合
                        order['remain'] = round(
                            order['remain'] - abs(execute['lot']), 9)  # 発注残数量を減らして
                        self._parameters.childorder_information.appendleft(
                            order)            # リストに戻す
                    else:
                        # 完全約定の場合
                        # 照合用リストからも対象のIDを検索して削除
                        with self._parameters.order_id_list_lock:
                            idx = self._parameters.childorder_id_list.index(
                                execute['id'][:-5])
                            self._parameters.childorder_id_list.rotate(-idx)
                            self._parameters.childorder_id_list.popleft()
                            self._parameters.childorder_id_list.rotate(idx)
                        # 完全約定カウント
                        self._parameters.order_filled_count[-1] += 1

                        if order['price'] != execute['price']:
                            self._parameters.order_taked[-1] += 1  # 成り行き約定カウント
                            self._logger.info("          TAKE!!!  order_price:{:.0f}  exec_price:{:.0f}".format(
                                order['price'], execute['price']))

                        # ChartCreator用のデータ書き出し
#                        self._write_exec_history( order['id'], order['side'], order['TTE'], order['price'], order['size'],
#                                                 "exec", time.time() if execute["date"]=="" else self.format_date(execute["date"],timedelta(hours=9)).timestamp(),
#                                                  execute["price"], abs(execute['lot']) )

                    # 約定価格とオーダー価格の差を保存（統計用）
                    slipage = int(execute['price']-order['price'] if order['side']
                                  == 'BUY' else order['price']-execute['price'])
                    self._parameters.slipage_history.append(
                        [datetime.utcnow()+timedelta(hours=9), slipage])
                    self._logger.debug("order:{}, exec:{} = slipage:{}".format(
                        order['price'], execute['price'], slipage))

                    # 想定ポジションを増減させる
                    self._parameters.estimated_position += execute['lot']

                    # 想定建玉の管理と想定利益計算
                    profit = 0
                    aveprice, possize = self.count_current_position()
                    if execute['lot'] > 0:
                        # 約定が買い注文の場合
                        if possize >= 0:
                            # 現在ポジが買い(または無し)なら、建玉リストに追加
                            self._parameters.current_position_list.append(
                                {'id': execute['id'], 'price': execute['price'], 'size': execute['lot'], 'side': 'BUY', 'timestamp': execute['timestamp']})
                            self._save_position(
                                {'id': execute['id'], 'price': execute['price'], 'size': execute['lot'], 'side': 'BUY'}, 0)

                        else:
                            # 現在ポジが売りなら、建玉リストからexecute['lot']分の建玉を削除
                            while execute['lot'] > 0:
                                if len(self._parameters.current_position_list) > 0:
                                    tg = self._parameters.current_position_list.popleft()
                                    if tg['side'] != 'SELL':
                                        self._logger.error(
                                            "Position list error!!!")
                                        self._logger.error(
                                            self._parameters.current_position_list)
                                        self._logger.error(
                                            self._parameters.estimated_position)

                                    if round(execute['lot']-tg['size'], 8) >= 0:
                                        # 建玉完全消化
                                        self._logger.debug("Clear position {} {} {:.0f} {:.3f} -> {} {:.0f} {:.3f} {}".format(
                                            tg['id'], tg['side'], tg['price'], tg['size'], order['side'], execute['price'], tg['size'], order['id']))
                                        profit += self.__calc_pofit(
                                            tg['price'], execute['price'], tg['size'], execute['id'], execute['date'])  # 利益
                                        execute['lot'] = round(
                                            execute['lot']-tg['size'], 8)
                                        self._save_position(
                                            {'id': tg['id'], 'price': 0, 'size': 0, 'side': 'CLEAR'}, 0)
                                    else:
                                        # 建玉部分消化
                                        self._logger.debug("Clear position {} {} {:.0f} {:.3f} -> {} {:.0f} {:.3f} {}".format(
                                            tg['id'], tg['side'], tg['price'], tg['size'], order['side'], execute['price'], execute['lot'], order['id']))
                                        profit += self.__calc_pofit(
                                            tg['price'], execute['price'], execute['lot'], execute['id'], execute['date'])  # 利益
                                        tg['size'] = round(
                                            tg['size']-execute['lot'], 8)
                                        execute['lot'] = 0
                                        self._parameters.current_position_list.appendleft(
                                            tg)
                                        self._save_position(tg, 0)
                                else:
                                    # 建玉がすべてなくなったらポジションファイルをクリア
                                    self.save_current_profit(True)
                                    # 建玉がすべてなくなったら新規に追加
                                    self._parameters.current_position_list.append(
                                        {'id': execute['id'], 'price': execute['price'], 'size': execute['lot'], 'side': 'BUY', 'timestamp': execute['timestamp']})
                                    self._save_position(
                                        {'id': execute['id'], 'price': execute['price'], 'size': execute['lot'], 'side': 'BUY'}, 0)
                                    execute['lot'] = 0

                    elif execute['lot'] < 0:
                        # 約定が売り注文の場合
                        if possize <= 0:
                            # 現在ポジが売り(または無し)なら、建玉リストに追加
                            self._parameters.current_position_list.append(
                                {'id': execute['id'], 'price': execute['price'], 'size': -execute['lot'], 'side': 'SELL', 'timestamp': execute['timestamp']})
                            self._save_position(
                                {'id': execute['id'], 'price': execute['price'], 'size': -execute['lot'], 'side': 'SELL'}, 0)

                        else:
                            # 現在ポジが買いなら、建玉リストからexecute['lot']分の建玉を削除
                            while execute['lot'] < 0:
                                if len(self._parameters.current_position_list) > 0:
                                    tg = self._parameters.current_position_list.popleft()
                                    if tg['side'] != 'BUY':
                                        self._logger.error(
                                            "Position list error!!!")
                                        self._logger.error(
                                            self._parameters.current_position_list)
                                        self._logger.error(
                                            self._parameters.estimated_position)

                                    if round(execute['lot']+tg['size'], 8) <= 0:
                                        # 建玉完全消化
                                        self._logger.debug("Clear position {} {} {:.0f} {:.3f} -> {} {:.0f} {:.3f} {}".format(
                                            tg['id'], tg['side'], tg['price'], tg['size'], order['side'], execute['price'], tg['size'], order['id']))
                                        profit += self.__calc_pofit(
                                            tg['price'], execute['price'], -tg['size'], execute['id'], execute['date'])  # 利益
                                        execute['lot'] = round(
                                            execute['lot']+tg['size'], 8)
                                        self._save_position(
                                            {'id': tg['id'], 'price': 0, 'size': 0, 'side': 'CLEAR'}, 0)
                                    else:
                                        self._logger.debug("Clear position {} {} {:.0f} {:.3f} -> {} {:.0f} {:.3f} {}".format(
                                            tg['id'], tg['side'], tg['price'], tg['size'], order['side'], execute['price'], -execute['lot'], order['id']))
                                        profit += self.__calc_pofit(
                                            tg['price'], execute['price'], execute['lot'], execute['id'], execute['date'])  # 利益
                                        tg['size'] = round(
                                            tg['size']+execute['lot'], 8)
                                        execute['lot'] = 0
                                        self._parameters.current_position_list.appendleft(
                                            tg)
                                        self._save_position(tg, 0)
                                else:
                                    # 建玉がすべてなくなったらポジションファイルをクリア
                                    self.save_current_profit(True)
                                    # 建玉がすべてなくなったら新規に追加
                                    self._parameters.current_position_list.append(
                                        {'id': execute['id'], 'price': execute['price'], 'size': -execute['lot'], 'side': 'SELL', 'timestamp': execute['timestamp']})
                                    self._save_position(
                                        {'id': execute['id'], 'price': execute['price'], 'size': -execute['lot'], 'side': 'SELL'}, 0)
                                    execute['lot'] = 0

                    if profit != 0:
                        self._parameters.estimated_profit += round(profit)
                        self._logger.info("          Profit {:+.0f}   Total profit {:+.0f}".format(
                            profit, self._parameters.estimated_profit))
                        self.save_current_profit(False, profit)

                    if len(self._parameters.current_position_list) == 0:
                        # 建玉がすべてなくなったらポジションファイルをクリア
                        self.save_current_profit(True)

                else:
                    if order['TTE'] > time_to_exprire:                # 残存時間がまだあるものは
                        self._parameters.childorder_information.append(
                            order)  # リストに戻す
                    else:
                        # apiから取得した発注リストから該当のIDを抜き出す (COMPLETED=対当売買で完了 EXPIRED=対当売買で部分約定)
                        alllist = [
                            x for x in self._parameters.childorders if x['child_order_acceptance_id'] == order['id']]
                        hitlist = [x for x in self._parameters.childorders if x['child_order_acceptance_id'] == order['id'] and (
                            x['child_order_state'] == 'COMPLETED' or x['child_order_state'] == 'EXPIRED')]

                        if len(hitlist) == 0:
                            executed_size = 0
                        elif len(hitlist) != 1:
                            self._logger.error("     Found multiple order informations (len:{}) id:{} {}".format(
                                len(hitlist), order['id'], alllist))
                            executed_size = 0
                        else:
                            # 自分の持っている残サイズとapiから取得した情報の残サイズの差（本来はゼロのはずだがこれが残っている場合には対当売買と考えられる)
                            executed_size = round(
                                float(order['remain'])-float(hitlist[0]['cancel_size']), 8)
                            self._logger.error(
                                "cross trading : {}".format(executed_size))
                            self._logger.debug(
                                "Expireing order information : {}".format(str(hitlist)))

                        if executed_size != 0 and self._parameters.check_cross_trade:
                            exec_treated = True
                            self._logger.info(
                                "          size different for : {}".format(str(order)))
                            # 疑似的に約定情報を作成して帳尻を合わせる（→　本来起きないはずなのでエラーで表示）
                            with self._parameters.executed_order_lock:
                                self._parameters.executed_order.appendleft(
                                    {'id': order['id']+'+0000', 'price': hitlist[0]['average_price'], 'lot': executed_size if hitlist[0]['side'] == 'BUY' else -executed_size, 'date': "", 'timestamp': time.time()})
                            self._logger.error("          HIT ======{}!!!  ({})  price:{:.0f}  size:{:.8f}".format(
                                hitlist[0]['side'], order['id'], hitlist[0]['average_price'], executed_size))

                            # 現在の注文リストを取得（デバッグのため
                            self.getchildorders()

                            # 未約定の注文リストを表示
                            rest = list(
                                self._parameters.childorder_information)
                            for r in rest:
                                self._logger.debug(
                                    "Open Orders : {}".format(r))
                                for x in [c for c in self._parameters.childorders if c['child_order_acceptance_id'] == r['id']]:
                                    self._logger.debug(
                                        "API Orders list : {}".format(x))

                            # 想定ポジション(速報値)を増減させる
                            if hitlist[0]['side'] == 'BUY':
                                self._parameters.estimated_position2 += executed_size
                            else:
                                self._parameters.estimated_position2 -= executed_size

                            # もう一回オーダー情報に戻す
                            self._parameters.childorder_information.appendleft(
                                order)  # リストに戻す

                        else:
                            # 期限切れの場合
                            # 照合用リストからも対象のIDを検索して削除
                            with self._parameters.order_id_list_lock:
                                idx = self._parameters.childorder_id_list.index(
                                    order['id'])
                                self._parameters.childorder_id_list.rotate(
                                    -idx)
                                self._parameters.childorder_id_list.popleft()
                                self._parameters.childorder_id_list.rotate(idx)

                            # 未約定キャンセル
                            if order['remain'] != order['size']:
                                # 部分約定
                                self._parameters.order_partial_filled_count[-1] += 1
                            else:
                                # キャンセル
                                self._parameters.order_not_filled_count[-1] += 1

                            # ChartCreator用のデータ書き出し
#                            self._write_exec_history( order['id'], order['side'], order['TTE'], order['price'], order['size'],
#                                                 "cancel", time.time(), order["price"], order['remain'] )

                if exec_treated == True:
                    break

            # 約定リストに入っていたのに、オーダー詳細に入っていない
            if exec_treated == False and execute != {}:
                self._logger.error(
                    "No order detail information in open orders.   id:{}".format(execute['id']))

                # 想定ポジション(速報値)を戻す
                self._parameters.estimated_position2 -= execute['lot']

                # 未約定の注文リストを表示
                rest = list(self._parameters.childorder_information)
                for r in rest:
                    self._logger.debug("Open Orders : {}".format(r))

            with self._parameters.executed_order_lock:
                order_len = len(self._parameters.executed_order)
            if order_len == 0:
                break

        # 自分の発注情報がキャンセルされたかどうかを順に確認
        for i in range(len(self._parameters.childorder_information)):
            order = self._parameters.childorder_information.popleft()
            if order['id'] not in list(self._parameters.canceled_child_order):
                self._parameters.childorder_information.append(order)
            else:
                # キャンセルされている場合、照合用リストからも対象のIDを検索して削除
                with self._parameters.order_id_list_lock:
                    idx = self._parameters.childorder_id_list.index(
                        order['id'])
                    self._parameters.childorder_id_list.rotate(-idx)
                    self._parameters.childorder_id_list.popleft()
                    self._parameters.childorder_id_list.rotate(idx)

        # 親注文のキャンセル情報をもとに発注リストから削除
        with self._parameters.order_id_list_lock:
            for i in range(len(self._parameters.canceled_parent_order)):
                order_id = self._parameters.canceled_parent_order.popleft()
                if order_id in self._parameters.parentorder_id_list:
                    idx = self._parameters.parentorder_id_list.index(order_id)
                    self._parameters.parentorder_id_list.rotate(-idx)
                    self._parameters.parentorder_id_list.popleft()
                    self._parameters.parentorder_id_list.rotate(idx)

        aveprice, possize = self.count_current_position()

        if self._parameters.estimated_position2 != self._parameters.estimated_position:
            self._logger.error("========= Position  size difference : {:.8f} ( {:.8f} , {:.8f} )".format(
                self._parameters.estimated_position2 - self._parameters.estimated_position, self._parameters.estimated_position2, self._parameters.estimated_position))
        self._parameters.estimated_position2 = self._parameters.estimated_position

        if old != self._parameters.estimated_position:
            self._logger.debug("          Position  size: {:.8f} -> {:.8f}({:.8f})    Changed {:+.8f}".format(
                old, self._parameters.estimated_position, self._parameters.estimated_position2, self._parameters.estimated_position-old))

        if round(possize-self._parameters.estimated_position, 8) != 0:
            self._logger.error("averageprice {:.0f}   avepos {:.8f}   Diff {:+.8f}".format(
                aveprice, possize, possize-self._parameters.estimated_position))

        # 建玉のリストを表示
        rest = list(self._parameters.current_position_list)
        if len(rest) > 0:
            message = 'Position List : '
            for r in rest:
                message = message + \
                    ' [{},{},{:.0f},{}]'.format(
                        r['id'], r['side'], r['price'], r['size'])
#            self._logger.log(5, message)

    def count_current_position(self):
        size = []
        price = []
        positions = list(self._parameters.current_position_list)

        if not positions:
            self._parameters.counted_position = 0
            self._parameters.counted_average_price = 0
            return 0, 0

        side = positions[0]['side']

        for pos in positions:
            price.append(pos['price'])
            size.append(pos['size'])
            if side != pos['side']:
                self._logger.error(
                    "Position list error!!!   {} != {}".format(side, pos['side']))
        average_price = round(sum(price[i] * size[i]
                                  for i in range(len(price))) / sum(size))
        sum_size = round(sum(size), 9)

        if round(sum_size, 8) == 0:
            self._parameters.current_position_list.clear()
            # 建玉がすべてなくなったらポジションファイルをクリア
            os.remove(self.__position_csvfilename())
            self._save_position({'id': '', 'price': 0, 'size': 0, 'side': 'PROFIT'}, round(
                self._parameters.estimated_profit))

        self._parameters.counted_average_price = average_price
        self._parameters.counted_position = round(
            float(sum_size if side == 'BUY' else -sum_size), 8)

        return self._parameters.counted_average_price, self._parameters.counted_position

    def getchildorders(self):
        with self._parameters.order_id_list_lock:
            if len(self._parameters.childorder_id_list) == 0 or self._parameters._strategy_class.sim_mode:
                return

        # 直近の子注文履歴(500件)を取得
        child_order_list = []
        try:
            start = time.time()
            child_order_list = self._api.getchildorders(
                product_code=self._parameters._config['product'], count=500)
            elapsed_time = (time.time()-start)*1000
            self._parameters.api_getorder_speed.append(elapsed_time)

            self._logger.debug('(getchildorders) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                self._api.LimitPeriod, self._api.LimitRemaining))

            if not child_order_list or "status" in child_order_list:
                self._logger.error(
                    "getchild order response : {}".format(child_order_list))
            elif not 'child_order_acceptance_id' in child_order_list[0]:
                self._logger.error(
                    "no child_order_acceptance_id in getchildorders : {}".format(child_order_list))
            else:
                self._parameters.childorders = child_order_list
                self._logger.debug("                      getchild orders  [date:{} - {}]    period{}      [{:.1f}]msec".format(child_order_list[0]['child_order_date'], child_order_list[-1]['child_order_date'],
                                                                                                                                self.format_date(child_order_list[0]['child_order_date'], timedelta(hours=9))-self.format_date(child_order_list[-1]['child_order_date'], timedelta(hours=9)), elapsed_time))

        except Exception as e:
            if child_order_list:
                self._logger.error(
                    "reply for getchildorders : {}".format(child_order_list))
            self._logger.exception(
                "Error while getting child orders : {}, {}".format(e, traceback.print_exc()))

        # API制限
        if child_order_list and "status" in str(child_order_list) and (child_order_list['status'] == -1 or child_order_list['status'] == -508):
            # 制限を食らった時にはDiscordにメッセージを投げる
            self._parent._send_discord("{}".format(child_order_list))
            self._parent.api_pending_time = time.time()+600  # api回数制限が落ち着くまでノートレードで待機 (10分固定)

    def sendparentorder(self, order_method, params, time_in_force="GTC"):
        start = time.time()
        callback = self._api.sendparentorder(
            order_method=order_method, minute_to_expire=self._parameters._strategy['minutes_to_expire'], time_in_force=time_in_force, parameters=params)
        self._logger.debug('(sendparentorder) PrivateAPI  OrderLimitPeriod:{} OrderLimitRemaining:{}'.format(
            self._api.OrderLimitPeriod, self._api.OrderLimitRemaining))

        if 'parent_order_acceptance_id' in callback:
            self._logger.debug("send parent orders in {:.3f}msec".format(
                (time.time()-start)*1000))
            # 発注後リストに追加 (約定履歴と突き合わせる)
            self._parameters.parentorder_id_list.append(
                callback['parent_order_acceptance_id'])    # websocketで迅速に照合させるためのリスト
            # order_methodを保管
            self._parameters.parentorder_method_dict[callback['parent_order_acceptance_id']] = order_method
            # 詳細なパラメータを保管
            self._parameters.parentorder_detail_param[callback['parent_order_acceptance_id']] = params

        return callback

    def sendchildorder(self, product_code, child_order_type, side, size, price, minute_to_expire=1, time_in_force="GTC", nocheck=False):
        callback = ''
        try:
            start = time.time()
            if size <= 0.1:
                self._parameters.api_counter_small_order[-1] += 1
            callback = self._api.sendchildorder(product_code=product_code, child_order_type=child_order_type,
                                                side=side, price=price, size=size, minute_to_expire=minute_to_expire, time_in_force=time_in_force)
            self._logger.debug('(sendchildorder) PrivateAPI  OrderLimitPeriod:{} OrderLimitRemaining:{}'.format(
                self._api.OrderLimitPeriod, self._api.OrderLimitRemaining))
            if nocheck:
                return callback
            if 'child_order_acceptance_id' in callback:
                self._parameters.api_sendorder_speed.append(
                    (time.time()-start)*1000)
                self._parameters.api_sendorder_speed_history[-1].append(
                    (time.time()-start)*1000)
                self._logger.debug("send child orders in {:.3f}msec".format(
                    (time.time()-start)*1000))

                # 発注後リストに追加 (約定履歴と突き合わせる)
                with self._parameters.order_id_list_lock:
                    self._parameters.childorder_id_list.append(
                        callback['child_order_acceptance_id'])    # websocketで迅速に照合させるためのリスト
                self._parameters.childorder_information.append({'id': callback['child_order_acceptance_id'], 'child_order_type': child_order_type, 'remain': size, 'side': side, 'TTE': int(
                    time.time()), 'price': self._parameters.ltp if price == 0 else price, 'size': size, 'parent_id': '', 'sendorder': start})  # update_current_positionで正確に計算させるためのリスト

                # オーダー時間統計用
                with self._parameters.server_accepted_time_lock:
                    self._parameters.server_accepted_time_detail.append(
                        {'id': callback['child_order_acceptance_id'], 'time': start, 'event': 'ORDER', 'accepted': time.time()})

                # オーダー回数統計用
                self._parameters.ordered_count[-1] += 1

                # 発行済みのIDがすでにwebsocketに流れてきていたら
                with self._parameters.executed_order_pending_rollback_lock:
                    if callback['child_order_acceptance_id'] in list(self._parameters.executed_order_pending):
                        self._logger.info(
                            "="*50 + "EXECUTIONS is already recieved".format(callback['child_order_acceptance_id']))
                        self._logger.info("pending list len:{} ({})".format(len(
                            self._parameters.executed_order_pending), self._parameters.executed_order_pending))
                        self._parameters.executed_order_pending_rollback = True

        except Exception as e:
            self._logger.info("Callback :{}".format(callback))
            self._logger.exception(
                "Error for sendchildorder : {}, {}".format(e, traceback.print_exc()))
            return ''

        # API制限
        if callback and "status" in str(callback) and (callback['status'] == -1 or callback['status'] == -508):
            # 制限を食らった時にはDiscordにメッセージを投げる
            self._parent._send_discord("{}".format(callback))
            self._parent.api_pending_time = time.time()+600  # api回数制限が落ち着くまでノートレードで待機 (10分固定)

        return callback

    def buy_order_limit_2(self, size, price, time_in_force="GTC"):
        self._last_ordered_time = time.time()
        return self.sendchildorder(product_code=self._product_code,
                                   child_order_type="LIMIT",
                                   side="BUY",
                                   size=round(size, 8),
                                   price=price,
                                   minute_to_expire=self._parameters._strategy['minutes_to_expire'],
                                   time_in_force=time_in_force
                                   )

    def sell_order_limit_2(self, size, price, time_in_force="GTC"):
        self._last_ordered_time = time.time()
        return self.sendchildorder(product_code=self._product_code,
                                   child_order_type="LIMIT",
                                   side="SELL",
                                   size=round(size, 8),
                                   price=price,
                                   minute_to_expire=self._parameters._strategy['minutes_to_expire'],
                                   time_in_force=time_in_force
                                   )

    def buy_order_limit(self, size, price, time_in_force="GTC"):
        retry_count = self._parameters.order_retry
        while retry_count >= 0:
            try:
                callback = self.buy_order_limit_2(size, price, time_in_force)
            except Exception:
                self._logger.error(str(callback))
                callback = ""

            if ("status" in callback or not callback or (callback and not "JRF" in str(callback))):
                if "status" in callback:
                    # "Order is not accepted. Please try again later."
                    if callback['status'] != -208:
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break

        return callback

    def sell_order_limit(self, size, price, time_in_force="GTC"):
        retry_count = self._parameters.order_retry
        while retry_count >= 0:
            try:
                callback = self.sell_order_limit_2(size, price, time_in_force)
            except Exception:
                self._logger.error(str(callback))
                callback = ""

            if ("status" in callback or not callback or (callback and not "JRF" in str(callback))):
                if "status" in callback:
                    # "Order is not accepted. Please try again later."
                    if callback['status'] != -208:
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break

        return callback

    def buy_order_market(self, size, nocheck=False):
        return self.sendchildorder(product_code=self._product_code,
                                   child_order_type="MARKET",
                                   side="BUY",
                                   size=round(size, 8),
                                   price=0,
                                   time_in_force="GTC",
                                   nocheck=nocheck
                                   )

    def sell_order_market(self, size, nocheck=False):
        return self.sendchildorder(product_code=self._product_code,
                                   child_order_type="MARKET",
                                   side="SELL",
                                   size=round(size, 8),
                                   price=0,
                                   time_in_force="GTC",
                                   nocheck=nocheck
                                   )

    def close_position_buy(self, size):
        retry_count = self._parameters.order_retry
        while retry_count >= 0:
            try:
                callback = self.buy_order_market(size)
            except Exception:
                self._logger.error(str(callback))
                callback = ""

            if ("status" in callback or not callback or (callback and not "JRF" in str(callback))):
                if "status" in callback:
                    # "Order is not accepted. Please try again later."
                    if callback['status'] != -208:
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break

        return callback

    def close_position_sell(self, size):
        retry_count = self._parameters.order_retry
        while retry_count >= 0:
            try:
                callback = self.sell_order_market(size)
            except Exception:
                self._logger.error(str(callback))
                callback = ""

            if ("status" in callback or not callback or (callback and not "JRF" in str(callback))):
                if "status" in callback:
                    # "Order is not accepted. Please try again later."
                    if callback['status'] != -208:
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break

        return callback

    def close_position(self, size):
        if size > 0:
            return self.close_position_sell(size)
        elif size < 0:
            return self.close_position_buy(-size)

    def cancel_all_orders(self):
        retry_count = self._parameters.cancel_retry
        while retry_count >= 0:
            callback = ''
            try:
                callback = self._api.cancelallchildorders(
                    product_code=self._product_code)
                self._logger.debug('(cancelallchildorders) PrivateAPI  OrderLimitPeriod:{} OrderLimitRemaining:{}'.format(
                    self._api.OrderLimitPeriod, self._api.OrderLimitRemaining))
                if not callback:
                    return callback
            except Exception:
                pass
            self._logger.error(str(callback))
            retry_count -= 1
            self._parameters.order_retry_count[-1] += 1
            time.sleep(0.1)

        return callback

    def cancel_childorder(self, id):
        with self._parameters.order_id_list_lock:
            checklist = list(self._parameters.childorder_id_list)
            if id not in checklist:
                return 'order is already completed or expired'

        retry_count = self._parameters.cancel_retry
        while retry_count >= 0:
            callback = ''
            try:
                start = time.time()
                with self._parameters.server_accepted_time_lock:
                    self._parameters.server_accepted_time_detail.append(
                        {'id': id, 'time': time.time(), 'event': 'CANCEL'})
                self._parameters.cancel_child_id_list.append(id)
                callback = self._api.cancelchildorder(
                    product_code=self._product_code, child_order_acceptance_id=id)
                self._logger.debug('(cancelchildorder) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                    self._api.LimitPeriod, self._api.LimitRemaining))
                self._parameters.api_cancel_speed.append(
                    (time.time()-start)*1000)
                self._parameters.api_cancel_speed_history[-1].append(
                    (time.time()-start)*1000)

                if not callback:
                    return callback
            except Exception:
                pass
            self._logger.error(str(callback))
            if "status" in callback:
                if "status" in callback:
                    if callback['status'] == -111:  # 'Order not found' はリトライしない
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break
        return callback

    def cancel_parentorder(self, id):
        checklist = list(self._parameters.parentorder_id_list)
        if id not in checklist:
            return 'order is already completed or expired'

        retry_count = self._parameters.cancel_retry
        while retry_count >= 0:
            callback = ''
            try:
                callback = self._api.cancelparentorder(
                    product_code=self._product_code, parent_order_acceptance_id=id)
                self._logger.debug('(cancelparentorder) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                    self._api.LimitPeriod, self._api.LimitRemaining))

                if not callback:
                    break
            except Exception:
                pass
            self._logger.error(str(callback))
            if "status" in callback:
                if "status" in callback:
                    if callback['status'] == -111:  # 'Order not found' はリトライしない
                        retry_count = 0
                retry_count -= 1
                self._parameters.order_retry_count[-1] += 1
                time.sleep(0.1)
            else:
                break

        return callback

    def _getpositions_api(self):
        positions = {}
        try:
            if self._parameters._config['product'] != 'BTC_JPY':
                size = []
                price = []
                positions = self._api.getpositions(
                    product_code=self._parameters._config['product'])
                self._logger.debug('(getpositions) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                    self._api.LimitPeriod, self._api.LimitRemaining))

                if not positions:
                    return 0

                if "status" in positions:
                    self._logger.error(
                        "reply for getpos : {}".format(positions))

                    # API制限
                    if positions['status'] == -1 or positions['status'] == -508:
                        self._parent.api_pending_time = time.time()+600  # api回数制限が落ち着くまでノートレードで待機 (10分固定)

                    return 0

                if "Message" in positions:
                    self._logger.error(
                        "reply for getpos : {}".format(positions))
                    return 0

                for pos in positions:
                    if "product_code" in pos:
                        self._logger.debug('          '+str(pos))
                        size.append(pos["size"])
                        price.append(pos["price"])
                        side = pos["side"]

#                average_price = round(sum(price[i] * size[i] for i in range(len(price))) / sum(size))
                sum_size = round(sum(size), 9)

                return round(float(sum_size if side == 'BUY' else -sum_size), 8)

            else:
                positions = self._api.getbalance()
                self._logger.debug('(getbalance) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                    self._api.LimitPeriod, self._api.LimitRemaining))

                if not positions:
                    return 0

                if "status" in positions:
                    self._logger.error(
                        "reply for getbalance : {}".format(positions))

                    # API制限
                    if positions['status'] == -1 or positions['status'] == -508:
                        self._parent.api_pending_time = time.time()+600  # api回数制限が落ち着くまでノートレードで待機 (10分固定)

                    return 0

                if "Message" in positions:
                    self._logger.error(
                        "reply for getbalance : {}".format(positions))
                    return 0

                for pos in positions:
                    if 'currency_code' in pos and pos['currency_code'] == 'JPY':
                        self._parameters.balance = pos

                for pos in positions:
                    if 'currency_code' in pos and pos['currency_code'] == 'BTC':
                        return pos['amount']

                return 0

        except Exception as e:
            if positions:
                self._logger.error(
                    "reply for getbalance : {}".format(positions))
            self._logger.exception(
                "Error from getbalance : {}, {}".format(e, traceback.print_exc()))
            return 0

    def _getcollateral_api(self):
        response = ''
        try:
            response = self._api.getcollateral()
            self._logger.debug('(getcollateral) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                self._api.LimitPeriod, self._api.LimitRemaining))

            if not response:
                self._logger.error("reply for getcollateral is Null")
                return self._parameters.collateral

            if "status" in response:
                self._logger.error(
                    "reply for getcollateral : {}".format(response))
                return self._parameters.collateral

            if "Message" in response:
                self._logger.error(
                    "reply for getcollateral : {}".format(response))
                return self._parameters.collateral

            self._parameters.collateral = response
            return self._parameters.collateral

        except Exception as e:
            if response:
                self._logger.error(
                    "reply for getcollateral : {}".format(response))
            self._logger.exception(
                "Error from getcollateral : {}, {}".format(e, traceback.print_exc()))
            return self._parameters.collateral
