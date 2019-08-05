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
