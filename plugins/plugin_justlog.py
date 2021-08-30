#  This is a simple utility bot
#  Copyright (C) 2021 Mm2PL
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
import collections
import copy
import dataclasses
import datetime
import time
import typing
import unicodedata
from typing import List, Generator

import aiohttp
import regex
import twitchirc

import util_bot.clients.twitch as twitch_client
import util_bot
import plugins.utils.arg_parser as arg_parser
from util_bot import StandardizedMessage

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager
try:
    import plugin_hastebin
except ImportError:
    import plugins.plugin_hastebin as plugin_hastebin_module

    plugin_hastebin: plugin_hastebin_module.Plugin
    exit(1)
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit()
NAME = 'justlog'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'logs'
    ]
}
log = util_bot.make_log_function(NAME)


@dataclasses.dataclass
class Stats:
    io_wait_time = 0
    parse_time = 0
    filter_time = 0
    messages_processed = 0


class Plugin(util_bot.Plugin):
    _current_log_fetch: typing.Optional[asyncio.Task]
    loggers: List['JustLogApi']

    def __init__(self, module, source):
        super().__init__(module, source)
        self.command_logs = util_bot.bot.add_command(
            'logs',
            enable_local_bypass=False,
            cooldown=util_bot.CommandCooldown(5, 0, 0, False)
        )(self.command_logs)
        self.logger_setting = plugin_manager.Setting(
            self,
            'justlog.loggers',
            default_value=[],
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True,
            on_load=self._load_loggers,
            help_='List of JustLog instances'
        )
        plugin_help.add_manual_help_using_command(
            'Searches known JustLog instances. '
            'Usage: _logs regex:"REGULAR EXPRESSION" [user:USERNAME|#USERID] '
            '[from:DATETIME|lookback:TIMEDELTA] [to:DATETIME] [max:COUNT] '
            '[channel:USERNAME] [expire:TIMEDELTA]',
            aliases=[
                'mb.logs'
            ]
        )(self.command_logs)

        plugin_help.create_topic(
            'logs regex',
            'Regular expression to filter messages by. Required.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs regex'
            ]
        )
        plugin_help.create_topic(
            'logs user',
            'Filter logs by user. Can be an id prefixed with a "#" or a username.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs user'
            ]
        )
        plugin_help.create_topic(
            'logs from',
            'Beginning date for the search. Must be before `logs to`. '
            'Default: current datetime - 30 days.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs from'
            ]
        )
        plugin_help.create_topic(
            'logs to',
            'Ending date for the search. Must be after `logs from`. '
            'Default: current datetime',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs to'
            ]
        )
        plugin_help.create_topic(
            'logs max',
            'Maximum count of messages returned',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs max'
            ]
        )
        plugin_help.create_topic(
            'logs channel',
            'Channel to pull the logs from.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs channel'
            ]
        )
        plugin_help.create_topic(
            'logs simple',
            'Use JustLog\'s simple text format.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs simple'
            ]
        )
        plugin_help.create_topic(
            'logs lookback',
            'How much time to look through when checking logs. '
            'Here be dragons: If this value is too big you will experience general slowness and if it is big enough '
            'you could crash the bot.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs lookback'
            ]
        )
        plugin_help.create_topic(
            'logs expire',
            'When should the hastebin expire expressed as a duration of time.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs expire'
            ]
        )
        plugin_help.create_topic(
            'logs context',
            'How many messages of context to show. Use "before" and "after" to adjust it separately.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs context',
                'mb.logs before',
                'mb.logs after',
                'logs before',
                'logs after',
            ]
        )
        plugin_help.create_topic(
            'logs cancel',
            'Cancel a running log fetch. You cannot cancel another person\'s log fetch unless you have the '
            '`util.logs.cancel_other` permission.',
            plugin_help.SECTION_ARGS,
            links=[
                'mb.logs cancel'
            ]
        )
        self.loggers = []
        self._current_log_fetch = None
        self._current_log_owner = None

    def _load_loggers(self, settings: plugin_manager.ChannelSettings):
        val: list = settings.get(self.logger_setting)
        self.loggers.clear()
        for i in val:
            self.loggers.append(JustLogApi(i))

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return ['logs']

    @property
    def on_reload(self):
        return super().on_reload

    async def _justlog_for_channel(self, channel: str):
        for i in self.loggers:
            if await i.has_channel(channel):
                return i
        return None

    async def command_logs(self, msg: util_bot.StandardizedMessage):
        missing_perms = await util_bot.bot.acheck_permissions(msg, ['util.logs', 'util.logs.channel.*'])
        if 'util.logs' in missing_perms:
            return (util_bot.CommandResult.NO_PERMISSIONS,
                    f'@{msg.user} You don\'t have the permissions to use this command.')
        if msg.platform != util_bot.Platform.TWITCH:
            return (util_bot.CommandResult.OTHER_FILTERED,
                    f'{msg.user_mention} This command only works on Twitch! Use whispers if needed.')
        try:
            args = arg_parser.parse_args(
                msg.text,
                {
                    # filter criteria
                    'user': str,
                    'regex': regex.compile,
                    'from': (datetime.datetime, {'includes_end': False}),
                    'to': (datetime.datetime, {'includes_end': True}),
                    'lookback': datetime.timedelta,

                    # other settings
                    'max': int,  # max results
                    'channel': str,

                    'simple': bool,
                    'expire': datetime.timedelta,

                    'cancel': bool,
                    'logviewer': bool,
                    'text': bool,

                    'before': int,
                    'after': int,
                    'context': int
                },
                defaults={
                    'user': None,
                    'regex': None,
                    'from': datetime.datetime.utcnow() - datetime.timedelta(days=30.0),
                    'to': datetime.datetime.utcnow(),
                    'lookback': None,

                    'max': 100,
                    'channel': msg.channel,
                    'simple': False,
                    'expire': datetime.timedelta(days=7),

                    'cancel': False,
                    'logviewer': True,
                    'text': False,

                    'before': 0,
                    'after': 0,
                    'context': 0
                },
                strict_escapes=False
            )
        except arg_parser.ParserError as e:
            return (util_bot.CommandResult.OTHER_FAILED,
                    f'@{msg.user} {e.message}')
        if args['cancel']:
            if self._current_log_fetch:
                missing_permissions = await util_bot.bot.acheck_permissions(msg, ['util.logs.cancel_other'])
                if self._current_log_owner == msg.user or not missing_permissions:
                    print('Cancelling log fetch!')
                    self._current_log_fetch.cancel()
                    return None
                else:
                    await util_bot.bot.send(
                        msg.reply_directly(f'You don\'t have permissions to cancel this log fetch.'))
                    await util_bot.bot.flush_queue()
                    return None
            else:
                return f"@{msg.user}, There's nothing to cancel!"
        if args['channel'] == 'whispers' and msg.channel == 'whispers':
            return (util_bot.CommandResult.OTHER_FAILED,
                    f'@{msg.user}, To use this command in whispers you need to provide a channel, like '
                    f'"channel:pajlada"')
        missing_chan_permissions = await util_bot.bot.acheck_permissions(msg, [f'util.logs.channel.{args["channel"]}'])
        if missing_chan_permissions and missing_perms:
            return (util_bot.CommandResult.NO_PERMISSIONS,
                    f'@{msg.user} You don\'t have the permissions to search for logs in channel {args["channel"]}')
        logger = await self._justlog_for_channel(args['channel'])
        if not logger:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'No matching JustLog instance found :(')
        if not args['regex']:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'Missing required argument "regex"')
        if args['lookback']:
            args['from'] = args['to'] - args['lookback']

        if args['simple']:
            log_format = 'simple'
            args['text'] = False
            args['logviewer'] = False
        elif args['text']:
            log_format = 'pretty'
            args['simple'] = False
            args['logviewer'] = False
        else:
            log_format = 'raw'
            args['simple'] = False
            args['text'] = False

        if args['context']:
            args['before'] = args['context']
            args['after'] = args['context']
        users = []
        not_users = []
        if args.get('user'):
            for i in args['user'].lower().split(','):
                if i.startswith('!'):
                    not_users.append(i.lstrip('!'))
                else:
                    users.append(i)

        stats = Stats()
        filter_task = asyncio.create_task(self._filter_messages(
            logger,
            channel=args['channel'],
            users=users,
            not_users=not_users,
            regular_expr=args['regex'],
            start=args['from'],
            end=args['to'],
            count=args['max'],
            stats=stats,
            ctx_before=args['before'],
            ctx_after=args['after']
        ))
        self._current_log_fetch = asyncio.current_task()
        self._current_log_owner = msg.user
        try:
            try:
                matched = await asyncio.wait_for(asyncio.shield(filter_task), timeout=5)
            except asyncio.TimeoutError:
                additional_message = ('Using local user filtering, because you used advanced user searching.'
                                      if len(users) > 1 or not_users else '')
                await util_bot.bot.send(msg.reply(f'@{msg.user}, Looks like this log fetch will take a while, '
                                                  f'do `_logs --cancel` to abort. '
                                                  f'{stats.messages_processed} msgs processed '
                                                  f'{additional_message}'))
                matched = None
            if not filter_task.done():
                matched = await filter_task
        except asyncio.CancelledError:
            self._current_log_fetch = None
            self._current_log_owner = None
            filter_task.cancel()
            return f'@{msg.user} The log fetch was cancelled.'

        self._current_log_fetch = None
        self._current_log_owner = None
        hastebin_link = await self._hastebin_result(matched, args, datetime.datetime.utcnow() + args['expire'],
                                                    log_format)
        if args['logviewer']:
            channel_id = list(filter(lambda o: o.name == args['channel'], logger.channels))[0].id

            return (util_bot.CommandResult.OK,
                    f'Uploaded {len(matched)} filtered messages to hastebin. Use --text for plaintext, '
                    f'--simple for justlog format. '
                    f'{stats.messages_processed} messages processed, '
                    f'waited {stats.io_wait_time:.2f}s for downloads, '
                    f'{stats.parse_time:.2f}s for parsing,'
                    f'Log viewer link: '
                    f'https://logviewer.kotmisia.pl/?url=/h/{hastebin_link}&c={args["channel"]}&cid={channel_id}')
        return (util_bot.CommandResult.OK,
                f'Uploaded {len(matched)} filtered messages to hastebin: '
                f'{plugin_hastebin.hastebin_addr}raw/{hastebin_link}')

    async def _filter_messages(self, logger: 'JustLogApi', channel,
                               users: List[str], not_users: List[str],
                               regular_expr: typing.Pattern, start, end, count,
                               ctx_before: int,
                               ctx_after: int,
                               stats: Stats):
        matched = []
        context = collections.deque([], maxlen=ctx_before)
        spacer = twitchirc.auto_message('@msg-id=log_spacer :tmi.twitch.tv NOTICE * :' + '-' * 80)
        ctx_after_add = 0
        if len(users) == 1:
            is_userid = False
            user = users[0]
            if user and user.startswith('#'):
                user = user.lstrip('#')
                is_userid = True
            async for i in logger.iterate_logs_for_user(channel, user, start, end, is_userid=is_userid, stats=stats):
                if len(matched) >= count:
                    break

                context.append(i)
                did_match, ctx_after_add = await self._filter_message(
                    context, ctx_after, ctx_after_add, ctx_before, i, matched,
                    regular_expr,
                    spacer, stats
                )
                if not did_match:
                    cpy = copy.copy(i)
                    cpy.flags = copy.copy(i.flags)
                    cpy.flags['match'] = 'ctxb'

                    context.append(cpy)
        else:
            async for i in logger.iterate_logs_for_channel(channel, start, end, stats=stats):
                if len(matched) >= count:
                    break

                uid = '#' + i.flags.get('user-id', '')
                if (i.user in not_users or uid in not_users) or (users and i.user not in users and uid not in users):
                    continue

                did_match, ctx_after_add = await self._filter_message(
                    context, ctx_after, ctx_after_add, ctx_before, i, matched,
                    regular_expr,
                    spacer, stats
                )
                if not did_match:
                    cpy = copy.copy(i)
                    cpy.flags = copy.copy(i.flags)
                    cpy.flags['match'] = 'ctxb'

                    context.append(cpy)

        return matched

    async def _filter_message(self, context, ctx_after, ctx_after_add, ctx_before, message, matched, regular_expr,
                              spacer, stats) -> typing.Tuple[bool, int]:
        filter_start = time.monotonic()
        try:
            if regular_expr.search(message.text):
                if ctx_before:
                    if not ctx_after:
                        matched.append(spacer)
                    matched.extend(context)
                    context.clear()
                matched.append(message)
                message.flags['match'] = 'y'
                ctx_after_add = ctx_after
                return True, ctx_after_add
            elif ctx_after_add:
                ctx_after_add -= 1
                message.flags['match'] = 'ctxa'
                matched.append(message)
                if ctx_after_add == 0:
                    matched.append(spacer)
        finally:
            filter_end = time.monotonic()
            stats.filter_time += filter_end - filter_start
        return False, ctx_after_add

    def _convert_to_simple_text(self, matched: List[StandardizedMessage]) -> str:
        output = ''
        for msg in matched:
            dt = datetime.datetime.utcfromtimestamp(int(msg.flags["tmi-sent-ts"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            output += f'[{dt}] #{msg.channel} {msg.user}: {msg.text}\n'
        return output

    async def _hastebin_result(self, matched: List[StandardizedMessage], args, expire_on, log_format):
        if log_format == 'simple':
            output = self._convert_to_simple_text(matched)
        elif log_format == 'pretty':
            output = self._convert_to_pretty_text(args, expire_on, matched)
        elif log_format == 'raw':
            output = self._convert_to_raw_irc(args, expire_on, matched)
        else:
            raise RuntimeError('Invalid log format.')
        return await plugin_hastebin.upload(output, expire_on)

    def _convert_to_raw_irc(self, args, expire_on, matched):
        output = ''
        for i in (f'Found {len(matched)} (out of maximum {args["max"]}) messages',
                  f'Channel: #{args["channel"]}',
                  f'User: {args["user"] or "[any]"}',
                  f'Start date/time: {args["from"]}',
                  f'End date/time: {args["to"]}',
                  f'Search regex: {args["regex"].pattern}',
                  f'This paste expires on: {expire_on} or in {args["expire"]}'):
            output += f'@msg-id=log_info :tmi.twitch.tv NOTICE * :{i}\n'

        for msg in matched:
            output += bytes(msg).decode() + '\r\n'
        return output

    def _convert_to_pretty_text(self, args, expire_on, matched):
        output = (f'# {"=" * 78}\n'
                  f'# Found {len(matched)} (out of maximum {args["max"]}) messages\n'
                  f'# Channel: #{args["channel"]}\n'
                  f'# User: {args["user"] or "[any]"}\n'
                  f'# Start date/time: {args["from"]}\n'
                  f'# End date/time: {args["to"]}\n'
                  f'# Search regex: {args["regex"].pattern}\n'
                  f'# This paste expires on: {expire_on} or in {args["expire"]}\n'
                  f'# {"=" * 78}\n')
        for i in matched:
            badges = i.flags.get('badges', '').split(',')
            chan_badges = ''
            for b in badges:
                if b.startswith('subscriber/'):
                    chan_badges += b.replace('subscriber/', '') + unicodedata.lookup('GLOWING STAR')
                elif b.startswith('bits/'):
                    chan_badges += b.replace('bits/', '') + unicodedata.lookup('MONEY BAG')
            dt = datetime.datetime.utcfromtimestamp(int(i.flags["tmi-sent-ts"]) / 1000).isoformat(sep=" ")
            output += (f'[{dt}] '
                       f'{self._pretty_badges(badges)}'
                       f'{chan_badges}'
                       f'<{i.user}> {i.text}\n')
        return output

    def _pretty_badges(self, badges) -> str:
        return (
                ((unicodedata.lookup("CROSSED SWORDS") + " ") if "moderator/1" in badges else "")
                + ((unicodedata.lookup("GEM STONE") + " ") if "vip/1" in badges else "")
                + ((unicodedata.lookup("CINEMA") + " ") if "broadcaster/1" in badges else "")
                + ((unicodedata.lookup("WRENCH") + " ") if "staff/1" in badges else "")
        )


class JustLogApi:
    channels: List['JustlogChannel']

    def __init__(self, address: str):
        self.address = address
        self.channels = []

    async def logs_for_user(self, channel: str, user: str,
                            year: typing.Optional[int] = None,
                            month: typing.Optional[int] = None,
                            reverse=False, is_userid: bool = False, stats: typing.Optional[Stats] = None):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        date_frag = ''
        if year is not None and month is not None:
            date_frag = f'/{year}/{month}'

        params = {'raw': '1'}
        if reverse:
            params['reverse'] = '1'

        log('warn', f'Fetch logs for {user}@#{channel} for {year} {month}')
        return fetch_and_convert_messages(
            self.address + f'/channel/{channel}/user{"id" if is_userid else ""}/{user}{date_frag}',
            params,
            stats
        )

    async def logs_for_channel(self, channel: str,
                               year: typing.Optional[int] = None,
                               month: typing.Optional[int] = None,
                               day: typing.Optional[int] = None,
                               reverse=False, stats: typing.Optional[Stats] = None):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        date_frag = ''
        if year is not None and month is not None and day is not None:
            date_frag = f'/{year}/{month}/{day}'

        params = {'raw': '1'}
        if reverse:
            params['reverse'] = '1'
        log('warn', f'JustLog at {self.address}: logs for channel {channel} at {date_frag}')
        return fetch_and_convert_messages(
            self.address + f'/channel/{channel}{date_frag}',
            params,
            stats
        )

    async def iterate_logs_for_user(self, channel: str, user: str,
                                    start: typing.Optional[datetime.datetime],
                                    end: datetime.datetime, is_userid=False, stats: typing.Optional[Stats] = None):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        days = (end - start).days
        last_date = start
        for day in range(days, 0, -1):
            cdate = start + datetime.timedelta(days=day)
            if cdate.month != last_date.month or day == 0:
                last_date = cdate
                iterator = await self.logs_for_user(channel, user, year=cdate.year, month=cdate.month,
                                                    is_userid=is_userid, stats=stats)
                if iterator is None:
                    break
                async for msg in iterator:
                    tmi_sent_ts = datetime.datetime.utcfromtimestamp(int(msg.flags.get('tmi-sent-ts', 0)) / 1000)
                    if (start and tmi_sent_ts < start) or tmi_sent_ts > end:
                        continue

                    yield msg

    async def iterate_logs_for_channel(self, channel: str,
                                       start: typing.Optional[datetime.datetime],
                                       end: datetime.datetime, stats: typing.Optional[Stats] = None):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        days = (end - start).days
        if days <= 0:
            days = 1

        utc_offset = datetime.datetime.now() - datetime.datetime.utcnow()
        for day in range(days, 0, -1):
            cdate = start + datetime.timedelta(days=day)
            iterator = await self.logs_for_channel(channel, year=cdate.year, month=cdate.month, day=cdate.day,
                                                   stats=stats)
            if iterator is None:
                break
            async for msg in iterator:
                tmi_sent_ts = (datetime.datetime.fromtimestamp(int(msg.flags.get('tmi-sent-ts', 0)) / 1000)
                               - utc_offset)
                if (start and tmi_sent_ts < start) or tmi_sent_ts > end:
                    continue

                yield msg

    def iterate_logs(self, channel: str, user: typing.Optional[str],
                     start: typing.Optional[datetime.datetime],
                     end: datetime.datetime, is_userid=False, stats: typing.Optional[Stats] = None):
        if user:
            return self.iterate_logs_for_user(channel, user, start, end, is_userid=is_userid, stats=stats)
        else:
            return self.iterate_logs_for_channel(channel, start, end, stats=stats)

    async def has_channel(self, channel: str):
        if not self.channels:
            await self._query_channels()
        for i in self.channels:
            if i.name == channel:
                return True
        return False

    async def _query_channels(self):
        log('warn', f'JustLog at {self.address}: query channels')
        try:
            async with aiohttp.request('get', self.address + f'/channels') as r:
                # r.raise_for_status()
                self.channels = [JustlogChannel(i['name'], i['userID']) for i in (await r.json()).get('channels', [])]
        except aiohttp.client_exceptions.ContentTypeError:
            self.channels = []
            log('warn', f'@{self.address}, You promised me JSON and sent XML.')


class JustlogChannel:
    name: str
    id: str

    def __init__(self, name, id_):
        self.name = name
        self.id = id_


async def fetch_and_convert_messages(url, params, stats: Stats) -> Generator[util_bot.StandardizedMessage, None, None]:
    async with aiohttp.request(
            'get',
            url,
            params=params,
            headers={
                'User-Agent': util_bot.USER_AGENT
            }
    ) as req:
        if req.status in (404, 500):
            return

        reader = req.content
        while not reader.at_eof():
            wait_start = time.monotonic()
            i = await reader.readline()
            wait_end = time.monotonic()
            stats.io_wait_time += wait_end - wait_start

            parse_start = time.monotonic()
            msg = twitchirc.auto_message(i.decode().rstrip('\n'), util_bot.bot)
            m, = twitch_client.convert_twitchirc_to_standarized([msg], util_bot.bot)
            parse_end = time.monotonic()
            stats.messages_processed += 1
            stats.parse_time += parse_end - parse_start

            if isinstance(m, StandardizedMessage):
                yield m  # other messages might not get built into StandardizedMessages
