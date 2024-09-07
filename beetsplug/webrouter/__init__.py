import codecs
import mediafile
import os
import re
import importlib
from contextlib import AsyncExitStack, asynccontextmanager
from flask import Flask
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs
from beets import config
from optparse import OptionParser
from confuse import ConfigSource, load_yaml
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from beetsplug.web import ReverseProxied
from flask import Blueprint
from fastapi import FastAPI
from starlette.routing import Mount
from fastapi.middleware.wsgi import WSGIMiddleware


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
        app = FastAPI(
            title=__name__,
            description="Serves multiple Beets webapps",
            version="1.0.0",
        )
        flask_app = None

        routes = {}
        flask_routes = {}
        blueprint_routes = []

        for k,v in self.config['routes'].items():
            plugin = v['plugin'].get()
            if plugin:
                mod = importlib.import_module(f'beetsplug.{plugin}')
                has_create_app = hasattr(mod, 'create_app')
                has_app = hasattr(mod, 'app')
                if 'blueprint' in v and v['blueprint'].get():
                    blueprint_routes.append(BlueprintRoute(k,
                        getattr(mod, v['blueprint'].get())))
                elif has_app or has_create_app:
                    if has_create_app:
                        modapp = mod.create_app()
                    else:
                        modapp = mod.app

                    if isinstance(modapp, FastAPI):
                        self._configure_fastapi_app(modapp, v['config'].items(), lib)
                    else:
                        self._configure_flask_app(modapp, v['config'].items(), lib)

                    if k == '/':
                        if isinstance(modapp, FastAPI):
                            app = modapp
                        else:
                            flask_app = modapp
                    else:
                        if isinstance(modapp, FastAPI):
                            routes[k] = modapp
                        else:
                            flask_routes[k] = modapp
                elif hasattr(mod, 'bp'):
                    blueprint_routes.append(BlueprintRoute(k, getattr(mod, 'bp')))
                else:
                    raise Exception(f"webrouter: cannot register route to plugin '{plugin}' since it neither specifies a 'create_app' function, a Flask app 'app' nor a Blueprint 'bp' nor is a Blueprint name configured!")

        @app.on_event("startup")
        async def initialize():
            async with AsyncExitStack() as stack:
                for route in app.routes:
                    if isinstance(route, Mount) and isinstance(route.app, FastAPI):
                        # Initialize app
                        await stack.enter_async_context(
                            route.app.router.lifespan_context(route.app), # noqa
                        )

        for k,v in routes.items():
            app.mount(k, v)

        if (blueprint_routes or flask_routes) and not flask_app:
            flask_app = Flask(__name__)

        for r in blueprint_routes:
            flask_app.register_blueprint(r.blueprint, url_prefix=r.url_prefix)

        if flask_app:
            flask_app.wsgi_app = DispatcherMiddleware(flask_app.wsgi_app, flask_routes)
            app.mount("/", WSGIMiddleware(flask_app))

        import uvicorn

        uvicorn.run(app,
            host=self.config['host'].as_str(),
            port=self.config['port'].get(int),
            log_level=opts.debug and 'debug' or 'info',
        )

    def _configure_fastapi_app(self, app, cfg, lib):
        for k,v in cfg:
            app.state[k] = v.get()

        app.state.lib = lib

        # TODO: support cors and running behind a reverse-proxy

    def _configure_flask_app(self, app, cfg, lib):
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

        if self.config['reverse_proxy'] or os.getenv('BEETS_WEBROUTER_REVERSE_PROXY') == 'true':
            app.wsgi_app = ReverseProxied(app.wsgi_app)

class BlueprintRoute:
    def __init__(self, url_prefix, blueprint):
        self.url_prefix = url_prefix
        self.blueprint = blueprint
