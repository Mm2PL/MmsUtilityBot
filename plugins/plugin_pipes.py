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
import copy
import time
import typing
from typing import Dict

import regex
from twitchirc import Event
import twitchirc

from plugins.utils import arg_parser
import util_bot as main
from util_bot.clients.twitch import convert_twitchirc_to_standarized

NAME = 'pipes'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class PipeWhisperMessage(main.StandardizedWhisperMessage):

    def __init__(self, user_from, user_to, text, platform, flags, outgoing=False, pipe_id=None):
        super().__init__(
            user_from=user_from,
            user_to=user_to,
            text=text,
            platform=platform,
            flags=flags,
            outgoing=outgoing,
        )
        self.pipe_id = pipe_id

    def reply(self, text: str):
        new = PipeWhisperMessage(
            user_from='OUTGOING',
            user_to=self.user_from,
            text=text,
            platform=self.platform,
            flags={},
            outgoing=True,
            pipe_id=self.pipe_id
        )
        return new


class PipeMessage(main.StandardizedMessage):
    def __init__(self, text: str, user: str, channel: str, platform, outgoing=False, parent=None, pipe_id=None):
        super().__init__(
            text=text,
            user=user,
            channel=channel,
            platform=platform,
            outgoing=outgoing,
            parent=parent
        )
        self.pipe_id = pipe_id

    def reply(self, text: str, force_slash=False):
        return PipeMessage(text=text, user='OUTGOING', channel=self.channel, platform=self.platform,
                           outgoing=True, parent=self.parent, pipe_id=self.pipe_id)

    def reply_directly(self, text: str):
        new = PipeWhisperMessage(
            user_from='OUTGOING',
            user_to=self.user,
            text=text,
            platform=self.platform,
            flags={},
            outgoing=True,
            pipe_id=self.pipe_id
        )
        return new


class Plugin(main.Plugin):

    def __init__(self, module, source):
        super().__init__(module, source)
        self.active_pipes = []
        self.pipe_responses = {

        }
        self.command_pipe = main.bot.add_command('pipe')(self.command_pipe)

        self.middleware = PipeMiddleware(self)
        main.bot.middleware.append(self.middleware)

        self.command_replace = main.bot.add_command('replace')(self.command_replace)
        self.command_regex_replace = main.bot.add_command('sub')(self.command_regex_replace)
        self.command_reverse = main.bot.add_command('reverse')(self.command_reverse)

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    def on_reload(self):
        main.bot.middleware.remove(self.middleware)

    async def command_reverse(self, msg: main.StandardizedMessage):
        return ''.join(reversed((msg.text + ' ').split(' ', 1)[1]))

    async def command_replace(self, msg: main.StandardizedMessage):
        try:
            # noinspection PyProtectedMember
            argv = arg_parser._split_args(main.delete_spammer_chrs(msg.text))
        except arg_parser.ParserError as e:
            return f'@{msg.user}, {e}'
        print(argv)
        if len(argv) < 3:
            return f'@{msg.user}, Usage: replace OLD NEW TEXT...'
        old = argv[1]
        new = argv[2]
        rest = ' '.join(argv[3:])
        return rest.replace(old, new)

    async def command_regex_replace(self, msg: main.StandardizedMessage):
        try:
            # noinspection PyProtectedMember
            argv = arg_parser._split_args(main.delete_spammer_chrs(msg.text), strict_escapes=False)
        except arg_parser.ParserError as e:
            return f'@{msg.user}, {e}'
        print(argv)
        if len(argv) < 3:
            return f'@{msg.user}, Usage: sub PATTERN REPLACEMENT TEXT...'
        pattern = argv[1]
        if pattern.startswith('/') and pattern.count('/') >= 2:
            pattern = pattern.lstrip('/')
            flags, p = pattern[::-1].split('/', 1)

            pattern = f'(?{flags}){p[::-1]}'

        try:
            pat = regex.compile(pattern)
        except:
            return f'@{msg.user}, Invalid pattern.'
        new = argv[2]
        rest = ' '.join(argv[3:])
        try:
            return pat.sub(new, rest, timeout=0.5)
        except TimeoutError:
            return f'@{msg.user}, Replacement timed out.'

    async def command_pipe(self, msg: main.StandardizedMessage):
        sub_commands = PIPE_REGEX.split(msg.text)
        sub_commands[0] = sub_commands[0].split(' ', 1)[1]
        print(sub_commands)
        buf = ''
        for cmd in sub_commands:
            print('processing command', cmd)
            pipe_id = time.time()
            self.active_pipes.append(pipe_id)
            new_msg = PipeMessage(
                text=cmd + ' ' + buf,
                user=msg.user,
                channel=msg.channel,
                platform=msg.platform,
                outgoing=False,
                parent=msg.parent,
                pipe_id=pipe_id
            )
            new_msg.flags = msg.flags

            was_handled = False
            redirection = REDIRECTION_REGEX.match(new_msg.text)
            if redirection:
                new_msg.text = redirection.group('command').rstrip(' ')
                redir_target = redirection.group('target').rstrip(' ')
            else:
                redir_target = None

            if ' ' not in new_msg.text:
                new_msg.text += ' '

            command_name = new_msg.text.split(' ', 1)[0]
            for handler in main.bot.commands:
                if handler.limit_to_channels is not None and new_msg.channel not in handler.limit_to_channels:
                    continue

                if command_name == handler.ef_command.rstrip(' '):
                    o = await main.bot.acall_middleware('command', {'message': new_msg, 'command': handler},
                                                        cancelable=True)
                    if o is False:
                        return (f'@{msg.user}, [pipe] command: {handler.chat_command!r} was canceled in the middle of '
                                f'executing your pipe')

                    command_output = await handler.acall(new_msg)
                    if isinstance(command_output, str):
                        command_output = new_msg.reply(command_output)
                    elif isinstance(command_output, twitchirc.ChannelMessage):
                        command_output = convert_twitchirc_to_standarized([command_output], main.bot)[0]
                    else:
                        return f'@{msg.user}, [PIPE] Command {(cmd + " ").split(" ")[0]} returned nothing.'

                    self.pipe_responses[pipe_id] = command_output
                    was_handled = True
                    break

            if not was_handled:
                return f'@{msg.user}, [pipe] unknown command: {(cmd + " ").split(" ")[0]}.'
            if pipe_id in self.pipe_responses and self.pipe_responses[pipe_id]:
                if redir_target is not None:
                    exit_code, output = await self._process_redirection(redir_target, new_msg,
                                                                        self.pipe_responses[pipe_id].text)
                    if exit_code != 0:
                        return f'@{msg.user}, {output}'
                    else:
                        buf = output
                else:
                    buf = self.pipe_responses[pipe_id].text
            else:
                return f'@{msg.user}, [PIPE] Command {(cmd + " ").split(" ")[0]} returned nothing.'

            del self.pipe_responses[pipe_id]
            self.active_pipes.remove(pipe_id)
        return buf if buf else None  # prevent sending empty messages

    def _multi_in(self, arg_1, arg_2):
        for i in arg_1:
            if i in arg_2:
                return True
        return False

    async def _process_redirection(self, redir_target: str, new_msg: PipeMessage, response: str):
        permission_denied = f'pipe: {redir_target}: Permission denied'
        is_a_directory = f'pipe: {redir_target}: Is a directory'
        no_such_file_or_dir = f'pipe: {redir_target}: No such file or directory'

        pipe_info = f'[pipe from {new_msg.user}] '
        if self._multi_in(('yourmom', 'your_mom', 'your mom'), redir_target):
            return 1, 'No u'
        if not redir_target.startswith('/dev/'):
            return 1, permission_denied

        if redir_target == '/dev/null':
            return 0, ''
        redir_target = redir_target.replace('/dev/', '')
        if redir_target.startswith('ttyIRC') or redir_target.startswith('#'):
            channel = redir_target.replace('ttyIRC', '').lstrip('/#')
            do_it_anyway = False
            if channel == '':
                return 1, is_a_directory
            if channel.endswith('_raw'):
                channel = channel[::-1].replace('_raw'[::-1], '', 1)[::-1]
                do_it_anyway = True

            if channel != '*' and (channel not in main.bot.channels_connected and not do_it_anyway):
                return 1, permission_denied + ' (cannot pipe into a channel that the bot is not in)'
            missing_perms = await main.bot.acheck_permissions(new_msg, ['pipe.redirect.channel'],
                                                              enable_local_bypass=False)
            if missing_perms:
                return 1, permission_denied
            else:
                if channel != '*':
                    await main.bot.send(main.StandardizedMessage(
                        text=response,
                        user='OUTGOING',
                        channel=channel,
                        outgoing=True,
                        parent=main.bot,
                        platform=main.Platform.TWITCH
                    ))
                else:
                    missing_perms = await main.bot.acheck_permissions(new_msg, ['pipe.redirect.channel.all'],
                                                                      enable_local_bypass=False)
                    if missing_perms:
                        return 1, permission_denied

                    for i in main.bot.channels_connected:
                        await main.bot.send(main.StandardizedMessage(
                            text=pipe_info + response,
                            user='OUTGOING',
                            channel=i,
                            outgoing=True,
                            parent=main.bot,
                            platform=main.Platform.TWITCH
                        ))
            return 0, ''
        elif redir_target.startswith('ttyWS'):
            user = redir_target.replace('ttyWS', '')
            missing_perms = await main.bot.acheck_permissions(new_msg, ['pipe.redirect.whispers'],
                                                              enable_local_bypass=False)
            if missing_perms:
                return 1, permission_denied
            else:
                await main.bot.send(main.StandardizedWhisperMessage(
                    flags={},
                    user_from=main.bot.username,
                    user_to=user,
                    text=pipe_info + response,
                    outgoing=True,
                    source_message=new_msg,
                    platform=new_msg.platform
                ))
            return 0, ''
        elif redir_target.startswith('ttyUSB'):
            return 1, permission_denied
        elif redir_target.startswith('supibot'):
            target = redir_target.replace('supibot', '')
            if target in ['', '/']:
                return 1, is_a_directory
            elif target.startswith('/remind/'):
                user = target.replace('/remind/', '')
                try:
                    id_ = await main.supibot_api.create_reminder(user, pipe_info + response)
                    return 0, id_
                except main.ApiError as error:
                    # EX_UNAVAILABLE
                    return 69, f'API Error: {error.message}'
            elif target.rstrip('/') == '/remind':
                return 1, is_a_directory
            else:
                return 1, permission_denied
        elif redir_target.startswith(('sd', 'hd', 'nvme', 'mmcblk')):
            return 1, f'{permission_denied}. Why do you think writing to my drives is a good idea?'
        else:
            # bad path
            if '/' in redir_target.replace('/dev/', ''):
                return 1, no_such_file_or_dir
            else:
                return 1, permission_denied


PIPE_REGEX = regex.compile(r'(?V1)\s?[^\\]\|\s?')
REDIRECTION_REGEX = regex.compile(r'(?V1)(?P<command>.+)\s?>>?\s?(?P<target>.+)')


class PipeMiddleware(twitchirc.AbstractMiddleware):

    def __init__(self, parent):
        super().__init__()
        self.parent: Plugin = parent

    async def aon_action(self, event: Event) -> None:
        if event.name == 'command':
            await self.acommand(event)

    async def acommand(self, event: Event) -> None:
        message: typing.Union[main.StandardizedMessage, typing.Any] = event.data.get('message')
        command: twitchirc.Command = event.data.get('command')
        if command.forced_prefix or command.matcher_function:
            return

        if isinstance(message, main.StandardizedMessage):  # has to be a message from the user
            if '|' in message.text or '>' in message.text:  # implicit pipe invocation
                event.cancel()
                msg2 = copy.copy(message)
                prefix = main.bot.get_prefix(message.channel, message.platform, message)
                msg2.text = f'{prefix}pipe {msg2.text.replace(prefix, "", 1)}'
                print(f'implicit pipe text {msg2.text}')
                output = await self.parent.command_pipe.acall(msg2)
                print(output)
                await main.bot._send_if_possible(output, message)
