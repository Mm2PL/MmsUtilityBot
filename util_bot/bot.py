#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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
import inspect
import traceback
import typing
import warnings
from typing import Dict, Tuple

import twitchirc

import util_bot
from util_bot.clients.abstract_client import AbstractClient
from util_bot.clients.twitch import convert_twitchirc_to_standarized, TwitchClient
from util_bot.msg import StandardizedMessage, StandardizedWhisperMessage
from . import Platform
from .clients import CLIENTS
from .command import Command, CommandCooldown, CommandResult
from .utils import Reconnect, deprecated

bot_instance = None
RECONNECT = 'RECONNECT'


class Bot(twitchirc.Bot):
    prefixes: Dict[Tuple[str, Platform], str]

    @staticmethod
    def get():
        if bot_instance:
            return bot_instance
        else:
            raise RuntimeError('Bot has not been initialized yet')

    def __init__(self, storage=None):
        global bot_instance
        if bot_instance:
            raise RuntimeError('There cannot be more than one bot.')
        bot_instance = self

        self.clients: typing.Dict[Platform, typing.Union[AbstractClient, TwitchClient]] = {}
        self.middleware = []
        self.commands = []
        self.repeated_events = []
        self.recv_q = []
        self._username = ''
        super().__init__('localhost', 'xd', None, True, storage=storage, no_atexit=True, secure=False,
                         message_cooldown=0, no_connect=True)
        self.prefixes = {
            # ('name', Platform.TWITCH): 'prefix'
        }
        self.pubsub = None
        self.no_permissions_message_settings: Dict[Tuple[str, Platform], bool] = {}

    async def send(self, msg: StandardizedMessage, is_reconnect=False, **kwargs):
        o = await self.acall_middleware('send', dict(message=msg, queue=msg.channel), cancelable=True)
        if o is False:
            twitchirc.log('debug', str(msg), ': canceled')
            return

        if msg.platform in self.clients:
            try:
                await self.clients[msg.platform].send(msg)
            except Reconnect as e:
                await self.reconnect_client(e.platform)
                if is_reconnect:
                    raise RuntimeError('Failed to send message even after reconnect')
                return await self.send(msg, is_reconnect=True)
        else:
            raise RuntimeError(f'Cannot send message without a client being present for platform {msg.platform!r}')

    async def disconnect(self):
        await self.acall_middleware('disconnect', {}, False)
        for platform, client in self.clients.items():
            await client.disconnect()
        self.call_handlers('post_disconnect')

    def schedule_event(self, delay, priority, function, args, kwargs):
        return self.schedule_event_absolute(asyncio.get_event_loop().time() + delay, priority, function, args, kwargs)

    def schedule_event_absolute(self, when, priority, function, args, kwargs):
        return asyncio.get_event_loop().call_at(when, lambda: function(*args, **kwargs))

    def add_command(self, command: str, forced_prefix: typing.Optional[str] = None,
                    enable_local_bypass: bool = True,
                    required_permissions: typing.Optional[typing.List[str]] = None,
                    limit_to_channels: typing.Optional[typing.List[str]] = None,
                    available_in_whispers: bool = True,
                    cooldown: typing.Optional[CommandCooldown] = None):
        if required_permissions is None:
            required_permissions = []

        def decorator(func: typing.Callable) -> Command:
            cmd = Command(
                chat_command=command,
                function=func,
                parent=self,
                limit_to_channels=limit_to_channels,
                available_in_whispers=available_in_whispers
            )
            cmd.forced_prefix = forced_prefix
            cmd.enable_local_bypass = enable_local_bypass
            if cooldown:
                cmd.cooldown = cooldown

            cmd.permissions_required.extend(required_permissions)
            self.commands.append(cmd)
            self.call_middleware('add_command', (cmd,), cancelable=False)
            return cmd

        return decorator

    def call_middleware(self, action, arguments, cancelable) -> typing.Union[bool, typing.Tuple[bool, typing.Any]]:
        if cancelable:
            event = twitchirc.Event(action, arguments, source=self, cancelable=cancelable)
            canceler: typing.Optional[twitchirc.AbstractMiddleware] = None
            for m in self.middleware:
                if hasattr(m, 'aon_action'):
                    warnings.warn('Middleware has async on_action variant, but function was called from sync context')
                else:
                    m.on_action(event)
                if not canceler and event.canceled:
                    canceler = m
            if event.canceled:
                twitchirc.log('debug', f'Event {action!r} was canceled by {canceler.__class__.__name__}.')
                return False
            if event.result is not None:
                return True, event.result
            return True
        else:
            asyncio.get_event_loop().create_task(self.acall_middleware(action, arguments, cancelable))

    async def acall_middleware(self, action, arguments, cancelable) -> typing.Union[bool,
                                                                                    typing.Tuple[bool, typing.Any]]:
        """
        Call all middleware. Shamelessly taken from my IRC library.

        :param action: Action to run.
        :param arguments: Arguments to give, depends on which action you use, for more info see
        AbstractMiddleware.
        :param cancelable: Can the event be canceled?
        :return: False if the event was canceled, True otherwise.
        """
        event = twitchirc.Event(action, arguments, source=self, cancelable=cancelable)
        canceler: typing.Optional[twitchirc.AbstractMiddleware] = None
        for m in self.middleware:
            if hasattr(m, 'aon_action'):
                await m.aon_action(event)
            else:
                m.on_action(event)
            if not canceler and event.canceled:
                canceler = m
        if event.canceled:
            twitchirc.log('debug', f'Event {action!r} was canceled by {canceler.__class__.__name__}.')
            return False
        if event.result is not None:
            return True, event.result
        return True

    def schedule_repeated_event(self, delay, priority, function, args: tuple, kwargs: dict):
        async def event():
            while 1:
                if inspect.iscoroutinefunction(function):
                    await function(*args, **kwargs)
                else:
                    function(*args, **kwargs)

                await asyncio.sleep(delay)

        t = asyncio.get_event_loop().create_task(event())
        self.repeated_events.append(t)

        return t

    @deprecated('acheck_permissions')
    def check_permissions(self, message: twitchirc.ChannelMessage, permissions: typing.List[str],
                          enable_local_bypass=True):
        """
        Check if the user has the required permissions to run a command

        :param message: Message received.
        :param permissions: Permissions required.
        :param enable_local_bypass: If False this function will ignore the permissions \
        `twitchirc.bypass.permission.local.*`. This is useful when creating a command that can change global
        settings.
        :return: A list of missing permissions.

        NOTE `permission_error` handlers are called if this function would return a non-empty list.
        """
        o = self.call_middleware('permission_check', dict(user=message.user, permissions=permissions,
                                                          message=message, enable_local_bypass=enable_local_bypass),
                                 cancelable=True)
        if o is False:
            return ['impossible.event_canceled']

        if isinstance(o, tuple):
            return o[1]

        missing_permissions = []
        if message.user not in self.permissions:
            missing_permissions = permissions
        else:
            perms = self.permissions.get_permission_state(message)
            if twitchirc.GLOBAL_BYPASS_PERMISSION in perms or \
                    (enable_local_bypass
                     and twitchirc.LOCAL_BYPASS_PERMISSION_TEMPLATE.format(message.channel) in perms):
                return []
            for p in permissions:
                if p not in perms:
                    missing_permissions.append(p)
        if missing_permissions:
            self.call_handlers('permission_error', message, None, missing_permissions)
            self.call_middleware('permission_error', {'message': message, 'missing_permissions': missing_permissions},
                                 False)
        return missing_permissions

    async def acheck_permissions(self, message: twitchirc.ChannelMessage, permissions: typing.List[str],
                                 enable_local_bypass=True, disable_handlers=False):
        """
        Check if the user has the required permissions to run a command

        :param message: Message received.
        :param permissions: Permissions required.
        :param enable_local_bypass: If False this function will ignore the permissions \
        `twitchirc.bypass.permission.local.*`. This is useful when creating a command that can change global \
        settings.
        :param disable_handlers: Disables any events/handlers being fired, essentially hiding the call from other \
        machinery
        :return: A list of missing permissions.

        NOTE `permission_error` handlers are called if this function would return a non-empty list.
        """
        if not disable_handlers:
            o = await self.acall_middleware('permission_check', dict(user=message.user, permissions=permissions,
                                                                     message=message,
                                                                     enable_local_bypass=enable_local_bypass),
                                            cancelable=True)

            if o is False:
                return ['impossible.event_canceled']

            if isinstance(o, tuple):
                return o[1]

        missing_permissions = []
        if message.user not in self.permissions:
            missing_permissions = permissions
        else:
            perms = self.permissions.get_permission_state(message)
            if twitchirc.GLOBAL_BYPASS_PERMISSION in perms or \
                    (enable_local_bypass
                     and twitchirc.LOCAL_BYPASS_PERMISSION_TEMPLATE.format(message.channel) in perms):
                return []
            for p in permissions:
                if p not in perms:
                    missing_permissions.append(p)

        if missing_permissions and not disable_handlers:
            self.call_handlers('permission_error', message, None, missing_permissions)
            await self.acall_middleware(
                'permission_error',
                {
                    'message': message,
                    'missing_permissions': missing_permissions
                },
                False
            )
        return missing_permissions

    @deprecated('acheck_permissions_from_command')
    def check_permissions_from_command(self, message: twitchirc.ChannelMessage, command: twitchirc.Command):
        """
        Check if the user has the required permissions to run a command

        :param message: Message received.
        :param command: Command used.
        :return: A list of missing permissions.

        NOTE `permission_error` handlers are called if this function would return a non-empty list.
        """
        o = self.call_middleware('permission_check', dict(user=message.user, permissions=command.permissions_required,
                                                          message=message, command=command), cancelable=True)
        if o is False:
            return ['impossible.event_canceled']

        if isinstance(o, tuple):
            return o[1]

        missing_permissions = []
        if message.user not in self.permissions:
            missing_permissions = command.permissions_required
        else:
            perms = self.permissions.get_permission_state(message)
            if twitchirc.GLOBAL_BYPASS_PERMISSION in perms or \
                    (
                            command.enable_local_bypass
                            and (twitchirc.LOCAL_BYPASS_PERMISSION_TEMPLATE.format(message.channel) in perms)
                    ):
                return []
            for p in command.permissions_required:
                if p not in perms:
                    missing_permissions.append(p)
        if missing_permissions:
            self.call_handlers('permission_error', message, command, missing_permissions)
            self.call_middleware('permission_error', {'message': message, 'missing_permissions': missing_permissions},
                                 False)
        return missing_permissions

    async def acheck_permissions_from_command(self, message: twitchirc.ChannelMessage, command: twitchirc.Command):
        """
        Check if the user has the required permissions to run a command

        :param message: Message received.
        :param command: Command used.
        :return: A list of missing permissions.

        NOTE `permission_error` handlers are called if this function would return a non-empty list.
        """
        o = await self.acall_middleware(
            'permission_check',
            {
                'user': message.user, 'permissions': command.permissions_required,
                'message': message, 'command': command
            },
            cancelable=True
        )
        if o is False:
            return ['impossible.event_canceled']

        if isinstance(o, tuple):
            return o[1]

        missing_permissions = await self.acheck_permissions(message, command.permissions_required,
                                                            command.enable_local_bypass, True)

        if missing_permissions:
            self.call_handlers('permission_error', message, command, missing_permissions)
            await self.acall_middleware(
                'permission_error',
                {
                    'message': message,
                    'missing_permissions': missing_permissions,
                    'command': command
                },
                False
            )
        return missing_permissions

    async def _send_if_possible(self, message, source_message: StandardizedMessage):
        print('send if possible', message)
        if (isinstance(message, tuple) and len(message) == 2
                and isinstance(message[0], CommandResult)):
            no_perm_setting = self.no_permissions_message_settings.get(
                (source_message.channel, source_message.platform), False
            )
            if ((message[0] == CommandResult.NO_PERMISSIONS and no_perm_setting)
                    or message[0] != CommandResult.NO_PERMISSIONS):
                return await self._send_if_possible(message[1], source_message)

        elif isinstance(message, str):
            await self.send(source_message.reply(message))
        elif isinstance(message, (StandardizedMessage, StandardizedWhisperMessage)):
            await self.send(message)
        elif isinstance(message, twitchirc.ChannelMessage):
            await self._send_if_possible(convert_twitchirc_to_standarized([message], message_parent=self),
                                         source_message)
        elif isinstance(message, list):
            for item in message:
                await self._send_if_possible(item, source_message)

    def _call_command_handlers(self, message: twitchirc.ChannelMessage):
        raise NotImplementedError('sync function')

    async def _call_command(self, handler, message):
        o = await self.acall_middleware('command', {'message': message, 'command': handler}, cancelable=True)
        if o is False:
            return
        t = asyncio.create_task(handler.sacall(message))
        self._tasks.append({
            'task': t,
            'source_msg': message,
            'command': handler
        })

    async def _a_wait_for_tasks(self, timeout=0.2):
        if not self._tasks:
            return
        done, _ = await asyncio.wait({i['task'] for i in self._tasks}, timeout=timeout)
        for task in done:
            t = None
            for elem in self._tasks:
                if elem['task'] == task:
                    t = elem
                    break
            if t is not None:
                try:
                    result = await t['task']
                except BaseException as e:
                    for line in traceback.format_exc(1000).split('\n'):
                        twitchirc.log('warn', line)

                    if self.command_error_handler is not None:
                        if inspect.iscoroutinefunction(self.command_error_handler):
                            await self.command_error_handler(e, t['command'], t['source_msg'])
                        else:
                            self.command_error_handler(e, t['command'], t['source_msg'])
                    self._tasks.remove(t)
                    continue
                await self._send_if_possible(result, t['source_msg'])
                self._tasks.remove(t)

    async def _acall_command_handlers(self, message: typing.Union[StandardizedMessage, StandardizedWhisperMessage]):
        """Handle commands."""

        prefix = self.get_prefix(message.channel, message.platform, message)
        # print(prefix, message.text.startswith(prefix))

        if message.text.startswith(prefix):
            was_handled = False
            if ' ' not in message.text:
                message.text += ' '
            for handler in self.commands:
                handler: Command
                if handler.matcher_function(message, prefix):
                    await self._call_command(handler, message)
                    was_handled = True
                    break
            if not was_handled:
                self._do_unknown_command(message)
        else:
            await self._acall_forced_prefix_commands(message)

    def _call_forced_prefix_commands(self, message):
        raise NotImplementedError('sync function')

    async def _acall_forced_prefix_commands(self, message):
        for handler in self.commands:
            if handler.forced_prefix is None:
                continue
            elif message.text.startswith(handler.ef_command):
                await self._call_command(handler, message)
                return True
        return False

    def _do_unknown_command(self, message):
        """Handle unknown commands."""
        if self.on_unknown_command == 'warn':
            twitchirc.warn(f'Unknown command {message!r}')
        elif self.on_unknown_command == 'chat_message':
            msg = message.reply(f'Unknown command {message.text.split(" ", 1)[0]!r}')
            self.send(msg)
        elif self.on_unknown_command == 'ignore':
            # Just ignore it.
            pass
        else:
            raise Exception('Invalid handler in `on_unknown_command`. Valid options: warn, chat_message, '
                            'ignore.')

    async def arun(self):
        """
        This is a coroutine version of :py:meth:`run`.

        Connect to the server if not already connected. Process messages received.
        This function includes an interrupt handler that automatically calls :py:meth:`stop`.

        :return: nothing.
        """
        try:
            await self._arun()
        except KeyboardInterrupt:
            print('arun Got SIGINT, exiting.')
            await self.stop()
            return

    def run(self):
        raise NotImplementedError('sync function')

    async def _run_scheduler(self):
        while 1:
            self.scheduler.run(blocking=False)
            await asyncio.sleep(1)

    async def _platform_message_flush_loop(self, platform):
        while 1:
            await self.clients[platform].flush_queues()
            await asyncio.sleep(1)

    async def _platform_recv_loop(self, platform):
        while 1:
            # print(f'Wait for {platform!s} to recv')
            try:
                msgs = await self.clients[platform].receive()
            except Reconnect:
                pre_reconnect = 0.5
                print(f'Waiting for {pre_reconnect}s before reconnecting to {platform!s}...')
                await asyncio.sleep(pre_reconnect)
                print(f'Reconnecting to {platform!s}...')
                await self.reconnect_client(platform)
                print(f'Reconnected to {platform!s}...')
                continue

            # print(f'Done waiting for {platform!s} to recv')
            for i in msgs:
                if util_bot.debug:
                    twitchirc.log('debug', str(i))
                self.call_handlers('any_msg', i)
                if isinstance(i, twitchirc.PingMessage):
                    await self.clients[Platform.TWITCH].send(i.reply())
                elif isinstance(i, twitchirc.ReconnectMessage):
                    await self.reconnect_client(Platform.TWITCH)
                elif isinstance(i, StandardizedMessage):
                    self.call_handlers('chat_msg', i)
                    await self._acall_command_handlers(i)
                elif isinstance(i, StandardizedWhisperMessage):
                    print('whisper', i)
                    await self._acall_command_handlers(i)
                await self.flush_queue(3)

    async def _command_task_awaiter(self):
        while 1:
            if self._tasks:
                await self._a_wait_for_tasks(10)
            else:
                await asyncio.sleep(0.1)

    async def _arun(self):
        """
        Brains behind :py:meth:`run`. Doesn't include the `KeyboardInterrupt` handler.

        :return: nothing.
        """
        self.hold_send = False
        self._load_prefixes()
        self.call_handlers('start')
        scheduler_task = asyncio.create_task(self._run_scheduler())
        awaiter_task = asyncio.create_task(self._command_task_awaiter())
        platform_recv_tasks = [self._platform_recv_loop(platform) for platform in list(Platform)]
        platform_flush_tasks = [self._platform_message_flush_loop(platform) for platform in list(Platform)]
        await asyncio.wait((scheduler_task, *platform_recv_tasks, *platform_flush_tasks, awaiter_task),
                           return_when=asyncio.FIRST_COMPLETED)
        await self.disconnect()

    def _run(self):
        raise NotImplementedError('sync function')

    def call_handlers(self, event, *args):
        """
        Call handlers for `event`

        :param event: The event that happened. See `handlers`
        :param args: Arguments to give to the handler.

        :return: nothing.
        """
        if event not in ['any_msg', 'chat_msg']:
            twitchirc.log('debug', f'Calling handlers for event {event!r} with args {args!r}')
        for h in self.handlers[event]:
            h(event, *args)

    async def stop(self):
        """
        Stop the bot and disconnect.
        This function force saves the `storage` and disconnects using :py:meth:`disconnect`

        :return: nothing.
        """
        self.call_handlers('pre_save')
        self.storage.save(is_auto_save=False)
        self.call_handlers('post_save')
        await self.disconnect()
        self.storage['prefixes'] = self._serialize_prefixes(self.prefixes)

    def moderate(self, channel: str, user: typing.Optional[str] = None, message_id: typing.Optional[str] = None):
        """
        Construct a ModerationContainer targeting the channel, and optionally a user and message.

        :return: Newly created ModerationContainer
        """
        warnings.warn('Assuming platform is Twitch!!!!')
        return twitchirc.ModerationContainer(message_id, user, channel, parent=self)

    async def join(self, channel, platform=Platform.TWITCH):
        """
        Join a channel.

        :param platform: Platform to send this on, depending on this your call maybe ignored by the underlying \
        platform implementation.
        :param channel: Channel you want to join.
        :return: nothing.
        """
        channel = channel.lower().strip('#')

        o = await self.acall_middleware('join', dict(channel=channel), True)
        if o is False:
            return
        await self.clients[platform].join(channel)
        if channel not in self.channels_connected:
            self.channels_connected.append(channel)

    async def part(self, channel, platform=Platform.TWITCH):
        """
        Leave a channel

        :param platform: Platform to send this on, depending on this your call maybe ignored by the underlying \
        platform implementation.
        :param channel: Channel you want to leave.
        :return: nothing.
        """
        channel = channel.lower().strip('#')

        o = await self.acall_middleware('part', dict(channel=channel), cancelable=True)
        if o is False:
            return
        await self.clients[platform].part(channel)

        while channel in self.channels_connected:
            self.channels_connected.remove(channel)

    def twitch_mode(self):
        self.cap_reqs(True)

    def cap_reqs(self, use_membership=True):
        """
        Send CAP REQs.

        :param use_membership: Send the membership capability.
        :return: nothing.
        """
        twitchirc.log('debug', f'Sending CAP REQs. Membership: {use_membership}')
        # await self.force_send(f'CAP REQ :twitch.tv/commands twitch.tv/tags'
        #                       f'{" twitch.tv/membership" if use_membership else ""}\r\n')
        self.clients[Platform.TWITCH].connection.cap_reqs(use_membership)

    def connect(self, username, password: typing.Union[str, None] = None) -> None:
        warnings.warn('Initialize using coroutine.')

    def force_send(self, message):
        return self.send(message)

    def flush_single_queue(self, queue, no_cooldown=False, max_messages=1, now=None):
        return

    async def flush_queue(self, max_messages: int = 1):
        for client in self.clients.values():
            await client.flush_queues()

    def process_messages(self, max_messages: int = 1, mode=-1):
        q = self.recv_q.copy()
        self.recv_q.clear()
        return q

    def clone(self):
        return self.clients[Platform.TWITCH].connection.clone()

    def clone_and_send_batch(self, message_batch: typing.List[typing.Union[str, twitchirc.ChannelMessage]]):
        return self.clients[Platform.TWITCH].connection.clone_and_send_batch(message_batch)

    def run_commands_from_file(self, file_object):
        raise NotImplementedError('xd')

    def _login(self, username, password: typing.Union[str, None] = None):
        raise NotImplementedError('xd')

    def _connect(self):
        raise NotImplementedError('xd')

    def _send(self, message: bytes):
        raise NotImplementedError('xd')

    def _remove_parted_channels(self):
        raise NotImplementedError('xd')

    async def _run_once(self):
        raise NotImplementedError('Replaced with loops for each platform.')

    async def aconnect(self):
        for p, client in self.clients.items():
            print(f'Connecting to {p.name}')
            await client.connect()
        await self.acall_middleware('connect', {}, False)

    async def init_clients(self, auths: typing.Dict[Platform, typing.Any]):
        for plat, auth in auths.items():
            if plat not in CLIENTS:
                raise RuntimeError(f'Got authentication for platform without a client: {plat!r}')
            c_class = CLIENTS[plat]
            self.clients[plat] = c_class(auth)

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    async def reconnect_client(self, platform):
        await self.clients[platform].reconnect()

    def _deserialize_prefixes(self, data) -> typing.Dict[typing.Tuple[str, Platform], str]:
        output = {}
        if isinstance(data, dict):  # plugin_prefixes data
            for k, v in data.items():
                output[(k, Platform.TWITCH)] = v
            return output
        elif isinstance(data, list):
            for v in data:
                chan, prefix = v['channel'], v['prefix']
                if 'name' in chan:
                    platform, name = chan['platform'], chan['name']

                    output[(name, Platform[platform])] = prefix
                else:
                    platform = chan['platform']
                    output[Platform[platform]] = prefix
            return output
        else:
            raise TypeError(f'Unable to deserialize prefixes from type {type(data)!r}')

    def _serialize_prefixes(self, data: dict) -> typing.List[typing.Dict[str, str]]:
        output = []
        for k, v in data.items():
            if isinstance(k, Platform):
                output.append({
                    'channel': {
                        'platform': k.name
                    },
                    'prefix': v
                })
            else:
                output.append({
                    'channel': {
                        'name': k[0],
                        'platform': k[1].name
                    },
                    'prefix': v
                })
        return output

    def _load_prefixes(self):
        if self.storage:
            if 'prefixes' in self.storage.data:
                self.prefixes = self._deserialize_prefixes(self.storage['prefixes'])
            elif 'plugin_prefixes' in self.storage.data and 'prefixes' in self.storage['plugin_prefixes']:
                self.prefixes = self._deserialize_prefixes(self.storage.data['plugin_prefixes']['prefixes'])
            else:
                self.prefixes = {}

    def _save_prefixes(self):
        if self.storage:
            self.storage['prefixes'] = self._serialize_prefixes(self.prefix)
            del self.storage.data['plugin_prefixes']

    def get_prefix(self, channel_name, platform, msg: typing.Union[None, StandardizedMessage,
                                                                   StandardizedWhisperMessage] = None):
        if msg is not None:
            if platform == Platform.DISCORD and isinstance(msg, StandardizedMessage):
                guild_id = 'guild.' + str(msg.source_message.channel.guild.id)
                if (guild_id, Platform.DISCORD) in self.prefixes:
                    return self.prefixes[(guild_id, Platform.DISCORD)]

        channel_ident = (channel_name, platform)
        if channel_ident in self.prefixes:
            return self.prefixes[channel_ident]
        elif platform in self.prefixes:
            return self.prefixes[platform]
        else:
            return self.prefix
