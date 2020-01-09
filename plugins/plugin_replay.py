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
import typing
import math

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

# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'replay'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'replay'
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    async def c_replay(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'time': datetime.timedelta,
                                             'channel': str,
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, Error: {e}'

        if 'time' not in args:
            args['time'] = datetime.timedelta(seconds=30)
        if 'channel' not in args:
            args['channel'] = msg.channel

        async with aiohttp.request('get', 'https://api.twitch.tv/helix/users',
                                   params={'login': args['channel']},
                                   headers={
                                       'Client-ID': main.twitch_auth.json_data["client_id"]
                                   }) as request:
            j_data = await request.json()
            if 'data' not in j_data:
                return f'@{msg.user}, API error (in get-users).'

            if len(j_data['data']) == 0:
                return f'@{msg.user}, failed to find user.'
        user = j_data['data'][0]
        async with aiohttp.request('get', 'https://api.twitch.tv/helix/videos',
                                   params={
                                       'user_id': user['id'],
                                       'sort': 'time',
                                       'first': 1
                                   },
                                   headers={
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

    def __init__(self, module, source):
        super().__init__(module, source)
        self.c_replay = main.bot.add_command('replay')(self.c_replay)
        plugin_help.add_manual_help_using_command('Create a link to the VOD.'
                                                  'Usage: replay [channel:STR] [time:TIME_DELTA]')(self.c_replay)

        plugin_help.create_topic('replay usage', 'replay [channel:STR] [time:TIME_DELTA]',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('replay channel', 'Channel to create the replay from. Must be live.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'replay channel:str'
                                     'replay channel: str'
                                     'replay channel:STR'
                                     'replay channel: STR'
                                 ])
        plugin_help.create_topic('replay time', 'Time to go back in the VOD.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'replay time:time_delta'
                                     'replay time: time_delta'
                                     'replay time:TIME_DELTA'
                                     'replay time: TIME_DELTA'
                                 ])

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return ['replay']

    @property
    def on_reload(self):
        return super().on_reload
