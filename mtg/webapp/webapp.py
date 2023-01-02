import logging
import time
#
from datetime import datetime, timedelta
from threading import Thread
from typing import (
    AnyStr,
)
from urllib.parse import parse_qs
#
import flask
#
from flask import Flask, jsonify, make_response, request, render_template
from flask.views import View
from werkzeug.serving import make_server
#
from mtg.config import Config
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import MeshtasticDB

#
class RenderTemplateView(View):
    """
    Generic HTML template renderer
    """

    def __init__(self, template_name):
        self.template_name = template_name

    def dispatch_request(self) -> AnyStr:
        """
        Process Flask request

        :return:
        """
        return render_template(self.template_name, timestamp=int(time.time()))


class RenderScript(View):
    """
    Specific script renderer
    """

    def __init__(self, config: Config):
        self.config = config

    def dispatch_request(self) -> flask.Response:
        """
        Process Flask request

        :return:
        """
        response = make_response(render_template(
            "script.js",
            api_key=self.config.WebApp.APIKey,
            redraw_markers_every=self.config.WebApp.RedrawMarkersEvery,
            center_latitude=self.config.enforce_type(float, self.config.WebApp.Center_Latitude),
            center_longitude=self.config.enforce_type(float, self.config.WebApp.Center_Longitude),
        ))
        response.headers['Content-Type'] = 'application/javascript'
        return response


class RenderDataView(View):
    """
    Specific data renderer
    """

    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: MeshtasticConnection, logger: logging.Logger):
        self.database = database
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection

    @staticmethod
    def format_hw(hw_model: AnyStr) -> AnyStr:
        """
        Format hardware model

        :param hw_model:
        :return:
        """
        if hw_model == 'TBEAM':
            return '<a href="https://meshtastic.org/docs/hardware/supported/tbeam">TBEAM</a>'
        if hw_model.startswith('TLORA'):
            return '<a href="https://meshtastic.org/docs/hardware/supported/lora">TLORA</a>'
        if hw_model.startswith('T_ECHO'):
            return '<a href="https://meshtastic.org/docs/hardware/devices/techo">T-ECHO</a>'
        if hw_model.startswith('DIY'):
            return '<a href="https://meshtastic.discourse.group/t/meshtastic-diy-project/3831/1">DIY</a>'
        return hw_model

    def dispatch_request(self) -> flask.Response:  # pylint:disable=too-many-locals
        """
        Process Flask request

        :return:
        """
        query_string = parse_qs(request.query_string)
        tail_value = self.config.enforce_type(int, self.config.WebApp.LastHeardDefault)
        #
        tail = query_string.get(b'tail', [])
        if len(tail) > 0:
            try:
                tail_value = int(tail[0].decode())
            except ValueError:
                self.logger.error("Wrong tail value: ", tail)
        #
        name = ''
        name_qs = query_string.get(b'name', [])
        if len(name_qs) > 0:
            name = name_qs[0].decode()
        nodes = []
        for node_info in self.meshtastic_connection.nodes_with_user:
            device_metrics = node_info.get('deviceMetrics', {})
            position = node_info.get('position', {})
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not (latitude and longitude):
                try:
                    latitude, longitude = self.database.get_last_coordinates(node_info.get('id'))
                except RuntimeError:
                    continue
            user = node_info.get('user', {})
            hw_model = user.get('hwModel', 'unknown')
            snr = node_info.get('snr', 10.0)
            # No signal info, use default MAX (10.0)
            if snr is None:
                snr = 10.0
            last_heard = int(node_info.get('lastHeard', 0))
            last_heard_dt = datetime.fromtimestamp(last_heard)
            battery_level = position.get('batteryLevel', 100)
            altitude = position.get('altitude', 0)
            # tail filter
            diff = datetime.fromtimestamp(time.time()) - last_heard_dt
            if diff > timedelta(seconds=tail_value):
                continue
            # name filter
            if len(name) > 0 and user.get('longName') != name:
                continue
            # Channel and Air utilization
            ch_util = int(device_metrics.get('channelUtilization', 0))
            air_util = int(device_metrics.get('airUtilTx', 0))
            #
            nodes.append([user.get('longName'), str(round(latitude, 5)),
                          str(round(longitude, 5)), self.format_hw(hw_model), snr,
                          last_heard_dt.strftime("%d/%m/%Y, %H:%M:%S"),
                          battery_level,
                          altitude,
                          ch_util,
                          air_util,
                          ])
        return jsonify(nodes)


class RenderAirRaidView(View):
    """
    Air Raid Alert renderer
    """

    # pylint:disable=too-many-arguments
    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger):
        self.database = database
        self.config = config
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.logger = logger
        self.region_table = {3: 'Khmelnystjka', 4: 'Vinnytsjka', 5: 'Rivnenska',
                             8: 'Volynska', 9: 'Dnipro', 10: 'Zhytomyrska',
                             11: 'Zakarpattya', 12: 'Zaporizhzhja', 13: 'Ivano-Fr',
                             14: 'Kyiv obl', 15: 'Kirovohrad',  16: 'Luhansk',
                             17: 'Mykolaiv',  18: 'Odesa',  19: 'Poltava',
                             20: 'Sumy',  21: 'Ternopil',  22: 'Kharkiv',
                             23: 'Kherson',  24: 'Cherkasy',  25: 'Chernihiv',
                             26: 'Chernivtsi', 27: 'Lviv', 28: 'Donetsjk',
                             31: 'Kyiv', 9999: 'Krym'}

    def dispatch_request(self) -> AnyStr:
        """
        Process Flask request

        :return:
        """
        msg = request.get_json()
        alert_type = msg.get('alarmType')
        region_id = msg.get('regionId', 0)
        alert_place = self.region_table.get(region_id)
        alert_status = msg.get('status')
        alert_tz = msg.get('createdAt')
        dt_f = datetime.strptime(alert_tz, '%Y-%m-%dT%H:%M:%SZ')
        tzinfo = datetime.now().astimezone().tzinfo
        dt_f = dt_f + tzinfo.utcoffset(None)
        alert_time = dt_f.strftime("%H:%M:%S")
        print(msg)
        if region_id in [14, 31] and self.config.enforce_type(bool, self.config.WebApp.AirRaidEnabled):
            new_msg = f'Alert: {alert_type}, {alert_place}, {alert_status} since {alert_time}'
            self.telegram_connection.send_message(chat_id=self.config.enforce_type(int,
                                                                               self.config.Telegram.NotificationsRoom),
                                                  text=new_msg)
            self.meshtastic_connection.send_text(new_msg)
        return 'Ok'


class WebApp:  # pylint:disable=too-few-public-methods
    """
    WebApp: web application container
    """
    # pylint:disable=too-many-arguments
    def __init__(self, database: MeshtasticDB, app: Flask, config: Config,
                 meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger):
        self.database = database
        self.app = app
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection

    def register(self) -> None:
        """
        Register Flask routes

        :return:
        """
        self.app.add_url_rule('/script.js', view_func=RenderScript.as_view(
            'script_page', config=self.config))
        self.app.add_url_rule('/data.json', view_func=RenderDataView.as_view(
            'data_page',
            database=self.database,
            config=self.config,
            meshtastic_connection=self.meshtastic_connection, logger=self.logger))
        # This should be moved out to separate directory
        self.app.add_url_rule('/airraid/' + self.config.enforce_type(str, self.config.WebApp.AirRaidPrivate),
                              view_func=RenderAirRaidView.as_view(
                              'airraid_page',
                              database=self.database,
                              config=self.config,
                              meshtastic_connection=self.meshtastic_connection,
                              telegram_connection=self.telegram_connection,
                              logger=self.logger), methods=['POST'])
        self.app.add_url_rule('/airraid/' + self.config.enforce_type(str, self.config.WebApp.AirRaidPrivate) + '/',
                              view_func=RenderAirRaidView.as_view(
                              'airraid_page_with_slash',
                              database=self.database,
                              config=self.config,
                              meshtastic_connection=self.meshtastic_connection,
                              telegram_connection=self.telegram_connection,
                              logger=self.logger), methods=['POST'])
        # Index pages
        self.app.add_url_rule('/', view_func=RenderTemplateView.as_view(
            'root_page', template_name='index.html'))
        self.app.add_url_rule('/index.htm', view_func=RenderTemplateView.as_view(
            'index_page', template_name='index.html'))
        self.app.add_url_rule('/index.html', view_func=RenderTemplateView.as_view(
            'index_html_page', template_name='index.html'))


class ServerThread(Thread):
    """
    Web application server thread
    """
    def __init__(self, app: Flask, config: Config, logger: logging.Logger):
        Thread.__init__(self)
        self.config = config
        self.logger = logger
        self.server = make_server('', self.config.enforce_type(int, self.config.WebApp.Port), app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self) -> None:
        """

        :return:
        """
        self.logger.info('starting server')
        self.server.serve_forever()

    def shutdown(self) -> None:
        """

        :return:
        """
        self.server.shutdown()


class WebServer:  # pylint:disable=too-few-public-methods
    """
    Web server wrapper around Flask app
    """
    # pylint:disable=too-many-arguments
    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: MeshtasticConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger):
        self.database = database
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.config = config
        self.logger = logger
        self.app = Flask(__name__)
        self.server = None

    def run(self) -> None:
        """
        Run web server

        :return:
        """
        if self.config.enforce_type(bool, self.config.WebApp.Enabled):
            web_app = WebApp(self.database, self.app, self.config,
                             self.meshtastic_connection,
                             self.telegram_connection,
                             self.logger)
            web_app.register()
            self.server = ServerThread(self.app, self.config, self.logger)
            self.server.start()

    def shutdown(self) -> None:
        """
        Web server shutdown method

        :return:
        """
        self.server.shutdown()
