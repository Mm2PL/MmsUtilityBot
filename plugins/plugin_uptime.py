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
import asyncio
import datetime
import time
from typing import Dict, Union

import aiohttp
from twitchirc import Event


try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

import twitch_auth

__meta_data__ = {
    'name': 'plugin_uptime',
    'commands': [
        'uptime',
        'downtime',
        'title'
    ]
}
log = main.make_log_function('uptime')
UPTIME_CACHE_EXPIRATION_TIME = 60
cache_data_lock = asyncio.Lock()
cached_stream_data: Dict[str, Dict[str, Union[float, Dict[str, str]]]] = {
    # 'channel': {
    #     'expire': time.monotonic(),
    #     'data': {
    #         'started_at': "%Y-%m-%dT%H:%M:%SZ"
    #     }
    # }
}


@main.bot.add_command('title', available_in_whispers=False)
async def command_title(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('title', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    data = await _fetch_stream_data(msg.channel)
    if 'data' in data and len(data['data']):
        return f'@{msg.user}, {data["data"][0]["title"]}'
    else:
        return f'@{msg.user}, Stream not found'


async def _fetch_stream_data(channel, no_refresh=False) -> dict:
    async with aiohttp.request('get', 'https://api.twitch.tv/helix/streams', params={'user_login': channel},
                               headers={
                                   'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}',
                                   'Client-ID': twitch_auth.json_data['client_id']
                               }) as c_uptime_r:
        if c_uptime_r.status == 401 and not no_refresh:
            # get a new oauth token and pray.
            twitch_auth.refresh()
            twitch_auth.save()
            return await _fetch_stream_data(channel, no_refresh=True)
        c_uptime_r.raise_for_status()

        json_data = await c_uptime_r.json()
    data = json_data['data']
    return data


@main.bot.add_command('uptime', available_in_whispers=False)
async def command_uptime(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('uptime', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    now = time.monotonic()
    async with cache_data_lock:
        cache = cached_stream_data.get(msg.channel, {
            'expire': 0,
            'data': None
        })

        cached_stream_data[msg.channel] = cache
        if cache and cache['expire'] > now:
            data = cache['data']
        else:
            data = await _fetch_stream_data(msg.channel)
            if data:
                data = data[0]
                cache['data'] = data
                cache['expire'] = now + UPTIME_CACHE_EXPIRATION_TIME
            else:
                cache['data'] = None

    if data:
        start_time = datetime.datetime(*(time.strptime(data['started_at'],
                                                       "%Y-%m-%dT%H:%M:%SZ")[0:6]))
        uptime = round_time_delta(datetime.datetime.utcnow() - start_time)
        return f'@{msg.user}, {msg.channel} has been live for {uptime!s}'
    else:
        return f'@{msg.user}, {msg.channel} is not live.'


async def _fetch_last_vod_data(channel_id, no_refresh=False):
    async with aiohttp.request('get', 'https://api.twitch.tv/helix/videos',
                               params={
                                   'user_id': channel_id,
                                   'sort': 'time',
                                   'type': 'archive',
                                   'first': '1'
                               },
                               headers={
                                   'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}',
                                   'Client-ID': twitch_auth.json_data['client_id']
                               }) as video_r:
        if video_r.status == 401 and not no_refresh:
            # get a new oauth token and pray.
            twitch_auth.refresh()
            twitch_auth.save()
            return await _fetch_last_vod_data(channel_id, no_refresh=True)
        video_r.raise_for_status()

        json_data = await video_r.json()
    data = json_data['data']
    return data


@main.bot.add_command('downtime', available_in_whispers=False)
async def command_downtime(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('downtime', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    data = await _fetch_stream_data(msg.channel)
    if data:
        return f'@{msg.user}, {msg.channel} is live.'

    vod_data = await _fetch_last_vod_data(msg.flags['room-id'])
    if not vod_data:
        return f'@{msg.user}, no vods found'

    data = vod_data[0]
    duration = _parse_duration(data['duration'])
    struct_time = time.strptime(data['created_at'],
                                "%Y-%m-%dT%H:%M:%SZ")
    created_at = datetime.datetime(year=struct_time[0],
                                   month=struct_time[1],
                                   day=struct_time[2],
                                   hour=struct_time[3],
                                   minute=struct_time[4],
                                   second=struct_time[5])

    now = datetime.datetime.utcnow()
    time_start_difference = now - created_at
    offline_for = round_time_delta(time_start_difference - duration)

    return f'@{msg.user}, {msg.channel} has been offline for {offline_for}'


def round_time_delta(td):
    ntd = datetime.timedelta(seconds=round(td.total_seconds(), 0))
    return ntd


def _parse_duration(duration: str) -> datetime.timedelta:
    buf = ''
    hours = 0
    minutes = 0
    seconds = 0
    for i in duration:
        if i.isnumeric():
            buf += i
        else:
            if i == 's':
                seconds += int(buf)
                buf = ''
            elif i == 'm':
                minutes += int(buf)
                buf = ''
            elif i == 'h':
                hours = int(buf)
                buf = ''
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


class UptimeMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self):
        self.listeners = []

    async def aon_action(self, event: Event):
        if event.name == 'stream-up':
            await self.astream_up(event)
        elif event.name == 'stream-down':
            await self.astream_down(event)
        elif event.name == 'viewcount':
            await self.aviewcount(event)

    async def astream_up(self, event: Event) -> None:
        channel_name = event.data.get('channel_name')
        cache = cached_stream_data.get(channel_name, {
            'expire': 0,
            'data': None
        })
        cached_stream_data[channel_name] = cache

        now = time.monotonic()
        cache['data'] = {
            'started_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        cache['expire'] = now + UPTIME_CACHE_EXPIRATION_TIME

    async def astream_down(self, event: Event) -> None:
        channel_name = event.data.get('channel_name')
        cache = cached_stream_data.get(channel_name, {
            'expire': 0,
            'data': None
        })
        cached_stream_data[channel_name] = cache

        now = time.monotonic()
        cache['data'] = None
        cache['expire'] = now + UPTIME_CACHE_EXPIRATION_TIME

    async def aviewcount(self, event: Event) -> None:
        channel_name = event.data.get('channel_name')
        cache = cached_stream_data.get(channel_name, None)
        if not cache or not cache['data']:
            return  # will have to fetch the start time either way

        cached_stream_data[channel_name] = cache

        now = time.monotonic()
        cache['expire'] = now + UPTIME_CACHE_EXPIRATION_TIME


main.bot.middleware.append(UptimeMiddleware())
