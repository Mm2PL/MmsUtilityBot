#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import typing

import aiohttp
import regex

from plugins.utils import arg_parser

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

main.load_file('plugins/plugin_chat_cache.py')
try:
    import plugin_chat_cache as plugin_chat_cache
except ImportError:
    from plugins.plugin_chat_cache import Plugin as PluginChatCache

    plugin_chat_cache: PluginChatCache

main.load_file('plugins/plugin_hastebin.py')
try:
    import plugin_hastebin as plugin_hastebin
except ImportError:
    from plugins.plugin_hastebin import Plugin as PluginHastebin

    plugin_hastebin: PluginHastebin
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'nuke'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'nuke'
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.c_nuke = main.bot.add_command('nuke', required_permissions=['util.nuke'],
                                           enable_local_bypass=True)(self.c_nuke)
        self.c_nuke_url = main.bot.add_command('nuke_url', required_permissions=['util.nuke'],
                                               enable_local_bypass=True)(self.c_nuke)
        self.max_nuke = 30

        plugin_help.create_topic('nuke',
                                 'Timeout or ban in bulk, searches by message. '
                                 'Usage: nuke regex:REGEX [+perma] timeout:TIME search:TIME [+dry-run] [+force]',
                                 section=plugin_help.SECTION_COMMANDS)
        plugin_help.create_topic('nuke regex',
                                 'Find message by this key.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke perma',
                                 'Ban users permanently USE THIS WITH CAUTION',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke timeout',
                                 'Amount of time to timeout the users for.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke search',
                                 'How much of the message history to search',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke dry-run',
                                 'Don\'t perform any actions just return the results.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke force',
                                 f'Ban or timeout more than {self.max_nuke} users.',
                                 section=plugin_help.SECTION_ARGS)

        plugin_help.create_topic('nuke_url',
                                 'Timeout or ban in bulk, uses provided url.'
                                 'Usage: nuke_url url:URL [+perma] [+force] timeout:TIME [+dry-run]',
                                 section=plugin_help.SECTION_COMMANDS)
        plugin_help.create_topic('nuke_url url',
                                 'Download this and use this as a list of users to punish.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url perma',
                                 'Ban users permanently USE THIS WITH CAUTION',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url timeout',
                                 'Amount of time to timeout the users for.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url search',
                                 'How much of the message history to search',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url dry-run',
                                 'Don\'t perform any actions just return the results.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url force',
                                 f'Ban or timeout more than {self.max_nuke} users.',
                                 section=plugin_help.SECTION_ARGS)

    async def c_nuke(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'regex': str,
                                             'perma': bool,
                                             'timeout': datetime.timedelta,
                                             'search': datetime.timedelta,
                                             'dry-run': bool,
                                             'force': bool
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        arg_parser.check_required_keys(args, ('regex', 'timeout', 'search', 'perma', 'dry-run', 'force'))
        if args['regex'] is ... or args['timeout'] is ... or args['search'] is ...:
            return f'@{msg.user}, regex, timeout and search are required parameters'
        if args['perma'] is ...:
            args['perma'] = False

        try:
            r = regex.compile(args['regex'])
        except Exception as e:
            return f'@{msg.user}, error while compiling regex: {e}'

        results = plugin_chat_cache.find_messages(msg.channel, expr=r,
                                                  min_timestamp=time.time() - args['search'].total_seconds())
        if not results:
            return f'@{msg.user}, found no messages matching the regex.'
        else:
            return await self.nuke_from_messages(args, msg, results)

    async def c_nuke_url(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'dry-run': bool,
                                             'url': str,
                                             'perma': bool,
                                             'force': bool,
                                             'timeout': datetime.timedelta
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        arg_parser.check_required_keys(args, ('url', 'timeout', 'search', 'perma', 'dry-run'))
        if args['url'] is ... or (args['timeout'] is ... and not args['perma']) or args['search'] is ...:
            return f'@{msg.user}, url, timeout and search are required parameters'
        if args['perma'] is ...:
            args['perma'] = False

        url = args['url']
        if url.startswith(plugin_hastebin.hastebin_addr):
            url = url.replace(plugin_hastebin.hastebin_addr, plugin_hastebin.hastebin_addr + 'raw/')
        async with aiohttp.request('get', url) as req:
            if req.status != 200:
                return f'@{msg.user}, failed to download user list :('
            if req.content_type == 'text/plain':
                users = (await req.text('utf-8')).replace('\r\n', '\n').replace('$(newline)', '\n').split('\n')

                while '' in users:
                    users.remove('')

                return await self.nuke(args, msg, users, force_nuke=args['force'])

    async def nuke_from_messages(self, args, msg, search_results, force_nuke=False):
        users = []
        for i in search_results:
            if i.user not in users:
                users.append(i.user)
        return await self.nuke(args, msg, users, force_nuke)

    async def nuke(self, args, msg, users, force_nuke=False):
        if msg.user in users:
            users.remove(msg.user)  # make the executor not get hit by the fallout.
        if main.bot.username.lower() in users:
            users.remove(main.bot.username.lower())
        url = plugin_hastebin.hastebin_addr + await plugin_hastebin.upload("\n".join(users))
        if len(users) > self.max_nuke and not force_nuke:
            return (f'@{msg.user}, {"(dry run)" if args["dry-run"] else ""}'
                    f'refusing to nuke {len(users)} users. Add the +force flag or force nuke the list.'
                    f'Full list here: {url}')
        if args['dry-run'] is True:
            return (f'@{msg.user}, (dry run) {"timing out" if not args["perma"] else "banning (!!)"} {len(users)} '
                    f'users. Full list here: '
                    f'{url}')
        timeouts = []
        if not args['perma']:
            t_o_length = int(args['timeout'].total_seconds())
            for u in users:
                timeouts.append(msg.reply(f'/timeout {u} {t_o_length}s nuked by {msg.user}', force_slash=True))
        else:
            for u in users:
                timeouts.append(msg.reply(f'/ban {u} nuked by {msg.user}', force_slash=True))
        ret = [f'@{msg.user}, {"timing out" if not args["perma"] else "banning (!!)"} {len(users)} users. '
               f'Full list here: {url}']
        ret.extend(timeouts)
        return ret

    async def unnuke(self, args, msg, users):
        users.remove(msg.user)
        users.remove(main.bot.username)
        url = plugin_hastebin.hastebin_addr + await plugin_hastebin.upload("\n".join(users))
        if args['dry-run'] is True:
            return (f'@{msg.user}, {"removing time out from" if not args["perma"] else "unbanning"} {len(users)} '
                    f'users. Full list here: '
                    f'{url}')

        untimeouts = []
        if not args['perma']:
            for u in users:
                untimeouts.append(msg.reply(f'/untimeout {u}', force_slash=True))
        else:
            for u in users:
                untimeouts.append(msg.reply(f'/unban {u}', force_slash=True))
        ret = [f'@{msg.user}, {"removing time out from" if not args["perma"] else "unbanning"} {len(users)} users. '
               f'Full list here: {url}']
        ret.extend(untimeouts)
        return ret

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return ['nuke']

    def on_reload(self):
        pass
