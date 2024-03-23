# -*- coding: utf-8 -*-
""" Web application module """

import logging
import os
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
from flask import Flask, jsonify, make_response, request, render_template, send_file
from flask.views import View
from flask.typing import ResponseReturnValue
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.serving import make_server
#
from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import MeshtasticDB
from mtg.utils import Memcache


class CommonView(View):
    """
    Common view class
    """

    def get_tail(self, config, logger):
        """
        get_tail - get tail value from query string

        :return:
        """
        query_string = parse_qs(request.query_string.decode())
        tail_value = config.enforce_type(int, config.WebApp.LastHeardDefault)
        #
        tail = query_string.get('tail', [])
        if len(tail) > 0:
            try:
                tail_value = int(tail[0])
            except ValueError:
                logger.error("Wrong tail value: ", tail)
        name_qs = query_string.get('name', [])
        name = name_qs[0] if len(name_qs) > 0 else ''
        return name, tail_value

    def dispatch_request(self) -> ResponseReturnValue:
        """The actual view function behavior. Subclasses must override
        this and return a valid response. Any variables from the URL
        rule are passed as keyword arguments.
        """
        raise NotImplementedError()


class RenderTemplateView(CommonView):
    """
    Generic HTML template renderer
    """

    def __init__(self, template_name, config):
        self.template_name = template_name
        self.config = config

    def dispatch_request(self) -> AnyStr:
        """
        Process Flask request

        :return:
        """
        debug = self.config.enforce_type(bool, self.config.DEFAULT.Debug)
        sentry_enabled = self.config.enforce_type(bool, self.config.DEFAULT.SentryEnabled)
        sentry_dsn = self.config.DEFAULT.SentryDSN
        return render_template(self.template_name, debug=debug,
                               sentry_enabled=sentry_enabled,
                               sentry_dsn=sentry_dsn, timestamp=int(time.time()), )


class RenderFavicon(CommonView):
    """
    RenderFavicon - favicon.ico file renderer
    """

    def dispatch_request(self) -> flask.Response:
        return send_file(os.path.abspath('web/static/images/favicon.ico'),
                         mimetype='image/x-icon')


class RenderScript(CommonView):
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
            debug=self.config.enforce_type(bool, self.config.DEFAULT.Debug),
            sentry_enabled=self.config.enforce_type(bool, self.config.DEFAULT.SentryEnabled),
            sentry_dsn=self.config.DEFAULT.SentryDSN
        ))
        response.headers['Content-Type'] = 'application/javascript'
        return response


class RenderTrackView(CommonView):
    """
    Specific data renderer
    """

    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: RichConnection, logger: logging.Logger):
        self.database = database
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection

    def dispatch_request(self) -> flask.Response:  # pylint:disable=too-many-locals
        """
        Process Flask request

        :return:
        """
        name, tail_value = self.get_tail(self.config, self.logger)
        return jsonify(self.database.get_node_track(name, tail_value)) if len(name) > 0 else jsonify([])


class RenderDataView(CommonView):
    """
    Specific data renderer
    """

    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: RichConnection, logger: logging.Logger):
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
        hw_map = {
            'TBEAM': '<a href="https://meshtastic.org/docs/hardware/devices/tbeam/">TBEAM</a>',
            'TLORA': '<a href="https://meshtastic.org/docs/hardware/devices/lora/">TLORA</a>',
            'T_ECHO': '<a href="https://meshtastic.org/docs/hardware/devices/techo">T-ECHO</a>',
            'DIY': '<a href="https://meshtastic.discourse.group/t/meshtastic-diy-project/3831/1">DIY</a>',
        }
        return hw_map.get(hw_model, hw_model)

    def dispatch_request(self) -> flask.Response:  # pylint:disable=too-many-locals
        """
        Process Flask request

        :return:
        """
        # Get tail value
        name, tail_value = self.get_tail(self.config, self.logger)
        nodes = []
        # node default color
        default_color = "red"
        for node_info in self.meshtastic_connection.nodes_with_user:
            user_info = node_info.get('user', {})
            node_id = user_info.get('id')
            device_metrics = node_info.get('deviceMetrics', {})
            position = node_info.get('position', {})
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            if not latitude or not longitude:
                try:
                    latitude, longitude = self.database.get_last_coordinates(node_id)
                except RuntimeError:
                    continue
            hw_model = user_info.get('hwModel', 'unknown')
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
            if len(name) > 0 and user_info.get('longName') != name:
                continue
            # Channel and Air utilization
            ch_util = int(device_metrics.get('channelUtilization', 0))
            air_util = int(device_metrics.get('airUtilTx', 0))
            #
            color = default_color
            if self.meshtastic_connection.node_has_mqtt(node_id):
                if self.meshtastic_connection.node_mqtt_status(node_id) == 'online':
                    color = 'green'
                else:
                    color = 'blue'
            nodes.append([user_info.get('longName'), str(round(latitude, 5)),
                          str(round(longitude, 5)), self.format_hw(hw_model), snr,
                          last_heard_dt.strftime("%d/%m/%Y, %H:%M:%S"),
                          battery_level,
                          altitude,
                          ch_util,
                          air_util,
                          color,
                          self.meshtastic_connection.node_mqtt_status(node_id)
                          ])
        return jsonify(nodes)


class RenderAirRaidView(CommonView):  # pylint:disable=too-many-instance-attributes
    """
    Air Raid Alert renderer
    """

    # pylint:disable=too-many-arguments
    def __init__(self, database: MeshtasticDB, config: Config,
                 meshtastic_connection: RichConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger,
                 memcache: Memcache):
        self.database = database
        self.config = config
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.logger = logger
        self.memcache = memcache
        self.region_table = {3: 'Khmelnystjka', 4: 'Vinnytsjka', 5: 'Rivnenska',
                             8: 'Volynska', 9: 'Dnipro', 10: 'Zhytomyrska',
                             11: 'Zakarpattya', 12: 'Zaporizhzhja', 13: 'Ivano-Fr',
                             14: 'Kyiv obl', 15: 'Kirovohrad', 16: 'Luhansk',
                             17: 'Mykolaiv', 18: 'Odesa', 19: 'Poltava',
                             20: 'Sumy', 21: 'Ternopil', 22: 'Kharkiv',
                             23: 'Kherson', 24: 'Cherkasy', 25: 'Chernihiv',
                             26: 'Chernivtsi', 27: 'Lviv', 28: 'Donetsjk',
                             31: 'Kyiv', 9999: 'Krym'}
        self.translation_table = {'Dnipropetrovsk': 'Dnipro',
                                  'Kiev': 'Kyiv obl', 'Kyiv City': 'Kyiv',
                                  'Odessa': 'Odesa'}

    def dispatch_request(self) -> AnyStr:  # pylint:disable=too-many-locals
        """
        Process Flask request

        :return:
        """
        msg = request.get_json()
        alert_type = msg.get('alarmType')
        region_id = msg.get('regionId', 0)
        alert_place = self.region_table.get(region_id)
        alert_status = msg.get('status').lower().capitalize()
        alert_tz = msg.get('createdAt')
        dt_f = datetime.strptime(alert_tz, '%Y-%m-%dT%H:%M:%SZ')
        tzinfo = datetime.now().astimezone().tzinfo
        dt_f = dt_f + tzinfo.utcoffset(None)
        alert_time = dt_f.strftime("%H:%M:%S")
        self.logger.info(f"{msg}: {alert_place}")
        new_msg = f'Alert: {alert_type}, {alert_place}, {alert_status} since {alert_time}'
        if not self.config.enforce_type(bool, self.config.WebApp.AirRaidEnabled):
            return 'Ok'
        if self.memcache.get(new_msg):
            return 'Ok'
        # set
        self.memcache.set(new_msg, True, expires=60)
        # Telegram - Kyiv/obl only
        if region_id in [14, 31]:
            chat_id = self.config.enforce_type(int, self.config.Telegram.NotificationsRoom)
            self.telegram_connection.send_message(chat_id=chat_id,
                                                  text=new_msg)
        for node in self.meshtastic_connection.nodes_with_position:
            user = node.get('user', {})
            node_id = user.get('id')
            name = user.get('longName')
            position = node.get('position', {}).get('admin1')
            if not position:
                continue
            #
            translated = self.translation_table.get(position, position)
            self.logger.info(f"{node_id},{name},{position} {alert_place}")
            if translated == alert_place:
                self.logger.info(f"Sending alert to {node_id}....")
                self.meshtastic_connection.send_text(new_msg, destinationId=node_id)
        return 'Ok'


class WebApp:  # pylint:disable=too-few-public-methods
    """
    WebApp: web application container
    """

    # pylint:disable=too-many-arguments
    def __init__(self, database: MeshtasticDB, app: Flask, config: Config,
                 meshtastic_connection: RichConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger,
                 memcache: Memcache):
        self.database = database
        self.app = app
        self.config = config
        self.logger = logger
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.memcache = memcache

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

        self.app.add_url_rule('/track.json', view_func=RenderTrackView.as_view(
            'track_page',
            database=self.database,
            config=self.config,
            meshtastic_connection=self.meshtastic_connection, logger=self.logger))

        # This should be moved out to separate directory
        self.app.add_url_rule(
            f'/airraid/{self.config.enforce_type(str, self.config.WebApp.AirRaidPrivate)}',
            view_func=RenderAirRaidView.as_view(
                'airraid_page',
                database=self.database,
                config=self.config,
                meshtastic_connection=self.meshtastic_connection,
                telegram_connection=self.telegram_connection,
                logger=self.logger,
                memcache=self.memcache,
            ),
            methods=['POST'],
        )
        self.app.add_url_rule(
            f'/airraid/{self.config.enforce_type(str, self.config.WebApp.AirRaidPrivate)}/',
            view_func=RenderAirRaidView.as_view(
                'airraid_page_with_slash',
                database=self.database,
                config=self.config,
                meshtastic_connection=self.meshtastic_connection,
                telegram_connection=self.telegram_connection,
                logger=self.logger,
                memcache=self.memcache,
            ),
            methods=['POST'],
        )
        # Favicon
        self.app.add_url_rule('/favicon.ico', view_func=RenderFavicon.as_view('favicon'))
        # Index pages
        self.app.add_url_rule('/', view_func=RenderTemplateView.as_view(
            'root_page', template_name='index.html', config=self.config))
        self.app.add_url_rule('/index.htm', view_func=RenderTemplateView.as_view(
            'index_page', template_name='index.html', config=self.config))
        self.app.add_url_rule('/index.html', view_func=RenderTemplateView.as_view(
            'index_html_page', template_name='index.html', config=self.config))


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
        self.name = 'WebApp Server'

    def run(self) -> None:
        """

        :return:
        """
        setthreadtitle(self.name)
        self.logger.debug('starting server')
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
                 meshtastic_connection: RichConnection,
                 telegram_connection: TelegramConnection,
                 logger: logging.Logger,
                 static_folder: str,
                 template_folder: str):
        self.database = database
        self.meshtastic_connection = meshtastic_connection
        self.telegram_connection = telegram_connection
        self.config = config
        self.logger = logger
        self.app = Flask(__name__, static_folder=static_folder, template_folder=template_folder)
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        self.server = None

    def run(self) -> None:
        """
        Run web server

        :return:
        """
        if self.config.enforce_type(bool, self.config.WebApp.Enabled):
            memcache = Memcache(self.logger)
            memcache.run_noblock()
            web_app = WebApp(self.database, self.app, self.config,
                             self.meshtastic_connection,
                             self.telegram_connection,
                             self.logger,
                             memcache)
            web_app.register()
            self.server = ServerThread(self.app, self.config, self.logger)
            self.server.start()

    def shutdown(self) -> None:
        """
        Web server shutdown method

        :return:
        """
        if self.server is not None:
            self.server.shutdown()
