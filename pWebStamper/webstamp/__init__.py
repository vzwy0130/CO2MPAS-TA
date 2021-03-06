# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2014-2018 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
## From Flask-Bootstrap sample application. This will give you a
#  guided tour around creating an application using Flask-Bootstrap.
#
#  1. To run this application yourself, please install its requirements first:
#
#      $ pip install -r sample_app/requirements.txt
#
#  2. Copy and adapt `default_config.py --> local_config.py` in this package
#     (or in some other path).
#
#  3. Launch the a SINGLE instance of the application (for stamp-chain to work)
#     using `flask >=1.x.x` cli::
#
#         $export WEBSTAMP_CONFIG=local_config.py
#         $export FLASK_ENV=development
#         $export FLASK_APP=webstamp
#         $flask run
#
#     (optionally use an absolute path for `WEBSTAMP_CONFIG` envvar)
#
#  Afterwards, point your browser to http://localhost:5000, then check out the
#  source.

from co2mpas.__main__ import init_logging
import logging
import os
from polyversion import polyversion, polytime
import sys

from flask import Flask, request
from flask_bootstrap import Bootstrap
from raven.contrib.flask import Sentry

import os.path as osp
import subprocess as sbp


__version__ = polyversion(pname='webstamper')
__updated__ = polytime(pname='webstamper')


## NOTE: `configfile` DEPRECATED by `flask-appconfig` in latest dev.
#  Use `<APPNAME>_CONFIG` envvar instead.
#  See https://github.com/mbr/flask-appconfig/blob/master/flask_appconfig/__init__.py#L35
#
def create_app(configfile=None, logconf_file=None):
    from .frontend import frontend

    # We are using the "Application Factory"-pattern here, which is described
    # in detail inside the Flask docs:
    # http://flask.pocoo.org/docs/patterns/appfactories/

    ## log-configuration must come before Flask-config.
    #
    os.environ.get('%s_LOGCONF_FILE' % __name__)
    init_logging(logconf_file=logconf_file,
                 not_using_numpy=True)

    app = Flask(__name__)#, instance_relative_config=True)

    app.config.from_object('webstamp.default_config')
    app.config.from_envvar('WEBSTAMP_CONFIG')

    app.config['POLYVERSION'] = __version__
    app.config['POLYTIME'] = __updated__

    ## Automatically discover DSN key:
    #  https://docs.sentry.io/clients/python/integrations/flask/#setup
    #
    if 'SENTRY_DSN' in app.config:
        sentry = Sentry()
        sentry_log_level = app.config.get('SENTRY_LOG_LEVEL')
        sentry.init_app(app,
                        logging=bool(sentry_log_level),
                        level=sentry_log_level)

    # Install our Bootstrap extension
    Bootstrap(app)

    # Our application uses blueprints as well; these go well with the
    # application factory. We already imported the blueprint, now we just need
    # to register it:
    app.register_blueprint(frontend)

    # Because we're security-conscious developers, we also hard-code disabling
    # the CDN support (this might become a default in later versions):
    #app.config['BOOTSTRAP_SERVE_LOCAL'] = True

    return app


## From http://flask.pocoo.org/docs/dev/logging/#injecting-request-information
#
#  .. Warning::
#      Assign it to a logger used only from within a Request.
#
class RequestFormatter(logging.Formatter):
    def format(self, record):
        ## Form more request-data, see:
        #  http://flask.pocoo.org/docs/0.12/api/#incoming-request-data
        record.url = request.url
        record.remote_addr = request.remote_addr
        record.headers = request.headers
        record.cookies = request.cookies
        return super().format(record)


## From latest flask-0.12.2+:
#  https://github.com/pallets/flask/blob/master/flask/logging.py#L12
#
def wsgi_errors_stream():
    return request.environ['wsgi.errors'] if request else sys.stderr


def get_bool_arg(argname, default=None):
    """
    True is an arg alone, or any stripped string not one of: ``0|false|no|off``
    """
    args = request.args
    if argname in args:
        param = args[argname].strip()
        return param.lower() not in '0 false no off'.split()
    return default


if __name__ == '__main__':
    if __package__ is None:
        __package__ = 'webstamp'  # @ReservedAssignment
    from flask_appconfig import cli

    ## Set WEBSTAMP_CONFIG=local_config.py
    cmd = '--app=webstamp dev'.split()
    #cli.cli(ctx, app_name, configfile, env, amend_path)
    cli.cli(cmd)
