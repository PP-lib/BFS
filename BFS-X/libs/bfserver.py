# coding: utf-8
import pybitflyer
import time

# パブリックapiを使ってサーバービジーをチェック


class Health:
    def __init__(self, logger, parameters):
        self._publicapi = pybitflyer.API()
        self._logger = logger
        self._parameters = parameters
        self._timelast = 0   # 前回 ヘルスチェック を実行した時間
        self._parameters.server_health = "OTHER"
        self._last_board = {'mid_price': 0, 'bids': [], 'asks': []}

    # 取引所のヘルスチェック
    # "NORMAL", "BUSY", "VERY BUSY", "SUPER BUSY, "STOP", "FAIL", "OTHER"
    def status(self):

        timenow = time.time()
        # 前回の問い合わせからinterval_health_check(秒)経っていないときには、前回の結果を返す。頻繁にAPI呼び出しをしないように
        if (timenow-self._timelast) < self._parameters._config['interval_health_check']-0.1:
            return self._parameters.server_health

        self._timelast = time.time()
        try:
            self._parameters.api_counter[-1] += 1
            boardState = self._publicapi.getboardstate(
                product_code=self._parameters._config['product'])
            if boardState["state"] != "RUNNING":
                server_health = "STOP"
            elif boardState["health"] in ["NORMAL", "BUSY", "VERY BUSY", "SUPER BUSY"]:
                server_health = boardState["health"]
            else:
                self._logger.info("Health status :{}".format(boardState))
                server_health = "OTHER"
        except:
            self._logger.error("Health check failed")
            server_health = "FAIL"

        if server_health in ["SUPER BUSY", "OTHER", "FAIL"]:
            self._parameters.superbusy_happend = True

        self._parameters.server_health = server_health

        self._logger.debug('PublicAPI LimitPeriod:{} LimitRemaining:{}  LimitReset:{}  time:{}'.format(
            self._publicapi.LimitPeriod, self._publicapi.LimitRemaining, self._publicapi.LimitReset, int(time.time())))

        return server_health

    # 取引所の板情報取得
    # 戻り値
    #  {'mid_price': 588401,
    #   'bids': [{'price': 588382.0, 'size': 0.05021743}, {'price': 588381.0, 'size': 0.01}, ....],
    #   'asks': [{'price': 588404.0, 'size': 2.91807838}, {'price': 588423.0, 'size': 0.01474511},...] }
    def board(self):
        try:
            self._parameters.api_counter[-1] += 1
            value = self._publicapi.board(
                product_code=self._parameters._config['product'])
            if 'mid_price' in value:
                self._last_board = value
            else:
                self._logger.error(value)
        except Exception as e:
            self._logger.error(e)

        return self._last_board
