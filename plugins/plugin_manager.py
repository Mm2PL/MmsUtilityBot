#  This is a simple utility bot
#  Copyright (C) 2019 Maciej Marciniak
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
import enum
import json
import traceback
import typing
from typing import Dict, Any

import sqlalchemy
import twitchirc
from sqlalchemy import orm
from sqlalchemy.orm import relationship

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()

__meta_data__ = {
    'name': 'plugin_manager',
    'commands': [],
    'no_reload': True
}

log = main.make_log_function('plugin_manager')

# noinspection PyProtectedMember
call_command_handlers = main.bot._call_command_handlers

# map of command name and blacklisted channels.
blacklist: typing.Dict[
    str, typing.List[str]
] = {}
error_notification_channel = main.bot.username.lower()


def _call_handler(command, message):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_acall_handler(command, message))


async def _acall_handler(command, message):
    if message.channel in blacklist and command.chat_command in blacklist[message.channel]:
        # command is blocked in this channel.
        log('info', f'User {message.user} attempted to call command {command.chat_command} in channel '
                    f'{message.channel} where it is blacklisted.')
        return
    try:
        await main.bot._call_command(command, message)
    except Exception as e:
        msg = twitchirc.ChannelMessage(
            text=f'Errors monkaS {chr(128073)} ALERT: {e!r}',
            user='TO_BE_SENT',
            channel=error_notification_channel
        )
        msg.outgoing = True
        main.bot.force_send(msg)
        log('err', f'Error while running command {command.chat_command}')
        for i in traceback.format_exc(30).split('\n'):
            log('err', i)


# noinspection PyProtectedMember
async def _acall_command_handlers(message: twitchirc.ChannelMessage):
    """Handle commands."""
    if message.text.startswith(main.bot.prefix):
        was_handled = False
        if ' ' not in message.text:
            message.text += ' '
        for handler in main.bot.commands:
            if callable(handler.matcher_function) and handler.matcher_function(message, handler):
                await _acall_handler(handler, message)
                was_handled = True
            if message.text.startswith(main.bot.prefix + handler.ef_command):
                await _acall_handler(handler, message)
                was_handled = True

        if not was_handled:
            main.bot._do_unknown_command(message)
    else:
        main.bot._call_forced_prefix_commands(message)


def add_conditional_alias(alias: str, condition: typing.Callable[[twitchirc.Command, twitchirc.ChannelMessage], bool]):
    def decorator(command: twitchirc.Command):
        @main.bot.add_command(alias, enable_local_bypass=command.enable_local_bypass,
                              required_permissions=command.permissions_required)
        async def new_command(msg: twitchirc.ChannelMessage):
            if condition(command, msg):
                return await command.acall(msg)

        return command

    return decorator


channel_settings: Dict[str, Any] = {}


class ChannelSettings(main.Base):
    __tablename__ = 'channelsettings'

    channel_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'), primary_key=True)
    channel = relationship('User')
    settings_raw = sqlalchemy.Column(sqlalchemy.Text)

    @orm.reconstructor
    def _reconstructor(self):
        self._import()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings = {}
        self._export()

    @staticmethod
    def _load_all(session):
        return session.query(ChannelSettings).all()

    @staticmethod
    def load_all(session=None):
        if session is None:
            with main.session_scope() as s:
                return ChannelSettings._load_all(s)
        else:
            return ChannelSettings._load_all(session)

    def _import(self):
        self._settings = json.loads(self.settings_raw)

    def _export(self):
        self.settings_raw = json.dumps(self._settings)

    def fill_defaults(self):
        for k in all_settings.keys():
            self.set(k, Setting.find(k).default_value)

    def update(self):
        self._export()

    def get(self, setting_name) -> typing.Any:
        setting = Setting.find(setting_name)
        if self.channel_alias is not None and setting.scope == SettingScope.GLOBAL:
            raise RuntimeError(f'Setting {setting_name!r} is global, it cannot be changed per channel.')

        if setting_name in self._settings:
            return self._settings[setting_name]
        else:
            return setting.default_value

    def set(self, setting_name, value) -> None:
        setting = Setting.find(setting_name)
        if self.channel_alias != -1 and setting.scope == SettingScope.GLOBAL:
            raise RuntimeError(f'Setting {setting_name!r} is global, it cannot be changed per channel.')

        self._settings[setting_name] = value


channel_settings_session = None


def _init_settings():
    global channel_settings_session

    channel_settings_session = main.Session()
    channel_settings_session.flush = lambda *a, **kw: print('CS: Flushing a readonly session.')
    print('Load channel settings.')
    with main.session_scope() as write_session:
        print('Loading existing channel settings...')
        for i in ChannelSettings.load_all(write_session):
            if i.channel_alias == -1:  # global settings.
                channel_settings[SettingScope.GLOBAL.name] = i
            else:
                channel_settings[i.channel.last_known_username] = i
        print('OK')
        print('Creating missing channel settings...')
        for j in main.bot.channels_connected + [SettingScope.GLOBAL.name]:
            if j in channel_settings:
                continue
            cs = ChannelSettings()
            if j == SettingScope.GLOBAL.name:
                cs.channel_alias = -1
                write_session.add(cs)
                continue

            channels = main.User.get_by_name(j.lower(), write_session)
            if len(channels) != 1:
                continue
            cs.channel = channels[0]
            write_session.add(cs)
            channel_settings[channels[0].last_known_username] = cs
        print('OK')
        print('Commit.')

    print(f'Done. Loaded {len(channel_settings)} channel settings entries.')


main.bot.schedule_event(0.1, 100, _init_settings, (), {})


def _reload_settings():
    global channel_settings
    channel_settings = {}
    _init_settings()
    return 'OK'


main.reloadables['channel_settings'] = _reload_settings


class SettingScope(enum.Enum):
    PER_CHANNEL = 0
    GLOBAL = 1


all_settings = {}


class Setting:
    default_value: typing.Any
    name: str
    scope: SettingScope

    def __init__(self, owner: main.Plugin, name: str, default_value=..., scope=SettingScope.PER_CHANNEL):
        self.owner = owner
        self.name = name
        self.default_value = default_value
        self.scope = scope
        self.register()

    @staticmethod
    def find(name: str):
        if name in all_settings:
            return all_settings[name]
        else:
            raise KeyError(f'Cannot find setting {name}, did you misspell the name or is the plugin that adds it not '
                           f'loaded?')

    def register(self):
        if self.name not in all_settings:
            all_settings[self.name] = self
        else:
            raise KeyError(f'Refusing to override setting {all_settings[self.name]} with {self}.')

    def unregister(self):
        if self.name in all_settings:
            if all_settings[self.name] != self:
                raise KeyError(f'Refusing to unregister unrelated setting {all_settings[self.name]}. (as {self})')
            del all_settings[self.name]
        else:
            raise KeyError(f'Setting {self} is not registered.')

    def __repr__(self):
        return f'<Setting {self.name} from plugin {self.owner.name}, scope: {self.scope.name}>'


# command definitions

@main.bot.add_command('mb.unblacklist_command', required_permissions=['util.unblacklist_command'],
                      enable_local_bypass=True)
def command_unblacklist(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        main.bot.send(msg.reply(f'@{msg.user} Usage: '
                                f'"{main.bot.prefix}{command_unblacklist.chat_command} COMMAND". '
                                f'Where COMMAND is the command you want to unblacklist.'))
        return
    target = args[1]
    for i in main.bot.commands:
        if i.chat_command == target:
            if target not in blacklist[msg.channel]:
                main.bot.send(msg.reply(f"@{msg.user} Cannot unblacklist command {target} that isn't blacklisted "
                                        f"here."))
                return
            blacklist[msg.channel].remove(target)
            main.bot.send(msg.reply(f'@{msg.user} Unblacklisted command {target} from channel #{msg.channel}.'))
            return
    main.bot.send(msg.reply(f'@{msg.user} Cannot unblacklist nonexistent command {target}.'))


@main.bot.add_command('mb.blacklist_command', required_permissions=['util.blacklist_command'], enable_local_bypass=True)
def command_blacklist(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        main.bot.send(msg.reply(f'@{msg.user} Usage: '
                                f'"{main.bot.prefix}{command_blacklist.chat_command} COMMAND". '
                                f'Where COMMAND is the command you want to blacklist.'))
        return
    target = args[1]
    if target in blacklist[msg.channel]:
        main.bot.send(msg.reply(f'@{msg.user} That command is already blacklisted.'))
        return

    for i in main.bot.commands:
        if i.chat_command == target:
            blacklist[msg.channel].append(target)
            main.bot.send(msg.reply(f'@{msg.user} Blacklisted command {target}. '
                                    f'To undo use {main.bot.prefix}{command_unblacklist.chat_command} {target}.'))
            return
    main.bot.send(msg.reply(f'@{msg.user} Cannot blacklist nonexistent command {target}.'))
    return


@main.bot.add_command('mb.list_blacklisted_commands', required_permissions=['util.blacklist_command'],
                      enable_local_bypass=True)
def command_list_blacklisted(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    main.bot.send(msg.reply(f'@{msg.user}, There are {len(blacklist[msg.channel])} blacklisted commands: '
                            f'{", ".join(blacklist[msg.channel])}'))


@main.bot.add_command('blacklisted_join', required_permissions=[twitchirc.PERMISSION_COMMAND_JOIN],
                      enable_local_bypass=False)
def command_join_blacklisted(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    chan = msg.text.split(' ')[1].lower()
    if chan in ['all']:
        main.bot.send(msg.reply(f'Cannot join #{chan}.'))
        return
    if chan in main.bot.channels_connected:
        main.bot.send(msg.reply(f'This bot is already in channel #{chan}.'))
    else:
        blacklist[msg.channel] = [i.chat_command for i in main.bot.commands]
        blacklist[msg.channel].remove('mb.blacklist_command')
        blacklist[msg.channel].remove('mb.unblacklist_command')
        blacklist[msg.channel].remove('mb.list_blacklisted_commands')
        main.bot.send(msg.reply(f'Joining channel #{chan} with all commands blacklisted apart from '
                                f'mb.blacklist_command, mb.unblacklist_command and mb.list_blacklisted_command'))
        main.bot.join(chan)


def ensure_blacklist(channel):
    if channel not in blacklist:
        blacklist[channel] = []


main.bot._acall_command_handlers = _acall_command_handlers

if 'command_blacklist' in main.bot.storage.data:
    blacklist = main.bot.storage['command_blacklist']
else:
    main.bot.storage['command_blacklist'] = {}
