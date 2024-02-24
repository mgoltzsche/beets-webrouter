import codecs
import mediafile
import os
import re
import importlib
from flask import Flask, send_file, abort
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs
from beets import config
from optparse import OptionParser
from confuse import ConfigSource, load_yaml
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from beetsplug.web import ReverseProxied
from flask import Blueprint


class WebRouterPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()
        config_file_path = os.path.join(os.path.dirname(__file__), 'config_default.yaml')
        source = ConfigSource(load_yaml(config_file_path) or {}, config_file_path)
        self.config.add(source)

    def commands(self):
        p = OptionParser()
        p.add_option('-d', '--debug', action='store_true', default=False, help='debug mode')
        c = Subcommand('webrouter', parser=p, help='serve the web UI, Subsonic API and playlists')
        c.func = self._run_cmd
        return [c]

    def _run_cmd(self, lib, opts, args):
        app = Flask(__name__)
        routes = {}
        blueprint_routes = []

        for k,v in self.config['routes'].items():
            plugin = v['plugin'].get()
            if plugin:
                mod = importlib.import_module('beetsplug.{}'.format(plugin))
                if 'blueprint' in v and v['blueprint'].get():
                    blueprint_routes.append({
                        'prefix': k,
                        'blueprint': getattr(mod, v['blueprint'].get()),
                    })
                else:
                    if hasattr(mod, 'create_app'):
                        modapp = mod.create_app()
                    else:
                        modapp = mod.app
                    self._configure_app(modapp, v['config'].items(), lib)
                    if k == '/':
                        app = modapp
                    else:
                        routes[k] = modapp

        for e in blueprint_routes:
            app.register_blueprint(e['blueprint'], url_prefix=e['prefix'])

        icon = self.config['favicon'].get()
        if icon:
            @app.route('/favicon.ico')
            def favicon():
                return send_file(icon, mimetype='image/x-icon')

        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, routes)

        app.run(
            host=self.config['host'].as_str(),
            port=self.config['port'].get(int),
            debug=opts.debug,
            threaded=True,
        )

    def _configure_app(self, app, cfg, lib):
        app.config['lib'] = lib
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
        app.config['INCLUDE_PATHS'] = self.config['include_paths']
        app.config['READONLY'] = self.config["readonly"]

        if self.config['cors']:
            self._log.info('Enabling CORS with origin {}', self.config['cors'])
            from flask_cors import CORS

            app.config['CORS_ALLOW_HEADERS'] = 'Content-Type'
            app.config['CORS_RESOURCES'] = {
                r'/*': {'origins': self.config['cors'].get(str)}
            }
            CORS(
                app,
                supports_credentials=self.config['cors_supports_credentials'].get(bool),
            )

        for k,v in cfg:
            app.config[k] = v.get()

        if self.config['reverse_proxy']:
            app.wsgi_app = ReverseProxied(app.wsgi_app)
