# coding: utf-8
import websocket
from threading import Thread
import time
from secrets import token_hex
from hashlib import sha256
import hmac
import json


class RealtimeAPIWebsocket:
    def __init__(self, logger, parameters, public_handler, private_handler):
        self.logger = logger
        self._parameters = parameters
        self._ws = None

        self.auth_retry = 0
        self.auth_try_time = 0
        self.auth_completed = False

        self.RealtimeAPIWebsocket(public_handler, private_handler)

    def _auth(self):
        self.auth_try_time = time.time()
        if self._parameters._config['apikey'] == '' or self._parameters._config['secret'] == '':
            return
        now = int(time.time())
        nonce = token_hex(16)
        sign = hmac.new(self._parameters._config['secret'].encode(
            'utf-8'), ''.join([str(now), nonce]).encode('utf-8'), sha256).hexdigest()
        params = {'method': 'auth', 'params': {
            'api_key': self._parameters._config['apikey'], 'timestamp': now, 'nonce': nonce, 'signature': sign}, 'id': 1}
        self.logger.info("Auth process started")
        self._ws.send(json.dumps(params))

    def auth_check(self):
        # Private channelの認証が完了していない　& 前回のチャレンジから1分以上経過で再トライ
        if self.auth_try_time+60 < time.time() and not self.auth_completed:
            self.auth_retry = 0
            self._auth()
        return self.auth_completed

    def RealtimeAPIWebsocket(self, public_handler, private_handler):
        # ハンドラ呼び出し
        def handler(func, *args):
            return func(*args)

        def on_message(ws, message):

            messages = json.loads(message)

            # auth レスポンスの処理
            if 'id' in messages and messages['id'] == 1:
                if 'error' in messages and self.auth_retry < 10:
                    self.logger.error(
                        'auth error: {}  retry({})'.format(messages["error"], self.auth_retry))
                    self.auth_retry += 1
                    self._auth()

                elif 'result' in messages and messages['result'] == True:
                    self.auth_retry = 0
                    params = [{'method': 'subscribe', 'params': {
                        'channel': c}} for c in private_handler]

                    self.logger.info("Websocket auth successed")
                    mention = '' if not 'websocket_auth' in self._parameters._strategy else self._parameters._strategy[
                        'websocket_auth']+'\n'
                    self.auth_completed = True
                    if self._parameters.no_trade_period:
                        mention = ''  # ノートレード期間はメンション送らない（メンテ時間に毎日メンション来てウザいので）
                    self._parameters._message = mention+"Websocket auth successed"
                    self._parameters._parameter_message_send()
                    self.logger.debug(
                        "send private api subscribe {}".format(params))
                    ws.send(json.dumps(params))

                return

            if messages['method'] != 'channelMessage':
                return

            params = messages["params"]
            channel = params["channel"]
            recept_data = params["message"]

            realtime_handler = public_handler.get(channel)
            if realtime_handler != None:
                realtime_handler(recept_data)
                return

            realtime_handler = private_handler.get(channel)
            if realtime_handler != None:
                realtime_handler(recept_data)
                return

        def on_error(ws, error):
            self.logger.error(error)

        def on_close(ws):
            self.auth_completed = False
            self._ws = None
            self.logger.info("Websocket closed")
            mention = '' if not 'websocket_close' in self._parameters._strategy else self._parameters._strategy[
                'websocket_close']+'\n'
            if self._parameters.no_trade_period:
                mention = ''  # ノートレード期間はメンション送らない（メンテ時間に毎日メンション来てウザいので）
            self._parameters._message = mention+"Websocket closed"
            self._parameters._parameter_message_send()

        def on_open(ws):
            self.auth_completed = False
            self._ws = ws
            self.logger.info("Websocket connected")
            mention = '' if not 'websocket_connect' in self._parameters._strategy else self._parameters._strategy[
                'websocket_connect']+'\n'
            self._parameters._message = mention+"Websocket connected"
            self._parameters._parameter_message_send()
            params = [{'method': 'subscribe', 'params': {'channel': c}}
                      for c in public_handler]
            ws.send(json.dumps(params))

            self._auth()

        def run(ws):
            while True:
                ws.run_forever()
                time.sleep(3)

        ws = websocket.WebSocketApp("wss://ws.lightstream.bitflyer.com/json-rpc",
                                    on_message=on_message, on_error=on_error, on_close=on_close)
        ws.on_open = on_open
        websocketThread = Thread(target=run, args=(ws, ))
        websocketThread.start()
