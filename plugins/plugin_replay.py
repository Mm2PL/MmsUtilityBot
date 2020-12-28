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
import math
import random

import twitchirc
import aiohttp

try:
    from .utils import arg_parser
except ImportError:
    try:
        from plugins.utils import arg_parser
    except ImportError:
        # noinspection PyUnresolvedReferences,PyPackageRequirements
        from utils import arg_parser

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

NAME = 'replay'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'replay'
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    name = NAME
    no_reload = False
    commands = ['replay', 'qc']

    async def get_user(self, name, allow_refresh_token=True):
        async with aiohttp.request('get', 'https://api.twitch.tv/helix/users',
                                   params={'login': name},
                                   headers={
                                       'Authorization': f'Bearer {main.twitch_auth.json_data["access_token"]}',
                                       'Client-ID': main.twitch_auth.json_data["client_id"]
                                   }) as request:
            j_data = await request.json()
            if 'status' in j_data and j_data['status'] == 401:
                if allow_refresh_token:
                    main.twitch_auth.refresh()
                    main.twitch_auth.save()
                    return await self.get_user(name, allow_refresh_token=False)
                else:
                    request.raise_for_status()
            return j_data

    async def c_replay(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'time': datetime.timedelta,
                                             'channel': str,
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, Error: {e}'

        if args['time'] is ...:
            args['time'] = datetime.timedelta(seconds=30)
        if args['channel'] is ...:
            args['channel'] = msg.channel

        if args['channel'] != msg.channel:
            j_data = await self.get_user(args['channel'])
            if 'data' not in j_data:
                return f'@{msg.user}, API error (in get-users).'

            if len(j_data['data']) == 0:
                return f'@{msg.user}, failed to find user.'
            user = j_data['data'][0]['id']
        else:
            user = msg.flags['room-id']

        async with aiohttp.request('get', 'https://api.twitch.tv/helix/videos',
                                   params={
                                       'user_id': user,
                                       'sort': 'time',
                                       'first': 1
                                   },
                                   headers={
                                       'Authorization': f'Bearer {main.twitch_auth.json_data["access_token"]}',
                                       'Client-ID': main.twitch_auth.json_data["client_id"]
                                   }) as request:
            j_data = await request.json()
            print(j_data)
            if 'data' not in j_data:
                return f'@{msg.user}, API error (in get-videos).'

            if len(j_data['data']) == 0:
                return f'@{msg.user}, failed to find stream.'
            length = arg_parser.handle_typed_argument(j_data['data'][0]['duration'], datetime.timedelta)
            if args['time'] > length:
                return f'@{msg.user}, FeelsWeirdMan It is not possible to create a replay of before the stream started.'
            t: datetime.timedelta = length - args['time']
            return j_data['data'][0]['url'] + f'?t={math.floor(t.seconds / 3600):0>.0f}h' \
                                              f'{math.floor((t.seconds % 3600) / 60):0>.0f}m' \
                                              f'{math.floor((t.seconds % 3600) % 60):0>.0f}s'

    async def c_clip(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown(cmd='quick_clip', msg=msg, global_cooldown=30, local_cooldown=60)
        if cd_state:
            return
        clip_url = await self.create_clip(msg.flags['room-id'])
        if clip_url == 'OFFLINE':
            return f'@{msg.user}, Cannot create a clip of an offline channel'
        else:
            rand = random.randint(0, 100)
            if rand == 69:
                return f'@{msg.user}, Cliped it LUL {clip_url}'
            else:
                return f'@{msg.user}, Created clip FeelsDankMan {chr(0x1f449)} {clip_url}'

    async def create_clip(self, user_id: int, allow_refresh_token=True, force_wait_for_create=False):
        # attempt to create the clip
        async with aiohttp.request('post', 'https://api.twitch.tv/helix/clips', params={
            'broadcaster_id': str(user_id)
        }, headers={
            'Authorization': f'Bearer {main.twitch_auth.json_data["access_token"]}',
            'Client-ID': main.twitch_auth.json_data['client_id']
        }) as r:
            json = await r.json()
            if r.status == 401:
                if allow_refresh_token:
                    main.twitch_auth.refresh()
                    main.twitch_auth.save()
                    return await self.create_clip(user_id, allow_refresh_token=False)
                else:
                    r.raise_for_status()
            if r.status == 404 and json['message'] == 'Clipping is not possible for an offline channel.':
                return 'OFFLINE'
        clip_id = json['data'][0]['id']
        if force_wait_for_create:
            await asyncio.sleep(1)
            while 1:
                async with aiohttp.request('get', 'https://api.twitch.tv/helix/clips', params={
                    'id': clip_id
                }, headers={
                    'Authorization': f'Bearer {main.twitch_auth.json_data["access_token"]}',
                    'Client-ID': main.twitch_auth.json_data['client_id']
                }) as r:
                    retrieved_clip_data = await r.json()
                    if retrieved_clip_data['data']:
                        return retrieved_clip_data['data'][0]['url']
                await asyncio.sleep(2)
        else:
            return f'https://clips.twitch.tv/{clip_id}'

    def __init__(self, module, source):
        super().__init__(module, source)
        self.c_replay = main.bot.add_command('replay')(self.c_replay)
        self.c_clip = main.bot.add_command('quick_clip', required_permissions=['util.clip'],
                                           available_in_whispers=False)(self.c_clip)
        main.add_alias(main.bot, 'qc')(self.c_clip)

        plugin_help.add_manual_help_using_command('Create a link to the VOD. '
                                                  'Usage: replay [channel:STR] [time:TIME_DELTA]')(self.c_replay)

        plugin_help.add_manual_help_using_command('Creates a clip quickly, usage: quick_clip',
                                                  aliases=[
                                                      'qc',
                                                  ])(self.c_clip)

        plugin_help.create_topic('replay channel', 'Channel to create the replay from. Must be live.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'replay channel:str',
                                     'replay channel: str',
                                     'replay channel:STR',
                                     'replay channel: STR',
                                 ])
        plugin_help.create_topic('replay time', 'Time to go back in the VOD.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'replay time:time_delta',
                                     'replay time: time_delta',
                                     'replay time:TIME_DELTA',
                                     'replay time: TIME_DELTA',
                                 ])
