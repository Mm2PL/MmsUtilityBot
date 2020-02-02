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
import asyncio
import datetime
import math
import time
import typing
from typing import List

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
        self.c_nuke_url = main.bot.add_command('nuke_url', required_permissions=['util.nuke_url'],
                                               enable_local_bypass=True)(self.c_nuke_url)
        self.c_unnuke = main.bot.add_command('unnuke', required_permissions=['util.unnuke'],
                                             enable_local_bypass=True)(self.c_unnuke)
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
        plugin_help.create_topic('nuke_url dry-run',
                                 'Don\'t perform any actions just return the results.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url force',
                                 f'Ban or timeout more than {self.max_nuke} users.',
                                 section=plugin_help.SECTION_ARGS)

        plugin_help.create_topic('unnuke',
                                 'Unyimeout or unban in bulk, uses provided url.'
                                 'Usage: unnuke url:URL [+perma] [+dry-run]',
                                 section=plugin_help.SECTION_COMMANDS)
        plugin_help.create_topic('unnuke url',
                                 'Download this and use this as a list of users to revert.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('unnuke perma',
                                 'Use /unban instead of /untimeout',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('nuke_url dry-run',
                                 'Don\'t perform any actions just return the results.',
                                 section=plugin_help.SECTION_ARGS)
        self.connections = []
        self.tasks = []

    async def _send_messages(self, msgs, channels, i):
        print('send messages', msgs)
        connection = main.bot.clone()
        connection.name = str(i)
        connection.cap_reqs(False)
        await asyncio.sleep(0.1)
        connection.receive()
        print(connection.process_messages(max_messages=1000))
        for ch in channels:
            connection.join(ch)
        self.connections.append(connection)
        connection.message_cooldown = 0
        count_of_recv_msgs = 0
        for msg in msgs:
            print(i, msg)
            connection.send(msg)
            await asyncio.sleep(0.1)
            connection.flush_queue()
            connection.receive()
            recv_msgs = connection.process_messages()
            count_of_recv_msgs += len(recv_msgs)
            print(i, recv_msgs)
        connection.disconnect()
        print(f'connection {i} done received {count_of_recv_msgs} messages, sent {len(msgs)}')

    def _parse_line(self, line: str):
        if line.startswith(('#', '//', ';', '%%')):
            return None
        if line.startswith(('.', '/')):
            command = line.replace('.', '', 1).replace('/', '', 1)
            if command.startswith('ban'):
                argv = command.split(' ', 2)
                # .ban user reason
                if len(argv) == 2:  # no reason
                    return argv[1], None
                elif len(argv) == 3:  # reason provided
                    return argv[1], argv[2]
                else:
                    return None
            elif command.startswith('timeout'):
                argv = command.split(' ', 3)
                # .timeout user length reason
                if len(argv) == 3:
                    return argv[1], None
                elif len(argv) == 4:  # reason provided
                    return argv[1], argv[3]
                else:
                    return None
        else:
            return line, None

    def parse_user_list(self, text: str):
        users: List[str] = [
            # 'user_name'
        ]
        reasons = {
            # 'user': 'reason'
        }
        for line in text.splitlines(False):
            res = self._parse_line(line)
            if res is None:
                continue
            u, r = res
            if r is not None:
                reasons[u] = r
            users.append(u)
        return users, reasons

    async def c_nuke(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'regex': str,
                                             'perma': bool,
                                             'timeout': datetime.timedelta,
                                             'search': datetime.timedelta,
                                             'dry-run': bool,
                                             'force': bool,
                                             'hastebin': bool
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
            return await self.nuke_from_messages(args, msg, results, disable_hastebinning=not args['hastebin'])

    async def c_nuke_url(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'dry-run': bool,
                                             'url': str,
                                             'perma': bool,
                                             'force': bool,
                                             'timeout': datetime.timedelta,
                                             'hastebin': bool
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        arg_parser.check_required_keys(args, ('url', 'timeout', 'perma', 'dry-run'))
        if args['url'] is ... or not (args['timeout'] is not ... and args['perma']):
            return f'@{msg.user}, url, timeout are required parameters'
        if args['perma'] is ...:
            args['perma'] = False

        url = args['url']
        if url.startswith(plugin_hastebin.hastebin_addr):
            url = url.replace(plugin_hastebin.hastebin_addr, plugin_hastebin.hastebin_addr + 'raw/')
        async with aiohttp.request('get', url) as req:
            if req.status != 200:
                return f'@{msg.user}, failed to download user list :('
            if req.content_type == 'text/plain':
                users, reasons = self.parse_user_list((await req.text('utf-8'))
                                                      .replace('\r\n', '\n')
                                                      .replace('$(newline)', '\n'))

                while '' in users:
                    users.remove('')

                return await self.nuke(args, msg, users, force_nuke=args['force'],
                                       disable_hastebinning=not args['hastebin'])

    async def nuke_from_messages(self, args, msg, search_results: typing.List[twitchirc.ChannelMessage],
                                 force_nuke=False, ignore_vips=False, ignore_subs=False, disable_hastebinning=False):
        users = []
        ignored = []
        for i in search_results:
            if i.user not in users or i.user in ignored:
                is_sub = False
                if ignore_subs:
                    for k in i.flags['badges']:
                        k: str
                        if k.startswith('subscriber/'):
                            is_sub = True
                            break

                if ('moderator/1' in i.flags['badges']
                        or ('vip/1' in i.flags and ignore_vips)
                        or (ignore_subs and is_sub)):
                    ignored.append(i.user)
                    while i.user in users:
                        users.remove(i.user)
                    continue
                users.append(i.user)

        return await self.nuke(args, msg, users, force_nuke, disable_hastebinning=disable_hastebinning)

    async def nuke(self, args, msg, users, force_nuke=False, reasons=None, disable_hastebinning=False):
        if reasons is None:
            reasons = {}

        if msg.user in users:
            users.remove(msg.user)  # make the executor not get hit by the fallout.
        if main.bot.username.lower() in users:
            users.remove(main.bot.username.lower())

        for u in users.copy():
            m = twitchirc.ChannelMessage(
                text='', user=u, channel=msg.channel, parent=main.bot
            )
            missing_permissions = main.bot.check_permissions(m, ['util.nuke.no_fallout'], enable_local_bypass=False)
            if not missing_permissions:
                users.remove(u)
        if disable_hastebinning:
            url = '(disabled)'
        else:
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
                reason = f'nuked by {msg.user}'
                if u in reasons:
                    reason += f' - {reasons[u]}'
                timeouts.append(msg.reply(f'/timeout {u} {t_o_length}s {reason}', force_slash=True))
        else:
            for u in users:
                reason = f'nuked by {msg.user}'
                if u in reasons:
                    reason += f' - {reasons[u]}'
                timeouts.append(msg.reply(f'/ban {u} {reason}', force_slash=True))

        time_taken = await self._send_using_multiple_connections(msg, timeouts, msg.channel)
        return (f'@{msg.user}, {"timed out" if not args["perma"] else "banned (!!)"} {len(users)} users. '
                f'Full list here: {url}, time taken {round(time_taken)}, '
                f'speed {round(time_taken / len(timeouts)) if timeouts else "N/A"}')

    async def _send_using_multiple_connections(self, msg, timeouts, channel):
        start_time = time.time()
        number_of_needed_connections = math.ceil(len(timeouts) / 100)
        conns = []
        for i in range(number_of_needed_connections):
            batch = []
            for k, m in enumerate(timeouts.copy()):
                if k > 100:
                    break
                batch.append(timeouts.pop())
            conns.append(self._send_messages(batch, [channel], i))
        await asyncio.gather(*conns)
        end_time = time.time()
        return end_time - start_time

    async def c_unnuke(self, msg: twitchirc.ChannelMessage):
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
        arg_parser.check_required_keys(args, ('url', 'timeout', 'perma', 'dry-run'))
        if args['url'] is ... or (args['timeout'] is ... and not args['perma']):
            return f'@{msg.user}, url, timeout are required parameters'
        if args['perma'] is ...:
            args['perma'] = False

        url = args['url']
        if url.startswith(plugin_hastebin.hastebin_addr):
            url = url.replace(plugin_hastebin.hastebin_addr, plugin_hastebin.hastebin_addr + 'raw/')
        async with aiohttp.request('get', url) as req:
            if req.status != 200:
                return f'@{msg.user}, failed to download user list :('
            if req.content_type == 'text/plain':
                users, _ = self.parse_user_list((await req.text('utf-8'))
                                                .replace('\r\n', '\n')
                                                .replace('$(newline)', '\n'))

                while '' in users:
                    users.remove('')

                return await self.unnuke(args, msg, users)

    async def unnuke(self, args, msg, users):
        if msg.user in users:
            users.remove(msg.user)  # make the executor not get hit by the fallout.
        if main.bot.username.lower() in users:
            users.remove(main.bot.username.lower())
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
        # ret.extend(untimeouts)
        time_taken = await self._send_using_multiple_connections(msg, untimeouts, msg.channel)
        # await self._send_messages(untimeouts, [msg.channel], 0)
        return (f'@{msg.user}, {"removed timeouts from" if not args["perma"] else "unbanned"} {len(users)} users. '
                f'Full list here: {url}, time taken {round(time_taken)}, '
                f'speed {round(time_taken / len(untimeouts)) if untimeouts else "N/A"}')

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
