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

import argparse
import json
import time

import requests

import twitch_auth

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument('-r', '--refresh', help='Refresh the token', dest='refresh',
               action='store_true')
g.add_argument('-c', '--clip', help='Make a clip', dest='clip', action='store_true')
p.add_argument('-C', '--channel', help='Channel name to clip', dest='c_id', type=str)

args = p.parse_args()

# with open('twitch_api.json', 'r') as f:
#     json_data: dict = json.load(f)
#     orig_data: dict = json_data.copy()


def refresh():
    twitch_auth.refresh()


if args.refresh:
    refresh()
if args.clip:
    c_id_r = requests.get('https://api.twitch.tv/helix/users', params={'login': args.c_id},
                          headers={'Client-ID': twitch_auth.json_data['client_id']})

    c_id = c_id_r.json()['data'][0]['id']
    while 1:
        r = requests.post('https://api.twitch.tv/helix/clips', params={
            'broadcaster_id': c_id
        }, headers={
            'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}'
        })
        print('#', r.json())
        if 'status' in r.json() and r.json()['status'] == 401:
            refresh()
            continue
        if ('status' in r.json()
                and r.json()['status'] == 404
                and r.json()['message'] == 'Clipping is not possible for an offline channel.'):
            print('@error')
            print('OFFLINE')
            print('Clipping is not possible for an offline channel.')
            exit(2)
        break
    while True:
        time.sleep(5)
        r2 = requests.get('https://api.twitch.tv/helix/clips', params={
            'id': r.json()['data'][0]['id']
        }, headers={
            'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}'
        })
        clip_info = r2.json()
        print(f'# {clip_info}')
        if clip_info['data']:
            print(r2.json()['data'][0]['url'])
            break

if twitch_auth.json_data != twitch_auth.orig_data:
    twitch_auth.save()
    # with open('twitch_api.json', 'w') as f:
    #     json.dump(json_data, f, sort_keys=True, indent=4)
