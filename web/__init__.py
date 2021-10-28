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
import base64
import contextlib
import html
import importlib.util
import inspect
import json
import sys
import textwrap
import time
import traceback
from typing import Dict, Any, Callable, Union, List
import os
import typing

import regex
import requests
from flask import Flask, jsonify, abort, redirect, request, Response, session, flash

import util_bot
from web import ipc

if 'DBADDR' in os.environ:
    base_address = os.environ['DBADDR']
else:
    raise RuntimeError('Set the DBADDR envirionment variable to the base address.\n'
                       'mysql+pymysql://USERNAME:PASSWORD@HOST/DBNAME')


def load_secrets():
    global secrets
    with open('web_secrets.json', 'r') as f:
        secrets = json.load(f)
    return secrets


def save_secrets():
    with open('web_secrets.json', 'w') as f:
        json.dump(secrets, f)


util_bot.init_sqlalchemy(base_address)
Base = util_bot.Base
Session = util_bot.Session

PAGE_SIZE = 50
app = Flask(__name__)
api_endpoints: Dict[str, Callable[[], Union[str, Any]]] = {}
api_docs: Dict[str, str] = {}
aliases = {}
LINK_PREFIX = '/api'


def load_model(name: str):
    path = os.path.join('plugins', 'models', name + '.py')
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
        def _decorated_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                if app.debug:
                    raise
                traceback.print_exc()
                resp: app.response_class = jsonify({
                    'status': 500,
                    'message': f'Internal server error occurred, something 🅱roke',
                })
                resp.status_code = 500
                abort(resp)

        _decorated_func.__name__ = func.__name__  # 4HEad
        for path in paths:
            app.route(path)(_decorated_func)
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


def allow_return_to(func):
    def new_func(*args, **kwargs):
        ret_val = func(*args, **kwargs)
        return_to = request.args.get('return_to')
        print(return_to)
        if return_to:
            return_to = return_to.replace('https://', '/').replace('http://', '/')
            return redirect(return_to, code=302)
        else:
            return ret_val

    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    return new_func


@register_endpoint('/twitch_login')
def twitch_login_redirect():
    """Redirects to the login url for Twitch"""
    state = base64.b64encode(json.dumps({
        'redirect_to': request.args.get('return_to', None)
    }).encode())
    return redirect(f'https://id.twitch.tv/oauth2/authorize'
                    f'?client_id={secrets["app_id_twitch"]}'
                    f'&redirect_uri={secrets["app_redirect_twitch"]}'
                    f'&response_type=code'
                    f'&scope='
                    f'&state={state.decode()}')


def refresh_oauth_token(refresh_token):
    with requests.request('post', 'https://id.twitch.tv/oauth2/token', params={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': secrets['app_id_twitch'],
        'client_secret': secrets['app_secret_twitch'],
    }) as r:
        if r.status_code != 400:
            return {

            }
        new_data = r.json()
        return {
            'access_token': new_data['access_token'],
            'refresh_token': new_data['refresh_token']
        }


def validate_oauth_token(access_token: str, refresh_token: str,
                         try_refresh: bool = False) -> typing.Optional[dict]:
    with requests.request('get', 'https://id.twitch.tv/oauth2/validate', headers={
        'Authorization': f'OAuth {access_token}'
    }) as r:
        if r.status_code == 400:
            if try_refresh:
                new_data = refresh_oauth_token(refresh_token)
                access_token = new_data['access_token']
                refresh_token = new_data['refresh_token']
                return validate_oauth_token(access_token, refresh_token)
        data = r.json()
        data['access_token'] = access_token
        data['refresh_token'] = refresh_token
        return data


@register_endpoint('/twitch_logged_in')
def twitch_logged_in():
    """Users will get redirected here if the Twitch auth was successful."""
    code = request.args.get('code', None)
    print(request.args)
    if code is None:
        print('bad code')
        abort(Response(json.dumps(
            {
                'status': 400,
                'error': 'Missing code argument.'
            }
        ), status=400, mimetype='application/json'))
        # abort doesn't return

    with requests.request('post', 'https://id.twitch.tv/oauth2/token', params={
        'client_id': secrets['app_id_twitch'],
        'client_secret': secrets['app_secret_twitch'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': secrets['app_redirect_twitch']
    }) as r:
        j_data = r.json()
        print(j_data)
        if r.status_code == 400:
            abort(Response(json.dumps(
                {
                    'status': 400,
                    'error': 'Something went wrong, try again'
                }
            ), status=400, content_type='application/json'))

        access_token = j_data['access_token']
        refresh_token = j_data['refresh_token']

        session['access_token'] = access_token
        session['refresh_token'] = refresh_token
    print('pre validate')
    token_data = validate_oauth_token(access_token, refresh_token, try_refresh=False)
    print('post validate')
    session['login'] = token_data['login']
    session['user_id'] = token_data['user_id']

    state = request.args.get('state')
    redirect_to = None
    if state:
        try:
            j_value = json.loads(base64.b64decode(state.encode()).decode())
        except json.JSONDecodeError:
            abort(Response(json.dumps(
                {
                    'status': 400,
                    'error': 'Bad state.'
                }
            ), status=400, mimetype='application/json'))
        if 'redirect_to' in j_value:
            redirect_to = j_value['redirect_to']
    if redirect_to:
        flash('Authenticated successfully.')
        return redirect(redirect_to)
    return jsonify({
        'status': 200,
        'message': 'Authenticated successfully.'
    })


@register_endpoint('/logout')
@allow_return_to
def logout():
    """Logout"""
    for i in ('login', 'user_id', 'access_token', 'refresh_token'):
        if i in session:
            del session[i]
    return jsonify({
        'status': 200,
        'message': 'Logged out successfully.'
    })


@register_endpoint('/whoami')
def whoami():
    """Returns who you are authenticated as."""
    return jsonify({
        'login': session.get('login', None),
        'user_id': session.get('user_id', None)
    })


try:
    load_secrets()
except FileNotFoundError:
    secrets = {}
    # will be saved after creating a secret

if 'flask_secret' not in secrets:
    secrets['flask_secret'] = base64.b64encode(os.urandom(30)).decode()
    save_secrets()

app.secret_key = base64.b64decode(secrets['flask_secret'])

if 'app_id_twitch' not in secrets:
    raise RuntimeError('Missing `app_id_twitch` key in web_secrets.json. Create an app using the Twitch developers '
                       'website. Place the secret as `app_secret_twitch`.')

if 'app_secret_twitch' not in secrets:
    raise RuntimeError('Missing `app_secret_twitch` key in web_secrets.json')

ipc_conn = ipc.Connection('ipc_server')
ipc_conn.max_recv = 32_768  # should capture even the biggest json message.
time.sleep(0.5)  # wait for the welcome burst to come in fully.
ipc_conn.receive()  # receive the welcome burst

# initialize modules
User, flush_users = util_bot.User, util_bot.flush_users
from web import suggestions, channel_settings, channels, mailgame

this_module = sys.modules[__name__]
for i in [suggestions, channel_settings, channels, mailgame]:
    i.init(register_endpoint, ipc_conn, this_module, session_scope)
