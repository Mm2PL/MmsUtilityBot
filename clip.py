import argparse
import json
import time

import requests

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument('-r', '--refresh', help='Refresh the token', dest='refresh',
               action='store_true')
g.add_argument('-c', '--clip', help='Make a clip', dest='clip', action='store_true')
p.add_argument('-C', '--channel', help='Channel name to clip', dest='c_id', type=str)

args = p.parse_args()

with open('twitch_api', 'r') as f:
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


if args.refresh:
    refresh()
if args.clip:
    c_id_r = requests.get('https://api.twitch.tv/helix/users', params={'login': args.c_id},
                          headers={'Client-ID': json_data['client_id']})

    c_id = c_id_r.json()['data'][0]['id']
    while 1:
        r = requests.post('https://api.twitch.tv/helix/clips', params={
            'broadcaster_id': c_id
        }, headers={
            'Authorization': f'Bearer {json_data["access_token"]}'
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
            'Authorization': f'Bearer {json_data["access_token"]}'
        })
        clip_info = r2.json()
        print(f'# {clip_info}')
        if clip_info['data']:
            print(r2.json()['data'][0]['url'])
            break

if json_data != orig_data:
    with open('twitch_api', 'w') as f:
        json.dump(json_data, f, sort_keys=True, indent=4)
