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
import builtins
import contextlib
import inspect
import types
import urllib.parse
import importlib.util
import importlib.abc
import os
import sys
import time
import typing
from dataclasses import dataclass
import datetime
from types import ModuleType
from typing import List, Dict
import argparse
import traceback

import twitchirc
import json5 as json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from twitchirc import Command, Event
from sqlalchemy.ext.declarative import declarative_base

from apis.pubsub import PubsubClient
from apis.supibot import SupibotApi
import plugins.models.user as user_model
import twitch_auth

LOG_LEVELS = {
    'info': '\x1b[32minfo\x1b[m',
    'warn': '\x1b[33mwarn\x1b[m',  # weak warning
    'WARN': '\x1b[33mWARN\x1b[m',  # warning
    'err': '\x1b[31mERR\x1b[m',  # error
    'fat': '\x1b[5;31mFATAL\x1b[m',  # fatal error
    'debug': 'debug'
}


@dataclass
class Args:
    escalate: bool
    debug: bool
    restart_from: typing.List[str]


debug = False
base_address = None
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-e', '--escalate', help='Escalate warns, WARNs to ERRs and ERRs to fatals', action='store_true',
                   dest='escalate')
    p.add_argument('--debug', help='Run in a debug environment.', action='store_true',
                   dest='debug')
    p.add_argument('--_restart_from', help=argparse.SUPPRESS, nargs=2, dest='restart_from')
    p.add_argument('--base-addr', help='Address of database.', dest='base_addr')
    prog_args = p.parse_args()
    if prog_args.debug:
        debug = True
    if prog_args.base_addr:
        base_address = prog_args.base_addr

passwd = 'oauth:' + twitch_auth.json_data['access_token']
if debug:
    storage = twitchirc.JsonStorage('storage_debug.json', auto_save=True, default={
        'permissions': {

        }
    })
else:
    storage = twitchirc.JsonStorage('storage.json', auto_save=True, default={
        'permissions': {

        }
    })

Base = declarative_base()
if base_address:
    db_engine = create_engine(base_address)
else:
    if 'database_passwd' not in storage.data:
        raise RuntimeError('Please define a database password in storage.json.')

    db_engine = create_engine(f'mysql+pymysql://mm_sbot:{urllib.parse.quote(storage["database_passwd"])}'
                              f'@localhost/mm_sbot')

bot = twitchirc.Bot(address='irc.chat.twitch.tv', username='Mm_sUtilityBot', password=passwd,
                    storage=storage, no_atexit=True)
bot.prefix = '!'
del passwd
# noinspection PyTypeHints
bot.storage: twitchirc.JsonStorage
try:
    bot.storage.load()
except twitchirc.CannotLoadError:
    bot.storage.save()
bot.permissions.update(bot.storage['permissions'])
bot.handlers['exit'] = []
bot.storage.auto_save = False
cooldowns = {
    # 'global_{cmd}': time.time() + 1,
    # '{user}': time.time()
}


@contextlib.contextmanager
def session_scope_local_thread():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    session.expire_on_commit = False
    log('debug', 'Create local session.')
    try:
        yield session
        session.commit()
    except:
        log('debug', 'LS: Roll back.')
        session.rollback()
        raise
    finally:
        log('debug', 'LS: Expunge all and close')
        session.expunge_all()
        session.close()


session_scope = session_scope_local_thread


def _is_mod(msg: twitchirc.ChannelMessage):
    return 'moderator/1' in msg.flags['badges'] or 'broadcaster/1' in msg.flags['badges']


def make_log_function(plugin_name: str):
    def log(level, *data, **kwargs):
        if prog_args.escalate:
            if level in ['warn', 'WARN']:
                level = 'err'
            elif level in ['err']:
                level = 'fat'
        if level == 'fat':
            _print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
                   f'[{plugin_name}/{LOG_LEVELS[level]}] {" ".join([str(i) for i in data])}',
                   **kwargs)
            bot.stop()
            exit(1)
        data = ' '.join([str(i) for i in data])
        for line in data.split('\n'):
            _print((f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
                    f'[{plugin_name}/{LOG_LEVELS[level]}] {line}'),
                   **kwargs)

    return log


log = make_log_function('main')
_print = print
print = lambda *args, **kwargs: log('info', *args, **kwargs)


def do_cooldown(cmd: str, msg: twitchirc.ChannelMessage,
                global_cooldown: int = 10, local_cooldown: int = 30) -> bool:
    global cooldowns

    global_name = f'global_{msg.channel}_{cmd}'
    local_name = f'local_{cmd}_{msg.user}'
    # bot.check_permissions returns a list of missing permissions.
    # if the list is not empty, user has permissions run the code.
    if not bot.check_permissions(msg, ['util.no_cooldown'], enable_local_bypass=True):
        cooldowns[global_name] = time.time() + global_cooldown
        cooldowns[local_name] = time.time() + local_cooldown
        return False
    if _is_mod(msg):
        return False
    if msg.user in cooldowns:  # user is timeout from the bot.
        return cooldowns[msg.user] > time.time()
    if global_name not in cooldowns:
        cooldowns[global_name] = time.time() + global_cooldown
        cooldowns[local_name] = time.time() + local_cooldown
        return False
    if cooldowns[global_name] > time.time():
        return True

    if local_name not in cooldowns:
        cooldowns[global_cooldown] = time.time() + global_cooldown
        cooldowns[local_name] = time.time() + local_cooldown
        return False
    if cooldowns[local_name] > time.time():
        return True

    cooldowns[global_name] = time.time() + global_cooldown
    cooldowns[local_name] = time.time() + local_cooldown
    return False


def new_echo_command(command_name: str, echo_data: str,
                     limit_to_channel: typing.Optional[str] = None,
                     command_source='hard-coded') \
        -> typing.Callable[[twitchirc.ChannelMessage], None]:
    @bot.add_command(command_name)
    def echo_command(msg: twitchirc.ChannelMessage):
        cd_state = do_cooldown(cmd=command_name, msg=msg)
        if cd_state:
            return
        data = (echo_data.replace('{user}', msg.user)
                .replace('{cmd}', command_name))
        for num, i in enumerate(msg.text.replace(bot.prefix + command_name, '', 1).split(' ')):
            data = data.replace(f'{{{num}}}', i)
            data = data.replace('{+}', i + ' {+}')
        data = data.replace('{+}', '')
        bot.send(msg.reply(data))

    echo_command: Command
    echo_command.limit_to_channels = limit_to_channel
    echo_command.source = command_source

    return echo_command


User, flush_users = user_model.get(Base, session_scope, log)


class UserLoadingMiddleware(twitchirc.AbstractMiddleware):
    def _perm_check(self, message, required_permissions, perm_list, enable_local_bypass=True):
        missing_permissions = []
        if message.user not in perm_list:
            missing_permissions = required_permissions
        else:
            perm_state = perm_list.get_permission_state(message)
            return self._real_perm_check(enable_local_bypass, message, missing_permissions, perm_list,
                                         required_permissions, perm_state)
        return missing_permissions

    def _real_perm_check(self, enable_local_bypass, message, missing_permissions, perm_list, required_permissions,
                         perm_state):

        if twitchirc.GLOBAL_BYPASS_PERMISSION in perm_state or \
                (enable_local_bypass
                 and twitchirc.LOCAL_BYPASS_PERMISSION_TEMPLATE.format(message.channel) in perm_state):
            return []
        for p in required_permissions:
            if p not in perm_state:
                missing_permissions.append(p)
        return missing_permissions

    def permission_check(self, event: Event) -> None:
        # pre check
        message = event.data.get('message')
        permissions = event.data.get('permissions')
        enable_local_bypass = event.data.get('enable_local_bypass', False)

        missing_perms = self._perm_check(message, permissions, bot.permissions, enable_local_bypass)
        if missing_perms:
            user = User.get_by_message(message, False)
            perm_state = bot.permissions.get_permission_state(message)
            perm_state += user.permissions

            # noinspection PyProtectedMember
            perm_state = bot.permissions._get_permissions_from_parents(perm_state)

            real_missing_perms = self._real_perm_check(enable_local_bypass, message, [], bot.permissions, permissions,
                                                       perm_state)
            event.result = real_missing_perms


bot.middleware.append(UserLoadingMiddleware())


def delete_replace(text, chars):
    for ch in chars:
        text = text.replace(ch, '')
    return text


def delete_spammer_chrs(text):
    return delete_replace(text, f'\U000e0000\x01{chr(0x1f36a)}')


counters = {}


def counter_difference(text, counter):
    if text.startswith('-'):
        text = text[1:]
        print(text)
        if text.isnumeric():
            return counter - int(text)
        else:
            return None
    elif text.startswith('+'):
        text = text[1:]
        print(text)
        if text.isnumeric():
            return counter + int(text)
        else:
            return None
    elif text.startswith('='):
        text = text[1:]
        print(text)
        if text.isnumeric() or text[0].startswith('-') and text[1:].isnumeric():
            return int(text)
        else:
            return None
    return counter


def show_counter_status(old_val, val, counter_name, counter_message, msg):
    if val < 0:
        val = 'a lot of'
    print(val)
    if old_val != val:
        return msg.reply(counter_message['true'].format(name=counter_name, old_val=old_val,
                                                        new_val=val))
    else:
        return msg.reply(counter_message['false'].format(name=counter_name, val=val))


def new_counter_command(counter_name, counter_message, limit_to_channel: typing.Optional[str] = None,
                        command_source='hard-coded'):
    global counters
    counters[counter_name] = {}

    @bot.add_command(counter_name)
    def command(msg: twitchirc.ChannelMessage):
        global counters
        if isinstance(limit_to_channel, (str, list)):
            if isinstance(limit_to_channel, list) and msg.channel not in limit_to_channel:
                return
            if isinstance(limit_to_channel, str) and msg.channel != limit_to_channel:
                return

        cd_state = do_cooldown(counter_name, msg, global_cooldown=30, local_cooldown=0)
        if cd_state:
            return
        c = counters[counter_name]
        if msg.channel not in c:
            c[msg.channel] = 0
        text = msg.text[len(bot.prefix):].replace(counter_name + ' ', '')
        old_val = c[msg.channel]
        print(repr(text), msg.text)
        new_counter_value = counter_difference(text, c[msg.channel])
        if new_counter_value is None:
            bot.send(msg.reply(f'Not a number: {text}'))
            return
        else:
            c[msg.channel] = new_counter_value
        val = c[msg.channel]
        bot.send(show_counter_status(val, old_val, counter_name, counter_message, msg))

    command.source = command_source
    return command


class AliasCommand(twitchirc.Command):
    pass


def add_alias(bot_obj, alias):
    def decorator(command):
        if hasattr(command, 'aliases'):
            command.aliases.append(alias)
        else:
            command.aliases = [alias]

        async def alias_func(msg: twitchirc.ChannelMessage):
            return await command.acall(msg)

        alias_func = AliasCommand(alias, alias_func, parent=bot_obj, limit_to_channels=command.limit_to_channels,
                                  matcher_function=command.matcher_function)
        bot_obj.commands.append(alias_func)

        return command

    return decorator


def chat_msg_handler(event: str, msg: twitchirc.ChannelMessage, *args):
    user = User.get_by_message(msg, no_create=False)
    user.schedule_update(msg)


bot.schedule_repeated_event(0.1, 100, flush_users, args=(), kwargs={})


def check_spamming_allowed(channel: str, enable_online_spam=False):
    if channel == 'whispers':
        return False
    if channel in channel_live_state and channel_live_state[channel]:  # channel is live
        return enable_online_spam and check_spamming_allowed(channel, False)
    if channel in bot_user_state:
        return bot_user_state[channel]['mode'] in ('mod', 'vip')
    else:
        return False


def check_moderation(channel: str):
    if channel == 'whispers':
        return False
    if channel in bot_user_state:
        return bot_user_state[channel]['mode'] == 'mod'
    else:
        return False


bot_user_state: typing.Dict[str, typing.Dict[str, typing.Union[str, twitchirc.Message, list]]] = {
    # 'channel': {
    #     'message': twitchirc.Message(),
    #     'mode': 'mod' || 'vip' || 'user'
    # }
}
channel_live_state: Dict[str, bool] = {
    # 'channel': False
}


class UserStateCapturingMiddleware(twitchirc.AbstractMiddleware):
    def receive(self, event: Event) -> None:
        msg = event.data.get('message', None)
        if isinstance(msg, twitchirc.UserstateMessage):
            is_vip = 'vip/1' in msg.flags['badges']
            is_mod = 'moderator/1' in msg.flags['badges']

            user_state = {
                'message': msg,
                'mode': None
            }

            if is_mod:
                user_state['mode'] = 'mod'
            elif is_vip:
                user_state['mode'] = 'vip'
            else:
                user_state['mode'] = 'user'

            bot_user_state[msg.channel] = user_state
            bot.call_middleware('userstate', user_state, False)


bot.middleware.append(UserStateCapturingMiddleware())


class PubsubMiddleware(twitchirc.AbstractMiddleware):
    def join(self, event: Event) -> None:
        channel: str = event.data['channel']
        topic: str = f'video-playback.{channel}'
        print(f'join channel {channel}')
        pubsub.listen([
            topic
        ])
        pubsub.register_callback(topic)(self.live_handler)

    def part(self, event: Event) -> None:
        channel: str = event.data['channel']
        pubsub.unlisten([
            f'video-playback.{channel}'
        ])

    def live_handler(self, topic: str, msg: dict):
        channel_name = topic.replace('video-playback.', '')
        if channel_name not in channel_live_state:
            channel_live_state[channel_name] = False

        log('info', f'MEGADANK logging!!!!!!!\n'
                    f'{channel_name!r}\n'
                    f'{msg!r}')
        print(msg)
        if msg['type'] in ['stream-up', 'viewcount']:
            if not channel_live_state[channel_name]:
                bot.call_middleware('stream-up', (channel_name,), False)
            channel_live_state[channel_name] = True
        elif msg['type'] == 'stream-down':
            if channel_live_state[channel_name]:
                bot.call_middleware('stream-down', (channel_name,), False)
            channel_live_state[channel_name] = False

    async def restart_pubsub(self):
        await pubsub.stop()
        await pubsub.initialize()

    def connect(self, event: Event) -> None:
        asyncio.get_event_loop().create_task(
            self.restart_pubsub()
        )

    def userstate(self, event: Event) -> None:
        pass

    def on_action(self, event: Event):
        super().on_action(event)
        if event.name == 'userstate':
            self.userstate(event)


class PluginStorage:
    def __repr__(self):
        return f'PluginStorage(plugin={self.plugin!r}, storage={self.storage!r})'

    def __str__(self):
        return self.__repr__()

    def __init__(self, plugin, storage: twitchirc.JsonStorage):
        self.plugin = plugin
        self.storage = storage

    def load(self):
        self.storage.load()

    def save(self, is_auto_save=False):
        self.storage.save(is_auto_save)

    def __getitem__(self, item):
        return self.storage[self.plugin.name][item]

    def __setitem__(self, key, value):
        self.storage[self.plugin.name][key] = value

    def __contains__(self, item):
        return self.data.__contains__(item)

    @property
    def data(self):
        if self.plugin.name not in self.storage.data:
            self.storage.data[self.plugin.name] = {}
        return self.storage.data[self.plugin.name]


class Plugin:
    @property
    def name(self) -> str:
        return self.meta['name']

    @property
    def commands(self) -> typing.List[str]:
        return self.meta['commands']

    @property
    def no_reload(self) -> bool:
        return self.meta['no_reload'] if 'no_reload' in self.meta else False

    @property
    def on_reload(self):
        if hasattr(self.module, 'on_reload'):
            return getattr(self.module, 'on_reload')
        else:
            return None

    def __init__(self, module, source):
        self.module = module
        self.meta = module.__meta_data__
        self.source = source

    def __repr__(self):
        return f'<Plugin {self.name} from {self.source}>'


def reload_plugin(plugin: Plugin):
    if plugin.no_reload:
        return False, 'no_reload'

    print(f'Attempt to unload plugin {plugin.name} {plugin}')
    for c_name in plugin.commands:
        print(f'  Attempt to unload command {c_name}')
        for comm in bot.commands.copy():
            if comm.chat_command == c_name:
                print(f'    Unload command {c_name}/{comm}')
                bot.commands.remove(comm)
    pl_mod = plugin.module
    # print(f'      {pl_mod}')
    plugin_name = os.path.split(plugin.source)[1].replace('.py', '')
    print(plugin_name, pl_mod, plugin)
    pl_mod.__name__ = plugin_name

    old = plugin_meta_path[pl_mod]

    if plugin.on_reload:
        plugin.on_reload()
    # tell the plugin that it will be reloaded
    pl_mod = importlib.reload(pl_mod)
    sys.modules[plugin_name] = pl_mod
    plugin.module = pl_mod
    plugin_meta_path[pl_mod] = [
        old[0],
        pl_mod
    ]
    del old

    print('-' * 80)
    return True, None


def _exec(path, args):
    print(f'Running {path!r} with args {args!r}')
    os.execvp(path, args)


def reload_users():
    User.empty_cache()
    return 'emptied cache.'


reloadables: typing.Dict[str, types.FunctionType] = {}
reloadables['users'] = reload_users


@bot.add_command('mb.reload', required_permissions=['util.reload'], enable_local_bypass=False)
async def command_reload(msg: twitchirc.ChannelMessage):
    argv = delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)
    if len(argv) == 1:
        bot.send(msg.reply(f'Usage: {command_reload.chat_command} <target>, list of possible reloadable targets: '
                           f'{", ".join(reloadables.keys())}'))
    else:
        for name, func in reloadables.items():
            if name.lower() == argv[1].lower():
                reload_start = time.time()
                if inspect.iscoroutinefunction(func):
                    bot.send(msg.reply(f'@{msg.user}, reloading {name} (async)...'))
                    try:
                        o = await func()
                    except Exception as e:
                        message = f'@{msg.user}, failed. Error: {e} (Time taken: {time.time() - reload_start}s)'
                    else:
                        message = f'@{msg.user}, done. Output: {o} (Time taken: {time.time() - reload_start}s)'
                else:
                    bot.send(msg.reply(f'@{msg.user}, reloading {name} (sync)...'))

                    try:
                        o = reloadables[name]()
                    except Exception as e:
                        message = f'@{msg.user}, failed. Error: {e} (Time taken: {time.time() - reload_start}s)'
                    else:
                        message = f'@{msg.user}, done. Output: {o} (Time taken: {time.time() - reload_start}s)'
                return message

        return f'@{msg.user} Couldn\'t reload {argv[1]}: no such target.'


def new_command_from_command_entry(entry: typing.Dict[str, str]):
    if 'name' in entry and 'message' in entry:
        if 'channel' in entry:
            if entry['type'] == 'echo':
                new_echo_command(entry['name'], entry['message'], entry['channel'], command_source='commands.json')
            elif entry['type'] == 'counter':
                print(entry)
                new_counter_command(entry['name'], entry['message'], entry['channel'], command_source='commands.json')
        else:
            if entry['type'] == 'echo':
                new_echo_command(entry['name'], entry['message'], command_source='commands.json')
            elif entry['type'] == 'counter':
                new_counter_command(entry['name'], entry['message'], command_source='commands.json')


def load_commands():
    with open('commands.json', 'r') as file:
        for i in json.load(file):
            if not isinstance(i, dict):
                print(f'Bad command entry: {i!r}')
                continue
            print(f'Processing entry {i!r}')
            new_command_from_command_entry(i)


plugins: Dict[str, Plugin] = {}


class PluginNotLoadedException(Exception):
    def __init__(self, message):
        super().__init__(message)

    def __repr__(self):
        return f'PluginNotLoadedException({self.args})'

    def __str__(self):
        return self.__repr__()


def custom_import(name, globals_=None, locals_=None, fromlist=None, level=None):
    if name.startswith('plugin_'):
        plugin_name = name.replace('plugin_', '', 1)
        if plugin_name not in plugins:
            raise ImportError(f'Cannot request non-loaded plugin: {plugin_name}')
        if type(plugins[plugin_name]) is Plugin:
            return plugins[plugin_name].module
        else:
            return plugins[plugin_name]
    if name not in ['main']:
        return __import__(name, globals_, locals_, fromlist, level)
    else:
        return __import__('__main__')


# __import__(name, globals, locals, fromlist, level) -> module

class WayTooDank(BaseException):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return f'<WAYTOODANK {self.message}>'

    def __str__(self):
        return repr(self)


# noinspection PyProtectedMember
plugin_meta_path: Dict[str, List[typing.Union[importlib._bootstrap.ModuleSpec, ModuleType]]] = {
    # 'path': [
    #     'spec',
    #     'module'
    # ]
}


class PluginMetaPathFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        pass

    # noinspection PyUnusedLocal
    def find_spec(self, fullname, path, target=None):
        if target in plugin_meta_path:
            return plugin_meta_path[target][0]

    def find_module(self, fullname, path):
        return


sys.meta_path.append(PluginMetaPathFinder())


def load_file(file_name: str) -> typing.Optional[Plugin]:
    file_name = os.path.abspath(file_name)
    log('info', f'Loading file {file_name}.')

    for name, pl_obj in plugins.items():
        if pl_obj.source == file_name:
            print(' -> ALREADY LOADED')
            return None

    plugin_name = os.path.split(file_name)[1].replace('.py', '')
    log('info', f' -> Name: {plugin_name}')
    # noinspection PyProtectedMember
    spec: importlib._bootstrap.ModuleSpec = importlib.util.spec_from_file_location(plugin_name, file_name)

    module = importlib.util.module_from_spec(spec)

    # noinspection PyShadowingNames
    module.__builtins__ = {i: getattr(builtins, i) for i in dir(builtins)}
    module.__builtins__['__import__'] = custom_import

    spec.loader.exec_module(module)
    if hasattr(module, 'Plugin'):
        pl = module.Plugin(module, source=file_name)
    else:
        pl = Plugin(module, source=file_name)
    log_func = make_log_function(pl.name)
    module.__builtins__['print'] = lambda *args, **kwargs: log_func('info', *args, **kwargs)
    plugin_meta_path[pl.module] = [
        spec,
        pl.module
    ]
    sys.modules[plugin_name] = pl.module
    plugins[pl.name] = pl
    log('info', f' -> OKAY')
    return pl


def black_list_user(user, time_to_black_list):
    global cooldowns
    cooldowns[user] = time.time() + time_to_black_list


start_time = datetime.datetime.now()

with open('code_sign_public.pem', 'rb') as f:
    __public_key = load_pem_public_key(f.read(), backend=default_backend())


def verify_signed_code(code: str, sign: bytes):
    try:
        __public_key.verify(
            sign,
            bytes(code, 'utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False


def uptime() -> datetime.timedelta:
    return datetime.datetime.now() - start_time


with open('supibot_auth.json', 'r') as f:
    supibot_auth = json.load(f)

supibot_api = SupibotApi(supibot_auth['id'], supibot_auth['key'],
                         user_agent='Mm\'sUtilityBot/v1.0 (by Mm2PL), Twitch chat bot')
try:
    load_commands()
except FileNotFoundError:
    with open('commands.json', 'w') as f:
        json.dump({}, f)

# make sure that the plugin manager loads before everything else.
load_file('plugins/plugin_manager.py')

load_file('plugins/auto_load.py')

twitchirc.logging.log = make_log_function('TwitchIRC')
twitchirc.log = make_log_function('TwitchIRC')
Base.metadata.create_all(db_engine)
Session = sessionmaker(bind=db_engine)
bot.handlers['chat_msg'].append(chat_msg_handler)
twitchirc.get_join_command(bot)
twitchirc.get_part_command(bot)
twitchirc.get_perm_command(bot)
twitchirc.get_quit_command(bot)
if 'counters' in bot.storage.data:
    counters = bot.storage['counters']
if 'plebs' in bot.storage.data:
    plebs = bot.storage['plebs']
if 'subs' in bot.storage.data:
    subs = bot.storage['subs']
bot.twitch_mode()
pubsub: typing.Optional[PubsubClient] = None

loop = asyncio.get_event_loop()

bot.join(bot.username.lower())

if 'channels' in bot.storage.data:
    for i in bot.storage['channels']:
        if i in bot.channels_connected:
            log('info', f'Skipping joining channel: {i}: Already connected.')
            continue
        bot.join(i)

if prog_args.restart_from:
    msg = twitchirc.ChannelMessage(
        user='OUTGOING',
        channel=prog_args.restart_from[1],
        text=(f'@{prog_args.restart_from[0]} Restart OK. (debug)'
              if prog_args.debug else f'@{prog_args.restart_from[0]} Restart OK.')
    )
    msg.outgoing = True


    def _send_restart_message(*a):
        del a
        bot.send(msg, queue='misc')
        bot.flush_queue(1000)


    bot.schedule_event(1, 15, _send_restart_message, (), {})
pubsub_middleware = PubsubMiddleware()
bot.middleware.append(pubsub_middleware)


async def _wait_for_pubsub_task(pubsub):
    while 1:
        try:
            await pubsub.task
        except asyncio.CancelledError:
            continue


async def main():
    global pubsub
    try:
        uid = twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']
    except KeyError:
        twitch_auth.refresh()
        twitch_auth.save()
        uid = twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']

    pubsub = PubsubClient(twitch_auth.new_api.auth.token)
    await pubsub.initialize()
    pubsub.listen([
        f'chat_moderator_actions.{uid}.{uid}'
    ])
    for i in bot.channels_connected:
        pubsub_middleware.join(twitchirc.Event('join', {'channel': i}, bot, cancelable=False, has_result=False))
    await asyncio.gather(bot.arun(), _wait_for_pubsub_task(pubsub))


try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    print('Got SIGINT, exiting.')
    bot.stop()
except BaseException as e:
    traceback.print_exc()
    bot.call_middleware('fire',
                        {
                            'exception': e
                        },
                        False)
finally:
    log('debug', 'finally')
    # bot.call_handlers('exit', ())
    for name, pl in plugins.items():
        # noinspection PyBroadException
        try:
            if pl.on_reload is not None:
                pl.on_reload()
        except BaseException as e:
            log('warn', f'Failed to call on_reload for plugin {name!r}')
            traceback.print_exc()
    log('debug', 'flush cached users')
    user_model.users_lock.acquire()
    for k, v in user_model.modified_users.items():
        user_model.modified_users[k]['expire_time'] = 0
    user_model.users_lock.release()
    flush_users()
    log('debug', 'flush cached users: done')
    log('debug', 'update channels and counters')
    bot.storage.auto_save = False
    if bot.channels_connected:
        bot.storage['channels'] = bot.channels_connected
    bot.storage['counters'] = counters
    log('debug', 'update permissions')
    bot.permissions.fix()
    for i in bot.permissions:
        bot.storage['permissions'][i] = bot.permissions[i]
    bot.storage['plebs'] = plebs
    bot.storage['subs'] = subs
    log('debug', 'save storage')
    bot.storage.save()
    log('debug', 'save storage: done')
    log('info', 'Wrapped up')
