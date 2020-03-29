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
import select
import sys
import threading
import time
import typing
from typing import List, Dict, Any

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
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

try:
    import plugin_logs
except ImportError:

    if typing.TYPE_CHECKING:
        from plugins.plugin_logs import Plugin as PluginLogs

        plugin_logs: PluginLogs
    else:
        plugin_logs = None
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
BAN_T = 0.05


class Plugin(main.Plugin):
    kill_switches: Dict[Any, threading.Event]

    @property
    def max_nuke(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(self.max_nuke_setting)

    @property
    def max_connections(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name] \
            .get(self.max_connections_setting)

    def __init__(self, module, source):
        super().__init__(module, source)
        self.kill_switches = {}
        # region commands
        self.c_nuke = main.bot.add_command('nuke', required_permissions=['util.nuke'],
                                           enable_local_bypass=True, available_in_whispers=False)(self.c_nuke)
        self.c_nuke_url = main.bot.add_command('nuke_url', required_permissions=['util.nuke_url'],
                                               enable_local_bypass=True, available_in_whispers=False)(self.c_nuke_url)
        self.c_unnuke = main.bot.add_command('unnuke', required_permissions=['util.unnuke'],
                                             enable_local_bypass=True, available_in_whispers=False)(self.c_unnuke)
        self.c_stop_nuke = main.bot.add_command('stop_nuke', required_permissions=['util.nuke'],
                                                enable_local_bypass=True, available_in_whispers=False)(self.c_stop_nuke)
        # endregion

        # region help
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
                                 f'Ban or timeout more than "nuke.max_safe" users.',
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
                                 f'Ban or timeout more than "nuke.max_safe" users.',
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
        plugin_help.create_topic('unnuke dry-run',
                                 'Don\'t perform any actions just return the results.',
                                 section=plugin_help.SECTION_ARGS)
        # endregion
        # region settings
        self.max_nuke_setting = plugin_manager.Setting(
            self,
            'nuke.max_safe',
            default_value=15,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        self.max_connections_setting = plugin_manager.Setting(
            self,
            'nuke.max_connections',
            default_value=12,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        # region
        self.connections = []
        self.tasks = []

    async def c_stop_nuke(self, msg: twitchirc.ChannelMessage):
        if msg.channel in self.kill_switches:
            self.kill_switches[msg.channel].set()
            return f'@{msg.user}, Kill switch event triggered, bans should stop any second now.'
        else:
            return f'@{msg.user}, no nuke running in this channel'

    async def _send_messages(self, msgs, channels, i, abort_event: threading.Event):
        print('send messages', msgs)

        connection = twitchirc.Connection(main.bot.address, main.bot.port, message_cooldown=0,
                                          no_atexit=True, secure=main.bot.secure)
        connection.name = str(i)
        connection.cap_reqs(False)
        connection.connect(main.bot.username, 'oauth:' + main.twitch_auth.new_api.auth.token)
        await asyncio.sleep(0.5)
        connection.receive()
        print(connection.process_messages(max_messages=1000))
        for ch in channels:
            connection.join(ch)
        self.connections.append(connection)
        connection.message_cooldown = 0
        count_of_recv_msgs = 0

        for num, msg in enumerate(msgs):
            if abort_event.is_set():
                print('ABORT ABORT ABORT ABORT')
                break
            # print(i, msg)
            # print(num % 100 == 0)
            connection.send(msg)
            await asyncio.sleep(BAN_T)
            connection.flush_queue()
            if num % 500 == 0:
                sel_output, _, _ = select.select([connection.socket], [], [], 0)
                if sel_output:
                    print(connection.receive())
                    recv_msgs = connection.process_messages()
                    print(recv_msgs)
                    count_of_recv_msgs += len(recv_msgs)
                    print(i, recv_msgs)

        await asyncio.sleep(10 * BAN_T)
        sel_output, _, _ = select.select([connection.socket], [], [], 0)
        if sel_output:
            connection.receive()

        recv_msgs = connection.process_messages()
        count_of_recv_msgs += len(recv_msgs)
        connection.disconnect()
        print(f'connection {i} done received {count_of_recv_msgs} messages, sent {len(msgs)}')
        return count_of_recv_msgs

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
            args = arg_parser.parse_args(
                main.delete_spammer_chrs(msg.text),
                {
                    'dry-run': bool,
                    'url': str,
                    'perma': bool,
                    'force': bool,
                    'timeout': datetime.timedelta,
                    'hastebin': bool
                },
                defaults={
                    'dry-run': False,
                    'perma': False,
                    'hastebin': False,
                    'timeout': ...,
                    'force': False
                })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        if args['url'] is ... or (args['timeout'] is ... and not args['perma']):
            print(args)
            return f'@{msg.user}, url, timeout (or perma) are required parameters'

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
                                       disable_hastebinning=not args['hastebin'], reasons=reasons)
            else:
                return f'Refusing to use data, bad content type: {req.content_type}, expected text/plain'

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

        return await self.nuke(args, msg, users, force_nuke, disable_hastebinning=disable_hastebinning,
                               show_nuked_by=True)

    async def nuke(self, args, msg, users, force_nuke=False, reasons=None, disable_hastebinning=False,
                   show_nuked_by=False):
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
                if show_nuked_by:
                    reason = f'nuked by {msg.user} - '
                else:
                    reason = ''
                if u in reasons:
                    reason += reasons[u]
                timeouts.append(msg.reply(f'/timeout {u} {t_o_length}s {reason}', force_slash=True))
        else:
            for u in users:
                if show_nuked_by:
                    reason = f'nuked by {msg.user} - '
                else:
                    reason = ''
                if u in reasons:
                    reason += reasons[u]
                timeouts.append(msg.reply(f'/ban {u} {reason}', force_slash=True))

        number_of_needed_connections = self._calculate_number_of_connections(timeouts)
        main.bot.send(msg.reply_directly(self._make_nuke_notification_whisper(args, msg, number_of_needed_connections,
                                                                              timeouts, users)))
        main.bot.flush_queue(1)
        num_of_timeouts = len(timeouts)
        db_log_level_bkup = plugin_logs.db_log_level
        log_level_bkup = plugin_logs.log_level
        try:
            if plugin_logs:
                plugin_logs.db_log_level = plugin_logs.log_levels['warn']  # don't spam the logs
                plugin_logs.log_level = plugin_logs.log_levels['warn']
            # time_taken = await self._send_using_multiple_connections(msg, timeouts, msg.channel,
            #                                                          number_of_needed_connections)
            time_taken = await self._send_using_new_connection_thread(msg, timeouts, msg.channel,
                                                                      number_of_needed_connections)
        finally:
            plugin_logs.db_log_level = db_log_level_bkup
            plugin_logs.log_level = log_level_bkup
        return self._make_nuke_end_message(msg, args, users, url, time_taken, timeouts)

    # async def _send_using_multiple_connections(self, msg, timeouts, channel, number_of_needed_connections):
    #     start_time = time.time()
    #     conns = []
    #     messages_per_connection = len(timeouts) / number_of_needed_connections
    #     abort_lock = asyncio.Event()
    #     for i in range(number_of_needed_connections):
    #         batch = []
    #         for k, m in enumerate(timeouts.copy()):
    #             if k > messages_per_connection:
    #                 break
    #             batch.append(timeouts.pop())
    #         print(batch)
    #         conns.append(self._send_messages(batch, [channel], i, abort_lock))
    #     try:
    #         await asyncio.gather(*conns)
    #     except BaseException:
    #         abort_lock.set()
    #
    #     end_time = time.time()
    #     return end_time - start_time

    async def _send_using_new_connection_thread(self, msg, timeouts, channel, number_of_conns):
        start_time = time.time()
        kill_switch = threading.Event()
        # await asyncio.get_event_loop().run_in_executor(None,
        #                                                lambda: self._send_messages(timeouts, [channel], 0,
        #                                                                            kill_switch))
        self.kill_switches[msg.channel] = kill_switch
        await asyncio.get_event_loop().run_in_executor(None, lambda: self._connection_thread(timeouts, channel,
                                                                                             number_of_conns,
                                                                                             kill_switch))
        end_time = time.time()
        return end_time - start_time

    def _new_connection(self, channel, conn_number):
        try:
            connection = twitchirc.Connection(main.bot.address, main.bot.port, message_cooldown=0,
                                              no_atexit=True, secure=main.bot.secure)
            connection.name = str(conn_number)
            connection.cap_reqs(False)
            connection.connect(main.bot.username, 'oauth:' + main.twitch_auth.new_api.auth.token)
            connection.receive()
            print(connection.process_messages(max_messages=1000))
            connection.join(channel)
            self.connections.append(connection)
            connection.message_cooldown = 0
            return connection
        except BrokenPipeError:  # rate limited?
            print('Got broken pipe when creating connection, are we rate limited? Retrying to create this connection.')
            time.sleep(5)
            return self._new_connection(channel, conn_number)

    def _create_connections(self, number, channel):
        conns = []
        for i in range(number):
            connection = self._new_connection(channel, i)

            conns.append(connection)
        return conns

    def _send_and_flush(self, conn: twitchirc.Connection, msg, conns, channel, current_connection):
        try:
            conn.force_send(msg)
        except BrokenPipeError:
            # we lost a connection
            conns.remove(conn)
            print('We lost a connection. Recreating.')
            time.sleep(3)
            conns.append(self._new_connection(channel, current_connection))
            self._send_and_flush(conn, msg, conns, channel, current_connection)

    def _connection_thread(self, timeouts, channel, number_of_needed_connections, kill_switch):
        # works in another thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        conns = self._create_connections(number_of_needed_connections + 1, channel)
        try:
            current_connection = 0
            confirmed = []
            recv_conn = conns.pop()
            max_timeout_id = len(timeouts) - 1
            for num, timeout_obj in enumerate(timeouts):
                if kill_switch.is_set():
                    break
                conn = conns[current_connection]
                self._send_and_flush(conn, timeout_obj, conns, channel, current_connection)

                # conn.receive()
                conn.receive_buffer = ''
                current_connection += 1
                if current_connection >= len(conns):
                    current_connection = 0
                    time.sleep(BAN_T)  # keep rate limits

                if num % 500 == 0 or num == max_timeout_id:
                    while 1:
                        if num == max_timeout_id:
                            time.sleep(2)

                        recv_ready, _, _ = select.select([recv_conn.socket], [], [], 0)
                        if not recv_ready:
                            break
                        recv_conn.receive()
                        msgs = recv_conn.process_messages(1000)
                        for m in msgs:
                            if isinstance(m, (twitchirc.ChannelMessage, twitchirc.WhisperMessage, twitchirc.JoinMessage,
                                              twitchirc.UserstateMessage, twitchirc.NoticeMessage,
                                              twitchirc.GlobalNoticeMessage)):
                                continue

                            if isinstance(m, twitchirc.PingMessage):
                                conn.send(m.reply())
                            elif isinstance(m, twitchirc.Message):  # other messages
                                data = m.raw_data or m.args
                                if 'CLEARCHAT' in data:
                                    # '@room-id=117691339;target-user-id=70948394;tmi-sent-ts=1585480138749
                                    # :tmi.twitch.tv
                                    # CLEARCHAT
                                    # #mm2pl :weeb123\r\n'
                                    user = data.split(' ', 4)[-1].lstrip(':').rstrip('\r\n')
                                    confirmed.append(user)


        finally:
            print(timeouts)
            print(confirmed)
            sys.stderr.write(f'{len(timeouts)}, {len(confirmed)}\n')
            sys.stderr.write(f'Diff is {len(timeouts) - len(confirmed)}\n')
            for i in conns:
                i.disconnect()

    def _calculate_number_of_connections(self, timeouts):
        number_of_needed_connections = math.ceil(len(timeouts) / 100)
        print(number_of_needed_connections)
        if number_of_needed_connections > self.max_connections:
            number_of_needed_connections = self.max_connections
        print(number_of_needed_connections)
        return number_of_needed_connections

    async def c_unnuke(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(
                main.delete_spammer_chrs(msg.text),
                {
                    'dry-run': bool,
                    'url': str,
                    'perma': bool,
                    'force': bool,
                    'hastebin': bool
                },
                defaults={
                    'dry-run': False,
                    'perma': False,
                    'force': False,
                    'hastebin': False
                })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        if args['url'] is ...:
            return f'@{msg.user}, url is a required parameter'
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

                return await self.unnuke(args, msg, users, disable_hastebinning=(not args['hastebin']))

    async def unnuke(self, args, msg, users, disable_hastebinning=False):
        if msg.user in users:
            users.remove(msg.user)  # make the executor not get hit by the fallout.
        if main.bot.username.lower() in users:
            users.remove(main.bot.username.lower())
        if not disable_hastebinning:
            url = plugin_hastebin.hastebin_addr + await plugin_hastebin.upload("\n".join(users))
        else:
            url = '(disabled)'
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
        # time_taken = await self._send_using_multiple_connections(msg, untimeouts, msg.channel)
        number_of_needed_connections = self._calculate_number_of_connections(untimeouts)
        main.bot.send(msg.reply_directly(self._make_nuke_notification_whisper(args, msg, number_of_needed_connections,
                                                                              untimeouts, users, unban=True)))
        main.bot.flush_queue(1)
        log_level_bkup = plugin_logs.db_log_level
        try:
            if plugin_logs:
                plugin_logs.db_log_level = plugin_logs.log_levels['warn']  # don't spam the logs
            # time_taken = await self._send_using_multiple_connections(msg, timeouts, msg.channel,
            #                                                          number_of_needed_connections)
            time_taken = await self._send_using_new_connection_thread(msg, untimeouts, msg.channel,
                                                                      number_of_needed_connections)
        finally:
            plugin_logs.db_log_level = log_level_bkup
        # await self._send_messages(untimeouts, [msg.channel], 0)
        return self._make_nuke_end_message(msg, args, users, url, time_taken, untimeouts, unban=True)

    def _make_nuke_notification_whisper(self, args, msg, number_of_needed_connections, timeouts, users,
                                        unban=False):
        time_prediction = 1.26 * BAN_T * len(timeouts) / number_of_needed_connections
        ban_f = 1 / BAN_T
        if unban:
            action = "remove time outs from" if not args["perma"] else "unbanning"
        else:
            action = "timing out" if not args["perma"] else "banning"
        return (f'@{msg.user}, {action} '
                f'{len(users)} users. This operation will use {number_of_needed_connections} '
                f'connections, at {ban_f} Hz * {number_of_needed_connections}, '
                f'it will take about {time_prediction:.2f}s, please wait patiently monkaS')

    def _make_nuke_end_message(self, msg, args, users, url, time_taken, timeouts, unban=False):
        if unban:
            return (f'@{msg.user}, {"removed timeouts from" if not args["perma"] else "unbanned"} {len(users)} users. '
                    f'Full list here: {url} , time taken {round(time_taken)}s, '
                    f'speed {round(len(timeouts) / time_taken) if timeouts else "N/A"}Hz')
        else:
            return (
                f'@{msg.user}, {"timed out" if not args["perma"] else "banned (!!)"} {len(users)} users. '
                f'Full list here: {url} , time taken {round(time_taken)}s, '
                f'speed {round(len(timeouts) / time_taken) if time_taken else "N/A"}Hz'
            )

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
