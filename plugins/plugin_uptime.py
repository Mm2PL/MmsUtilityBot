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
import datetime
import time

import aiohttp

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
                                   'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}'
                               }) as c_uptime_r:
        if c_uptime_r.status == 401 and not no_refresh:
            # get a new oauth token and pray.
            twitch_auth.refresh()
            twitch_auth.save()
            return await _fetch_stream_data(channel, no_refresh=True)
        c_uptime_r.raise_for_status()

        json_data = await c_uptime_r.json()
    print(json_data)
    data = json_data['data']
    return data


@main.bot.add_command('uptime', available_in_whispers=False)
async def command_uptime(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('uptime', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    data = await _fetch_stream_data(msg.channel)
    if data:
        data = data[0]
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
                                   'Authorization': f'Bearer {twitch_auth.json_data["access_token"]}'
                               }) as video_r:
        if video_r.status == 401 and not no_refresh:
            # get a new oauth token and pray.
            twitch_auth.refresh()
            twitch_auth.save()
            return await _fetch_last_vod_data(channel_id, no_refresh=True)
        video_r.raise_for_status()

        json_data = await video_r.json()
    print(json_data)
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
    print(duration)

    struct_time = time.strptime(data['created_at'],
                                "%Y-%m-%dT%H:%M:%SZ")
    print(struct_time)
    created_at = datetime.datetime(year=struct_time[0],
                                   month=struct_time[1],
                                   day=struct_time[2],
                                   hour=struct_time[3],
                                   minute=struct_time[4],
                                   second=struct_time[5])

    now = datetime.datetime.utcnow()
    time_start_difference = now - created_at
    offline_for = round_time_delta(time_start_difference - duration)

    print(duration, created_at, offline_for)
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
