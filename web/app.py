#  This is a simple utility bot
#  Copyright (C) 2019 Maciej Marciniak
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
import json
from typing import Dict, Any, Callable, Union

import flask
from flask import Flask

try:
    from web import ipc
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    import ipc

app = Flask(__name__)
api_endpoints: Dict[str, Callable[[], Union[str, Any]]] = {}
LINK_PREFIX = '/api'


def register_endpoint(path):
    def _decorator(func):
        api_endpoints[path] = func
        app.route(path)(func)
        return func

    return _decorator


@register_endpoint('/')
def index():
    """Return all available endpoints"""
    return '\n'.join(
        [
            '<h1>Hello and welcome to the API</h1>',
            '<ol>'
        ]
        + [
            (
                f'<li>'
                f'  <a href={LINK_PREFIX}{k}>{k} ({v.__name__})</a><br/>'
                f'  <code>'
                f'  {v.__doc__}'
                f'  </code>'
                f'</li>'
            ) for k, v in api_endpoints.items()
        ]
        + ['</ol>'])


@register_endpoint('/index')
def index_json():
    """Return all available endpoints in a JSON format."""
    return {
        'status': 200,
        'data':
            [
                {
                    'name': v.__name__,
                    'url': k,
                    'doc': v.__doc__
                }
                for k, v in api_endpoints.items()
            ]
    }


@register_endpoint('/test')
def test():
    """Test if the API is online."""
    return 'KKaper Test successful KKaper'


ipc_conn = ipc.Connection('../ipc_server')
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
    app.run(debug=True)
