#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import time
from typing import Dict, Any, Callable, Union
import html

import regex
from flask import Flask, jsonify

try:
    from web import ipc
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    import ipc

app = Flask(__name__)
api_endpoints: Dict[str, Callable[[], Union[str, Any]]] = {}
aliases = {}
LINK_PREFIX = '/api'


def register_endpoint(*paths):
    global aliases
    aliases[paths[0]] = paths[1:]

    def _decorator(func):
        for path in paths:
            app.route(path)(func)
        api_endpoints[paths[0]] = func
        return func

    return _decorator


@app.after_request
def after_request(response):
    # Taken from https://stackoverflow.com/a/45438226
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


USER_READABLE_INDEX_FORMAT = '''
<!doctype html>
<html>
<head>
    <link href="/global.css" rel="stylesheet">
</head>
<body>
<h1>Hello and welcome to the DentAPI</h1>
<ol>
  {}
</ol>
</body>
</html>
'''


@register_endpoint('/')
def index():
    """Return all available endpoints"""
    endpoints = [
        (
                f'<li>\n'
                f'  <a href={LINK_PREFIX}{html.escape(k)}>{html.escape(k)} ({v.__name__})</a><br/>\n'
                f'  <code>\n'
                f'  {v.__doc__}\n'
                f'\n'
                + ('<b>Warning</b>: Arguments required. Clicking this long won\'t work.\n' if '<' in k else '')
                + f'  </code>\n'
                  f'</li>\n'
        ) for k, v in api_endpoints.items()
    ]
    return USER_READABLE_INDEX_FORMAT.format(''.join(endpoints))


ARG_PATTERN = regex.compile(r'\<(string|int|float|path|uuid):([a-zA-Z_-]+)\>')


def _parse_args(k):
    return ARG_PATTERN.findall(k)


@register_endpoint('/index')
def index_json():
    """Return all available endpoints in a JSON format."""
    return jsonify({
        'status': 200,
        'data':
            [
                {
                    'name': v.__name__,
                    'url': k,
                    'doc': v.__doc__,
                    'arguments': _parse_args(k)
                }
                for k, v in api_endpoints.items()
            ]
    })


@register_endpoint('/test')
def test():
    """Test if the API is online."""
    return 'KKaper Test successful KKaper'


ipc_conn = ipc.Connection('../ipc_server')
ipc_conn.max_recv = 32_768  # should capture even the biggest json message.
time.sleep(0.5)  # wait for the welcome burst to come in fully.
ipc_conn.receive()  # receive the welcome burst

# initialize modules
try:
    from web import suggestions
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    import suggestions

for i in [suggestions]:
    i.init(register_endpoint, ipc_conn)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
