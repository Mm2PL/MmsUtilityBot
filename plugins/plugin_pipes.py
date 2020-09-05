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
import time
import typing
from typing import Dict

import regex
from twitchirc import Event
import twitchirc

from plugins.utils import arg_parser
import util_bot as main

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
    pipe_locks: Dict[float, asyncio.Lock]

    def __init__(self, module, source):
        super().__init__(module, source)
        self.active_pipes = []
        self.pipe_responses = {

        }
        self.pipe_locks = {}
        self.command_pipe = main.bot.add_command('pipe')(self.command_pipe)
        main.bot.middleware.append(PipeMiddleware(self))
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

    @property
    def on_reload(self):
        return super().on_reload

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
            argv = arg_parser._split_args(main.delete_spammer_chrs(msg.text))
        except arg_parser.ParserError as e:
            return f'@{msg.user}, {e}'
        print(argv)
        if len(argv) < 3:
            return f'@{msg.user}, Usage: sub PATTERN REPLACEMENT TEXT...'
        try:
            pat = regex.compile(argv[1])
        except:
            return f'@{msg.user}, Invalid pattern.'
        new = argv[2]
        rest = ' '.join(argv[3:])
        try:
            return pat.sub(new, rest, timeout=0.1)
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
            self.pipe_locks[pipe_id] = asyncio.Lock()
            await self.pipe_locks[pipe_id].acquire()

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
                if command_name == handler.ef_command.rstrip(' '):
                    # noinspection PyProtectedMember
                    await main.bot._call_command(handler, new_msg)
                    was_handled = True
                    break

            if not was_handled:
                return f'@{msg.user}, [pipe] unknown command: {(cmd + " ").split(" ")[0]}.'
            await self.pipe_locks[pipe_id].acquire()
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

        if redir_target.startswith('/dev/ttyIRC'):
            channel = redir_target.replace('/dev/ttyIRC', '').lstrip('/')
            do_it_anyway = False
            if channel == '':
                return 1, is_a_directory
            if channel.endswith('_raw'):
                channel = channel[::-1].replace('_raw'[::-1], '', 1)[::-1]
                do_it_anyway = True

            if channel != '*' and (channel not in main.bot.channels_connected and not do_it_anyway):
                return 1, permission_denied + ' (cannot pipe into a channel that the bot is not in)'
            missing_perms = main.bot.check_permissions(new_msg, ['pipe.redirect.channel'], enable_local_bypass=False)
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
                    missing_perms = main.bot.check_permissions(new_msg, ['pipe.redirect.channel.all'],
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
        elif redir_target.startswith('/dev/ttyWS'):
            user = redir_target.replace('/dev/ttyWS', '')
            missing_perms = main.bot.check_permissions(new_msg, ['pipe.redirect.whispers'], enable_local_bypass=False)
            if missing_perms:
                return 1, permission_denied
            else:
                await main.bot.send(twitchirc.WhisperMessage(
                    flags={},
                    user_from=main.bot.username,
                    user_to=user,
                    text=pipe_info + response,
                    outgoing=True
                ))
            return 0, ''
        elif redir_target.startswith('/dev/ttyUSB'):
            return 1, permission_denied
        elif redir_target.startswith('/dev/supibot'):
            target = redir_target.replace('/dev/supibot', '')
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
        elif redir_target.startswith(('/dev/sd', '/dev/hd', '/dev/nvme', '/dev/mmcblk')):
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

    def send(self, event: Event) -> None:
        msg = event.data['message']
        if isinstance(msg, (PipeWhisperMessage, PipeMessage)):
            self.parent.pipe_responses[msg.pipe_id] = msg
            event.cancel()
            self.parent.pipe_locks[msg.pipe_id].release()
