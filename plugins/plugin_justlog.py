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
import datetime
import typing
import unicodedata
from typing import Dict, List, Union, Generator

import aiohttp
import regex

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


class Plugin(util_bot.Plugin):
    _current_log_fetch: typing.Optional[asyncio.Task]
    loggers: List['JustLogApi']

    def __init__(self, module, source):
        super().__init__(module, source)
        self.command_logs = util_bot.bot.add_command(
            'logs',
            enable_local_bypass=False,
            required_permissions=['util.logs'],
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
            'logs cancel',
            'Cancel a running log fetch. You cannot cancel another person\'s log fetch unless you have the '
            '`util.logs.cancel_other` permission.'
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

                    'cancel': bool
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

                    'cancel': False
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
        logger = await self._justlog_for_channel(args['channel'])
        if not logger:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'No matching JustLog instance found :(')
        if not args['regex']:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'Missing required argument "regex"')
        if args['lookback']:
            args['from'] = args['to'] - args['lookback']

        filter_task = asyncio.create_task(self._filter_messages(
            logger,
            channel=args['channel'],
            user=args['user'],
            regular_expr=args['regex'],
            start=args['from'],
            end=args['to'],
            count=args['max']
        ))
        self._current_log_fetch = asyncio.current_task()
        self._current_log_owner = msg.user
        try:
            try:
                matched = await asyncio.wait_for(asyncio.shield(filter_task), timeout=5)
            except asyncio.TimeoutError:
                await util_bot.bot.send(msg.reply(f'@{msg.user}, Looks like this log fetch will take a while, '
                                                  f'do `_logs --cancel` to abort.'))
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
        hastebin_link = await self._hastebin_result(matched, args, datetime.datetime.utcnow() + args['expire'])
        return (util_bot.CommandResult.OK,
                f'Uploaded {len(matched)} filtered messages to hastebin: '
                f'{plugin_hastebin.hastebin_addr}raw/{hastebin_link}')

    async def _filter_messages(self, logger: 'JustLogApi', channel, user, regular_expr: typing.Pattern, start, end,
                               count):
        matched = []
        is_userid = False
        if user and user.startswith('#'):
            user = user.lstrip('#')
            is_userid = True
        async for i in logger.iterate_logs(channel, user, start, end, is_userid=is_userid):
            if len(matched) >= count:
                break

            if regular_expr.search(i.text):
                matched.append(i)
        return matched

    def _convert_to_simple_text(self, matched: List[StandardizedMessage]) -> str:
        output = ''
        for msg in matched:
            dt = datetime.datetime.utcfromtimestamp(int(msg.flags["tmi-sent-ts"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            output += f'[{dt}] #{msg.channel} {msg.user}: {msg.text}\n'
        return output

    async def _hastebin_result(self, matched: List[StandardizedMessage], args, expire_on):
        if args['simple']:
            return await plugin_hastebin.upload(self._convert_to_simple_text(matched), expire_on)
        output = (f'# {"=" * 78}\n'
                  f'# Found {len(matched)} (out of maximum {args["max"]}) messages\n'
                  f'# Channel: #{args["channel"]},\n'
                  f'# User: {args["user"] or "[any]"}\n'
                  f'# Start date/time: {args["from"]},\n'
                  f'# End date/time: {args["to"]},\n'
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
        return await plugin_hastebin.upload(output, expire_on)

    def _pretty_badges(self, badges) -> str:
        return (
                ((unicodedata.lookup("CROSSED SWORDS") + " ") if "moderator/1" in badges else "")
                + ((unicodedata.lookup("GEM STONE") + " ") if "vip/1" in badges else "")
                + ((unicodedata.lookup("CINEMA") + " ") if "broadcaster/1" in badges else "")
                + ((unicodedata.lookup("WRENCH") + " ") if "staff/1" in badges else "")
        )


class JustLogApi:
    def __init__(self, address: str):
        self.address = address
        self.channels = []

    async def logs_for_user(self, channel: str, user: str,
                            year: typing.Optional[int] = None,
                            month: typing.Optional[int] = None,
                            reverse=False, is_userid: bool = False):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        date_frag = ''
        if year is not None and month is not None:
            date_frag = f'/{year}/{month}'

        params = {'json': '1'}
        if reverse:
            params['reverse'] = '1'

        log('warn', f'Fetch logs for {user}@#{channel} for {year} {month}')
        async with aiohttp.request(
                'get',
                self.address + f'/channel/{channel}/user{"id" if is_userid else ""}/{user}{date_frag}',
                params=params,
                headers={
                    'User-Agent': util_bot.USER_AGENT
                }
        ) as req:
            if req.status in (404, 500):
                return None
            json_resp: Dict[str, List[Dict[str, Union[str, int, Dict[str, str]]]]] = await req.json()
            raw_messages = json_resp.get('messages')
            return convert_messages(raw_messages)

    async def logs_for_channel(self, channel: str,
                               year: typing.Optional[int] = None,
                               month: typing.Optional[int] = None,
                               day: typing.Optional[int] = None,
                               reverse=False):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        date_frag = ''
        if year is not None and month is not None and day is not None:
            date_frag = f'/{year}/{month}/{day}'

        params = {'json': '1'}
        if reverse:
            params['reverse'] = '1'
        log('warn', f'JustLog at {self.address}: logs for channel {channel} at {date_frag}')
        async with aiohttp.request(
                'get',
                self.address + f'/channel/{channel}{date_frag}',
                params=params,
                headers={
                    'User-Agent': util_bot.USER_AGENT
                }
        ) as req:
            if req.status in (404, 500):
                return None
            json_resp: Dict[str, List[Dict[str, Union[str, int, Dict[str, str]]]]] = await req.json()
            raw_messages = json_resp.get('messages')
            return convert_messages(raw_messages)

    async def iterate_logs_for_user(self, channel: str, user: str,
                                    start: typing.Optional[datetime.datetime],
                                    end: datetime.datetime, is_userid=False):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        days = (end - start).days
        last_date = start
        utc_offset = datetime.datetime.now() - datetime.datetime.utcnow()
        for day in range(days, 0, -1):
            cdate = start + datetime.timedelta(days=day)
            if cdate.month != last_date.month or day == 0:
                last_date = cdate
                iterator = await self.logs_for_user(channel, user, year=cdate.year, month=cdate.month,
                                                    is_userid=is_userid)
                if iterator is None:
                    break
                for msg in iterator:
                    tmi_sent_ts = (datetime.datetime.fromtimestamp(int(msg.flags.get('tmi-sent-ts', 0)) / 1000)
                                   - utc_offset)
                    if (start and tmi_sent_ts < start) or tmi_sent_ts > end:
                        continue

                    yield msg

    async def iterate_logs_for_channel(self, channel: str,
                                       start: typing.Optional[datetime.datetime],
                                       end: datetime.datetime):
        if not await self.has_channel(channel):
            raise ValueError(f'Channel {channel!r} is not available on this JustLog instance')
        days = (end - start).days
        utc_offset = datetime.datetime.now() - datetime.datetime.utcnow()
        for day in range(days, 0, -1):
            cdate = start + datetime.timedelta(days=day)
            iterator = await self.logs_for_channel(channel, year=cdate.year, month=cdate.month, day=cdate.day)
            if iterator is None:
                break
            for msg in iterator:
                tmi_sent_ts = (datetime.datetime.fromtimestamp(int(msg.flags.get('tmi-sent-ts', 0)) / 1000)
                               - utc_offset)
                if (start and tmi_sent_ts < start) or tmi_sent_ts > end:
                    continue

                yield msg

    def iterate_logs(self, channel: str, user: typing.Optional[str],
                     start: typing.Optional[datetime.datetime],
                     end: datetime.datetime, is_userid=False):
        if user:
            return self.iterate_logs_for_user(channel, user, start, end, is_userid=is_userid)
        else:
            return self.iterate_logs_for_channel(channel, start, end)

    async def has_channel(self, channel: str):
        if not self.channels:
            await self._query_channels()
        return channel in self.channels

    async def _query_channels(self):
        log('warn', f'JustLog at {self.address}: query channels')
        async with aiohttp.request('get', self.address + f'/channels') as r:
            # r.raise_for_status()
            self.channels = [i['name'] for i in (await r.json()).get('channels', [])]


def convert_messages(raw_messages) -> Generator[util_bot.StandardizedMessage, None, None]:
    i = raw_messages.pop()
    while raw_messages:
        m = StandardizedMessage(
            text=i['text'],
            user=i['username'].lower(),
            channel=i['channel'].lower(),
            platform=util_bot.Platform.TWITCH,
            outgoing=False,
            parent=util_bot.bot
        )
        m.flags = i['tags']
        m.raw_data = i['raw']
        yield m
        i = raw_messages.pop()
