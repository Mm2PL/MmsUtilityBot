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
import contextlib
import html
import importlib.util
import inspect
import sys
import textwrap
import time
from typing import Dict, Any, Callable, Union, List
import os
import typing

import regex
from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

try:
    from web import ipc
except ImportError:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    import ipc

if 'DBADDR' in os.environ:
    base_address = os.environ['DBADDR']
else:
    raise RuntimeError('Set the DBADDR envirionment variable to the base address.\n'
                       'mysql+pymysql://USERNAME:PASSWORD@HOST/DBNAME')
Base = declarative_base()
db_engine = create_engine(base_address)
Session = sessionmaker(bind=db_engine)
PAGE_SIZE = 50
app = Flask(__name__)
api_endpoints: Dict[str, Callable[[], Union[str, Any]]] = {}
api_docs: Dict[str, str] = {}
aliases = {}
LINK_PREFIX = '/api'


def load_model(name: str):
    path = os.path.join('..', 'plugins', 'models', name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    session.expire_on_commit = False
    try:
        yield session
        session.commit()
    except:
        print('LS: Roll back.')
        session.rollback()
        raise
    finally:
        print('LS: Expunge all and close')
        session.expunge_all()
        session.close()


RETURNS_PATTERN = regex.compile(':returns?:(.*)')
PARAM_PATTERN = regex.compile(':param (.*):(.*)')


def _render_docs(data: Dict[str, Union[Union[List[Any], None, Dict[Any, Any]], Any]]) -> str:
    output = ''
    function_argspec = None
    if data['func']:
        func: typing.Callable = data["func"]
        function_argspec = inspect.getfullargspec(func)
        if data['path']:
            link = f'<a href="{LINK_PREFIX}{data["path"]}">'
        else:
            link = ''
        output += (
            f'<h2>{link}{func.__name__}({"..." if function_argspec.args else ""}){"</a>" if data["path"] else ""}'
            f'</h2>\n'
        )
        if link:
            output += f'<h3>Path: {link}{LINK_PREFIX}{html.escape(data["path"])}</a></h3>'
    is_raw = False
    for line in data['text']:
        line: str
        if line.strip().startswith('.. start-raw'):
            line = line.replace('.. start-raw', '')
            is_raw = True
        if line.strip().startswith('.. stop-raw'):
            line = line.replace('.. stop-raw', '')
            is_raw = False
        if len(line.strip()) == 0:
            continue
        if not is_raw:
            line = html.escape(line) + "<br>\n"
        output += line

    if data['params']:
        output += '<h3>Params</h3>\n' \
                  '<ol>\n'
        for param_name, docs in data['params'].items():
            param_name: str
            print(param_name, docs)
            docs: str
            param_type = None
            if function_argspec and param_name in function_argspec.annotations:
                param_type = repr(function_argspec.annotations[param_name])
            output += textwrap.dedent(
                f"""
                <li>\n
                    <b>{param_name}{f": {param_type}" if param_type is not None else ""}</b>\n
                    <cite>\n
                        {docs}\n
                    </cite>\n
                </li>\n
                """)
        output += '</ol>'
    if data['returns']:
        output += (f'<h3>Returns</h3>\n'
                   f'{html.escape(data["returns"])}')
    return output


def _parse_docs(doc, func: typing.Optional[typing.Callable] = None, path: typing.Optional[str] = None) -> str:
    data: Dict[str, Union[Union[List[Any], None, Dict[Any, Any]], Any]] = {
        'text': [],
        'returns': None,
        'params': {

        },
        'func': func,
        'path': path
    }
    for line in doc.split('\n'):
        line: str = line.lstrip()
        m = RETURNS_PATTERN.match(line)
        if m:
            data['returns'] = m[1]
            continue

        m = PARAM_PATTERN.match(line)
        if m:
            data['params'][m[1]] = m[2]
            continue

        # doesn't match any pattern
        data['text'].append(line)
    return _render_docs(data)


def register_endpoint(*paths):
    global aliases
    aliases[paths[0]] = paths[1:]

    def _decorator(func):
        for path in paths:
            app.route(path)(func)
        api_endpoints[paths[0]] = func
        api_docs[paths[0]] = _parse_docs(func.__doc__, func, paths[0])
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
        f'{v}' for k, v in api_docs.items()
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
                    'arguments': _parse_args(k),
                    'html_doc': api_docs[k]
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

try:
    import plugins.models.user as user_model
except ImportError:
    user_model = load_model('user')

User, flush_users = user_model.get(Base, session_scope, print)
this_module = sys.modules[__name__]
for i in [suggestions]:
    i.init(register_endpoint, ipc_conn, this_module)
if __name__ == '__main__':
    app.run(debug=True, port=8000)
