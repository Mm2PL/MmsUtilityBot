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
import textwrap
import time
import typing

import requests

with open('twitch_api.json', 'r') as f:
    json_data: dict = json.load(f)
    orig_data: dict = json_data.copy()


def refresh():
    rr = requests.post('https://id.twitch.tv/oauth2/token', params={
        'grant_type': 'refresh_token',
        'refresh_token': json_data['refresh_token'],
        'client_id': json_data['client_id'],
        'client_secret': json_data['client_secret']
    })
    json_data.update(rr.json())


def new_access_token(scopes: typing.List[str]):
    json_data[f'copy_{time.time()}'] = json_data.copy()
    # json_data.save()
    return (f'https://id.twitch.tv/oauth2/authorize?client_id={json_data["client_id"]}&redirect_uri=http://localhost'
            f'&response_type=code&scope={"%20".join(scopes)}')


def new_access_token_part_2(code):
    # https://id.twitch.tv/oauth2/token
    #     ?client_id=<your client ID>
    #     &client_secret=<your client secret>
    #     &code=<authorization code received above>
    #     &grant_type=authorization_code
    #     &redirect_uri=<your registered redirect URI>
    rr = requests.post('https://id.twitch.tv/oauth2/token', params={
        'client_id': json_data['client_id'],
        'client_secret': json_data['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'http://localhost'
    })
    json_data.update(rr.json())


def save():
    if json_data != orig_data:
        with open('twitch_api.json', 'w') as f:
            json.dump(json_data, f, sort_keys=True, indent=4)


class Auth:
    def __init__(self):
        with open('twitch_api.json', 'r') as f:
            self.data = json.load(f)

    @property
    def client_id(self):
        return self.data['client_id']

    @property
    def client_secret(self):
        return self.data['client_secret']

    @property
    def token(self):
        return self.data['access_token']


class API:
    def __init__(self, auth):
        self.auth = auth
        self.main_url = 'http://localhost'
        self.headers = {
            'Authorization': f'Bearer {self.auth.token}'
        }
        self.end_points = {
            'end_point_name': {
                'path': 'path/to/end_point',
                'args': [
                    'a',
                    '[b]'
                ],
                'request_type': 'get'
            }
        }

    def generate_functions(self):
        for name, data in self.end_points.items():
            args = []
            args2 = []
            print(name, data)
            for arg in data['args']:
                if arg.startswith('[') and arg.endswith(']'):
                    args.append(arg[1:-1] + '=None')
                    args2.append(f'{arg[1:-1]}={arg[1:-1]}')
                else:
                    args.append(arg)
                    args2.append(f'{arg}={arg}')
            code = textwrap.dedent(f'''
            def func({", ".join(args)}, **kwargs):
                return self._do_end_point({name!r}, {", ".join(args2)}, **kwargs)
            ''')
            variables = {
                'self': self
            }
            exec(code, variables, variables)
            setattr(self, name, variables['func'])

    def _do_end_point(self, end_point_name, **kwargs):
        if 'arg_type' not in self.end_points[end_point_name] or self.end_points[end_point_name]['arg_type'] == 'format':
            return self.request(self.end_points[end_point_name]['path'].format(**kwargs),
                                request_type=self.end_points[end_point_name]['request_type'])
        elif self.end_points[end_point_name]['arg_type'] == 'parameter':
            return self.request(self.end_points[end_point_name]['path'],
                                request_type=self.end_points[end_point_name]['request_type'],
                                **kwargs)

    def request(self, end_point, *, request_type='get', wait_for_result=False, **kwargs):
        """
        Request something from the API.

        :param end_point: Path to the end point
        :param request_type: Request type, can be 'get', 'post', 'put', 'delete' or 'head'
        :param wait_for_result: Wait for the result to come back. If this is True the deserialized data and the
        status code
        :param kwargs: Parameters to give to the request.
        :return:
        """
        if request_type == 'get':
            r = requests.get(self.main_url + end_point, headers=self.headers, params=kwargs)
        elif request_type == 'post':
            r = requests.post(self.main_url + end_point, headers=self.headers, params=kwargs)
        elif request_type == 'put':
            r = requests.put(self.main_url + end_point, headers=self.headers, params=kwargs)
        elif request_type == 'delete':
            r = requests.delete(self.main_url + end_point, headers=self.headers, params=kwargs)
        elif request_type == 'head':
            r = requests.head(self.main_url + end_point, headers=self.headers, params=kwargs)
        else:
            raise RuntimeError(f'Invalid request type {request_type!r}')
        if wait_for_result:
            return r.json(), r.status_code
        else:
            return r, -1


class TwitchNewAPI(API):
    def __init__(self, auth):
        super().__init__(auth)
        self.main_url = 'https://api.twitch.tv/helix/'
        self.headers = {
            'Authorization': f'Bearer {self.auth.token}',
            'Client-ID': self.auth.client_id
        }
        self.end_points = {
            'create_clip': {
                'path': 'clips',
                'args': [
                    'broadcaster_id',
                    '[has_delay]'
                ],
                'request_type': 'post',
                'arg_type': 'parameter'
            },
            'get_clips': {
                'arg_type': 'parameter',
                'path': 'clips',
                'args': [
                    '[broadcaster_id]',
                    '[game_id]',
                    '[id]',

                    '[after]',
                    '[before]',
                    '[ended_at]',
                    '[first]',
                    '[started_at]'
                ],
                'request_type': 'get'
            },
            'get_code_status': {
                'arg_type': 'parameter',
                'path': 'entitlements/codes',
                'args': [
                    'code',
                    'user_id'
                ],
                'request_type': 'get'
            },
            'redeem_code': {
                'arg_type': 'parameter',
                'path': 'entitlements/code',
                'args': [
                    'code',
                    'user_id'
                ],
                'request_type': 'post'
            },
            'get_top_games': {
                'arg_type': 'parameter',
                'path': 'games/top',
                'args': [
                    '[after]',
                    '[before]',
                    '[first]'
                ],
                'request_type': 'get'
            },
            'get_games': {
                'arg_type': 'parameter',
                'path': 'games',
                'request_type': 'get',
                'args': [
                    '[id]',
                    '[name]',
                ]
            },
            'get_banned_users': {
                'arg_type': 'parameter',
                'path': 'moderation/banned',
                'request_type': 'get',
                'args': [
                    'broadcaster_id',

                    '[user_id]',
                    '[after]',
                    '[before]'

                ]
            },
            'get_moderators': {
                'arg_type': 'parameter',
                'path': 'moderation/moderators',
                'request_type': 'get',
                'args': [
                    'broadcaster_id',
                    '[user_id]',
                    '[after]'
                ]
            },
            'get_streams': {
                'arg_type': 'parameter',
                'path': 'streams',
                'request_type': 'get',
                'args': [
                    '[after]',
                    '[before]',
                    '[first]',
                    '[game_id]',
                    '[language]',
                    '[user_id]',
                    '[user_login]'
                ]
            },
            'get_streams_metadata': {
                'arg_type': 'parameter',
                'path': 'streams/metadata',
                'request_type': 'post',
                'args': [
                    '[after]',
                    '[before]',
                    '[first]',
                    '[game_id]',
                    '[language]',
                    '[user_id]',
                    '[user_login]'
                ]
            },
            'get_stream_tags': {
                'arg_type': 'parameter',
                'path': 'streams/tags',
                'request_type': 'get',
                'args': [
                    'broadcaster_id'
                ]
            },
            'get_users': {
                'arg_type': 'parameter',
                'path': 'users',
                'request_type': 'get',
                'args': [
                    '[id]',
                    '[login]',
                ]
            },
            'get_user_followers': {
                'arg_type': 'parameter',
                'path': 'users/follows',
                'request_type': 'get',
                'args': [
                    '[after]',
                    '[first]',
                    '[from_id]',
                    '[to_id]'
                ]
            },
            'get_videos': {
                'arg_type': 'parameter',
                'path': 'videos',
                'request_type': 'get',
                'args': [
                    '[id]',
                    '[user_id]',
                    '[game_id]',
                    '[after]',
                    '[before]',
                    '[first]',
                    '[language]',
                    '[period]',
                    '[sort]',
                    '[type]'
                ]
            },
        }


class TwitchV5API(API):
    def __init__(self, auth):
        super().__init__(auth)
        self.main_url = 'https://api.twitch.tv/kraken'
        self.headers = {
            'Authorization': f'OAuth {self.auth.token}',
            'Client-ID': self.auth.client_id,
            'Accept': 'application/vnd.twitchtv.v5+json'
        }
        self.end_points = {
            # 'end_point_name': {
            #     'path': 'path/to/end_point',
            #     'args': [
            #         'a',
            #         '[b]'
            #     ],
            #     'request_type': 'get'
            # }
            'check_token': {
                'path': '',
                'args': [

                ],
                'request_type': 'get'
            },
            'get_cheermotes': {
                'path': '/v5/bits/actions',
                'args': [

                ],
                'request_type': 'get'
            },
            'get_channel_by_token': {
                'path': '/channel',
                'args': [],
                'request_type': 'get'
            },
            'get_channel_by_id': {
                'path': '/channels/{id}',
                'args': [
                    'id'
                ],
                'request_type': 'get'
            },
        }


_auth = Auth()
new_api = TwitchNewAPI(_auth)
new_api.generate_functions()
