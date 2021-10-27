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
import dataclasses
import datetime
import re
import shlex
import signal
import subprocess
import typing
from typing import List

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


@dataclasses.dataclass
class Stats:
    io_wait_time = 0
    parse_time = 0
    filter_time = 0
    messages_processed = 0


class JustgrepError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = errors

    def __repr__(self):
        return f'<Justgrep error: {", ".join(self.errors)}>'


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
            '[from:DATETIME to:DATETIME|lookback:DURATION] [to:DATETIME] [max:COUNT] '
            '[channel:USERNAME] [expire:DURATION]',
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

        if args['simple'] or args['text']:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'Log formats other than raw/logviewer have been removed since moving to justgrep. '
                    'I will reintroduce them later. - Mm2PL')

        if args['context']:
            args['before'] = args['context']
            args['after'] = args['context']

        if args['before'] or args['after']:
            return (util_bot.CommandResult.OTHER_FAILED,
                    'Context param has been removed since moving to justgrep. '
                    'I will reintroduce it later? - Mm2PL')
        users = []
        not_users = []
        if args.get('user'):
            for i in args['user'].lower().split(','):
                if i.startswith('!'):
                    not_users.append(i.lstrip('!'))
                else:
                    users.append(i)

        filter_task = asyncio.create_task(self._filter_messages(
            logger,
            channel=args['channel'],
            users=users,
            not_users=not_users,
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
                additional_message = ('Using local user filtering, because you used advanced user searching.'
                                      if len(users) > 1 or not_users else '')
                await util_bot.bot.send(msg.reply(f'@{msg.user}, Looks like this log fetch will take a while, '
                                                  f'do `_logs --cancel` to abort. '
                                                  f'Progress data unavailable. '
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
        hastebin_link = await self._hastebin_result(matched, args, datetime.datetime.utcnow() + args['expire'])
        if args['logviewer']:
            channel_id = list(filter(lambda o: o.name == args['channel'], logger.channels))[0].id
            link = f'https://logviewer.kotmisia.pl/?url=/h/{hastebin_link}&c={args["channel"]}&cid={channel_id}'
        else:
            link = f'{plugin_hastebin.hastebin_addr}raw/{hastebin_link}'
        return (util_bot.CommandResult.OK,
                f'@{msg.user}, Uploaded {len(matched)} filtered messages to hastebin: '
                f'{link}')

    async def _filter_messages(self, logger: 'JustLogApi', channel,
                               users: List[str], not_users: List[str],
                               regular_expr: typing.Pattern, start: datetime.datetime, end: datetime.datetime, count):
        DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
        if len(users) > 1 or not_users:
            not_user_arg = ()
            if not_users:
                not_user_arg = (
                    '-notuser', '|'.join(map(re.escape, not_users)),
                )
            user_arguments = (
                '-uregex',
                '-user', '|'.join(map(re.escape, users)),
                *not_user_arg
            )
        elif len(users) == 1:
            user_arguments = (
                '-user', users[0]
            )
        else:  # no users
            user_arguments = ()

        proc = await asyncio.create_subprocess_exec(
            'justgrep',
            shlex.join([
                '-channel', channel,
                '-start', start.strftime(DATE_FORMAT),
                '-end', end.strftime(DATE_FORMAT),
                '-url', logger.address,
                *user_arguments,
                '-regex', regular_expr.pattern,
                '-max', str(count)
            ]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            lines, stderr = (await proc.communicate())
            lines = lines.decode().split('\n')
            stderr = stderr.decode().split('\n')
            if len(stderr) and stderr[0]:
                raise JustgrepError(stderr)
        except asyncio.CancelledError:
            proc.send_signal(signal.SIGKILL)
            await proc.communicate()  # wait until it's ded
            raise
        return lines

    async def _hastebin_result(self, matched: List[StandardizedMessage], args, expire_on):
        output = self._convert_to_raw_irc(args, expire_on, matched)
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
            output += msg + '\r\n'
        return output


class JustLogApi:
    channels: List['JustlogChannel']

    def __init__(self, address: str):
        self.address = address
        self.channels = []

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
