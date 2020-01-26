#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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
import datetime
import typing

import aiohttp


class ApiError(Exception):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return f'{self.__class__.__name__}({self.message!r})'

    def __str__(self):
        return f'ApiError: {self.message}'


class SupibotAuth:
    def __init__(self, user, token):
        self.user = user
        self.token = token


class SupibotEndpoint:
    def __init__(self, method, url):
        self.url = url
        self.method = method


class SupibotApi:
    def __init__(self, auth_user, auth_token, user_agent=None):
        self.endpoints = []
        self.auth = SupibotAuth(auth_user, auth_token)
        self.user_agent = user_agent
        self.base_url = 'https://supinic.com/api'

    async def request(self, endpoint: typing.Union[SupibotEndpoint, str],
                      data: typing.Optional[typing.Dict[str, typing.Any]] = None,
                      params: typing.Optional[typing.Dict[str, typing.Any]] = None):
        if isinstance(endpoint, str):
            method, url = endpoint.split(' ')
            endpoint = SupibotEndpoint(method.lower(), url)

        headers = {
            'Authorization': f'Basic {self.auth.user}:{self.auth.token}',
        }
        if self.user_agent:
            headers['User-Agent'] = self.user_agent
        return aiohttp.request(endpoint.method, self.base_url + endpoint.url, params=params, data=data,
                               headers=headers)

    async def create_reminder(self, user_for: typing.Union[int, str], text: str,
                              schedule: typing.Optional[datetime.datetime] = None) -> int:
        params = {
            'text': text
        }
        if isinstance(user_for, int):
            params['userID'] = user_for
        elif isinstance(user_for, str):
            params['username'] = user_for
        else:
            raise TypeError(f'{self.__class__.__name__}.create_reminder(), user_for needs to be an "int" or "str"')

        if schedule is not None:
            params['schedule'] = schedule.isoformat()
        async with self.request('post /bot/reminder', params=params) as r:
            if r.status == 200:
                data = await r.json()
                return data['data']['reminderID']
            else:
                print(await r.content)
                raise ApiError(f'API returned non 200 status code: {r.status}')
