# -*- coding: utf-8 -*-
from threading import Event

# それぞれのメンバ・関数は、親クラス(backtestまたはtrade)を呼び出す


class Strategy:

    order_signal_event = Event()
    execution_event = Event()
    spot_ticker_event = Event()

    def __init__(self, logger, parent):
        self._logger = logger
        self._parent = parent

    def initialize_logic(self):
        initialize_func = None
        try:
            initialize_func = self.initialize
        except:
            pass
        if initialize_func != None:
            return self.initialize()

    def set_strategy_config(self, strategy_config):
        self._strategy_config = strategy_config

    @property
    def product(self):
        return self._parent.product

    @property
    def execution_timestamp(self):
        return self._parent._execution_timestamp

    @property
    def board_timestamp(self):
        return self._parent._board_timestamp

    @property
    def is_backtesting(self):
        return self._parent._is_backtesting

    @property
    def candle_date(self):
        return self._parent._candle_date

    @property
    def candle_date_list(self):
        return self._parent._candle_date_list

    @property
    def exec_date(self):
        return self._parent._exec_date

    @property
    def open(self):
        return self._parent._open

    @property
    def high(self):
        return self._parent._high

    @property
    def low(self):
        return self._parent._low

    @property
    def close(self):
        return self._parent._close

    @property
    def volume(self):
        return self._parent._volume

    @property
    def buy_volume(self):
        return self._parent._buy_volume

    @property
    def sell_volume(self):
        return self._parent._sell_volume

    @property
    def count(self):
        return self._parent._count

    @property
    def buy_count(self):
        return self._parent._buy_count

    @property
    def sell_count(self):
        return self._parent._sell_count

    @property
    def total_value(self):
        return self._parent._total_value

    @property
    def current_pos(self):
        return self._parent._pos

    @property
    def current_average(self):         # バックテスト非対応
        return self._parent._average

    @property
    def current_profit(self):          # バックテスト非対応
        return self._parent._profit

    @property
    def current_fixed_profit(self):          # バックテスト非対応
        return self._parent._fixed_profit

    @current_profit.setter
    def current_profit(self, pnl):
        return

    def reset_profit(self):
        self._parent._reset_profit()

    @property
    def current_profit_unreal(self):   # バックテスト非対応
        return self._parent._profit_unreal

    @property
    def server_latency(self):          # バックテスト非対応
        return self._parent._server_latency

    @property
    def server_latency_rate(self):     # バックテスト非対応
        return self._parent._server_latency_rate

    @property
    def server_health(self):           # バックテスト非対応
        return self._parent._server_health

    @property
    def ltp(self):
        return self._parent._ltp

    @property
    def sfd(self):
        return self._parent._sfd     # バックテスト非対応

    @property
    def spotprice(self):
        return self._parent._spot    # バックテスト非対応

    @property
    def spotprice_exec(self):
        return self._parent._spot_exec    # バックテスト非対応

    @property
    def sfd_commission(self):
        return self._parent._sfd_commission     # バックテスト非対応

    @property
    def best_ask(self):
        return self._parent._best_ask

    @property
    def best_bid(self):
        return self._parent._best_bid

    @property
    def current_candle(self):
        return self._parent._current_candle

    @property
    def api_count(self):
        return self._parent._api_count_per_user

    @property
    def api_order_count(self):
        return self._parent._api_order_count_per_user

    @property
    def api_count2(self):
        return self._parent._api_count2

    @property
    def api_count_total(self):
        return self._parent._api_count_total

    @property
    def from_lastcandle_update(self):
        return self._parent._from_lastcandle_update

    def fetch_cryptowatch_candle(self, minutes=1):
        return self._parent._fetch_cryptowatch(minutes)

    @property
    def cryptowatch_candle(self):
        return self._parent._get_cryptowatch()

    def _childorder(self, type, side, size, price=0, time_in_force="GTC"):
        if type == "LIMIT":
            if side == "BUY":
                return self._limit_buy(price=round(price), size=round(size, 8), time_in_force=time_in_force)
            else:
                return self._limit_sell(price=round(price), size=round(size, 8), time_in_force=time_in_force)
        else:
            if side == "BUY":
                return self._market_buy(size=round(size, 8))
            else:
                return self._market_sell(size=round(size, 8))

    def _limit_buy(self, price, size, time_in_force="GTC"):
        return self._parent._limit_buy(price=round(price), size=round(size, 8), time_in_force=time_in_force)

    def _limit_sell(self, price, size, time_in_force="GTC"):
        return self._parent._limit_sell(price=round(price), size=round(size, 8), time_in_force=time_in_force)

    def _market_buy(self, size, nocheck=False):
        return self._parent._market_buy(size=round(size, 8), nocheck=nocheck)

    def _market_sell(self, size, nocheck=False):
        return self._parent._market_sell(size=round(size, 8), nocheck=nocheck)

    def _close_position(self):
        return self._parent._close_position()

    def _cancel_all_orders(self):                     # バックテスト非対応
        return self._parent._cancel_all_orders()

    def _cancel_childorder(self, id):                  # バックテスト非対応
        return self._parent._cancel_childorder(id)

    def _cancel_parentorder(self, id):                  # バックテスト非対応
        return self._parent._cancel_parentorder(id)

    def _get_effective_tick(self, size_thru, startprice=0, limitprice=1000):    # バックテスト非対応
        return self._parent._get_effective_tick(size_thru, startprice, limitprice)

    def _get_board(self):                  # バックテスト非対応
        return self._parent._get_board()

    def _get_spot_board(self):                  # バックテスト非対応
        return self._parent._get_spot_board()

    @property
    def mid_price(self):
        return self._parent.mid_price

    @property
    def board_age(self):
        return self._parent.board_age

    def _get_board_api(self):              # バックテスト非対応
        return self._parent._get_board_api()

    def _get_positions(self):              # バックテスト非対応
        return self._parent._get_positions()

    def _update_position(self):            # バックテスト非対応
        return self._parent._order.update_current_position()

    def _send_discord(self, message, image_file=None):
        return self._parent._send_discord(message, image_file)

    def _get_balance(self, refresh=False):
        return self._parent._get_balance(refresh)     # バックテスト非対応

    def _getcollateral_api(self):          # バックテスト非対応
        return self._parent._getcollateral_api()

    @property
    def _initial_collateral(self):          # バックテスト非対応
        return self._parent._initial_collateral

    @property
    def ordered_list(self):          # バックテスト非対応
        return self._parent._ordered_list

    @property
    def parentorder_ordered_list(self):          # バックテスト非対応
        return self._parent._parentorder_ordered_list

    @property
    def no_trade_period(self):
        return self._parent.no_trade_period

    @property
    def _minimum_order_size(self):
        return self._parent._minimum_order_size

    @property
    def log_folder(self):
        return self._parent.log_folder

    @property
    def executed_history(self):
        return self._parent.executed_history

    @property
    def sim_mode(self):
        return False

    def hit_check(self, recept_data):
        return

    def _parentorder(self, params, method='SIMPLE', time_in_force="GTC"):
        return self._parent._parentorder(order_method=method, params=params, time_in_force=time_in_force)

    # type: LIMIT / MARKET / STOP / STOP_LIMIT / TRAIL
    # side: BUY / SELL
    def order(self, type, side, size, price=0, trigger=0, offset=0):
        if type == 'MARKET':
            return {"product_code": self.product, "condition_type": type, "side": side, "size": round(size, 8)}
        elif type == 'LIMIT':
            if price == 0:
                self._logger.error("LIMIT order require [price]")
                raise Exception
            return {"product_code": self.product, "condition_type": type, "side": side, "size": round(size, 8), "price": round(price)}
        elif type == 'STOP':
            if trigger == 0:
                self._logger.error("STOP order require [trigger]")
                raise Exception
            return {"product_code": self.product, "condition_type": type, "side": side, "size": round(size, 8), "trigger_price": round(trigger)}
        elif type == 'STOP_LIMIT':
            if price == 0 or trigger == 0:
                self._logger.error(
                    "STOP_LIMIT order require [price] and [trigger]")
                raise Exception
            return {"product_code": self.product, "condition_type": type, "side": side, "size": round(size, 8), "trigger_price": round(trigger), "price": round(price)}
        elif type == 'TRAIL':
            if offset == 0:
                self._logger.error("TRAIL order require [offset]")
                raise Exception
            return {"product_code": self.product, "condition_type": type, "side": side, "size": round(size, 8), "offset": round(offset)}
