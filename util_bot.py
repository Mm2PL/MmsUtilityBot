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
import atexit
import builtins
import contextlib
import inspect
import types
import urllib.parse
import importlib.util
import importlib.abc
import os
import subprocess as sp
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
from twitchirc import Command
from sqlalchemy.ext.declarative import declarative_base

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


# twitchirc.logging.LOG_FORMAT = '[{time}] [TwitchIRC/{level}] {message}\n'
# twitchirc.logging.DISPLAY_LOG_LEVELS = LOG_LEVELS
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
                    storage=storage)
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
        print('LS: Roll back.')
        session.rollback()
        raise
    finally:
        print('LS: Expunge all and close')
        session.expunge_all()
        session.close()


session_scope = session_scope_local_thread


class DebugDict(dict):
    def __setitem__(self, key, value):
        print(f'DEBUG DICT: SET {key} = {value}')
        return super().__setitem__(key, value)

    def __getitem__(self, item):
        print(f'DEBUG DICT: {item}')
        return super().__getitem__(item)


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


def _is_pleb(msg: twitchirc.ChannelMessage) -> bool:
    print(msg.flags['badges'])
    for i in (msg.flags['badges'] if isinstance(msg.flags['badges'], list) else [msg.flags['badges']]):
        # print(i)
        if i.startswith('subscriber'):
            return False
    return True


plebs = {
    # '{chat_name}': {
    # '{username}': time.time() + 60 * 60  # Expiration time
    # }
}
subs = {
    # '{chat_name}': {
    # '{username}': time.time() + 60 * 60  # Expiration time
    # }
}

User, flush_users = user_model.get(Base, session_scope, log)


def fix_pleb_list(chat: str):
    global plebs
    rem_count = 0
    if chat not in plebs:
        plebs[chat] = {}
        return
    if chat not in subs:
        subs[chat] = {}
    print(f'plebs: {plebs[chat]}')
    for k, v in plebs[chat].copy().items():
        if k in subs[chat]:
            del plebs[chat][k]
            rem_count += 1
            continue
        if v < time.time():
            del plebs[chat][k]
            rem_count += 1
    print(f'Removed {rem_count} expired pleb entries.')


def fix_sub_list(chat: str):
    global subs
    rem_count = 0
    # print(f'plebs: {subs}')
    if chat not in subs:
        subs[chat] = {}
        return
    for k, v in subs[chat].copy().items():
        if v < time.time():
            del subs[chat][k]
            rem_count += 1
    print(f'Removed {rem_count} expired sub entries.')


def delete_replace(text, chars):
    for ch in chars:
        text = text.replace(ch, '')
    return text


def delete_spammer_chrs(text):
    return delete_replace(text, f'\U000e0000\x01{chr(0x1f36a)}')


@bot.add_command('count_subs')
def count_subs_command(msg: twitchirc.ChannelMessage):
    global subs
    cd_state = do_cooldown(cmd='count_subs', msg=msg)
    if cd_state:
        return
    fix_sub_list(msg.channel)
    bot.send(msg.reply(
        f'@{msg.flags["display-name"]} Counted {len(subs[msg.channel])} subs active in chat during the last hour.'))


@bot.add_command('count_plebs')
def count_pleb_command(msg: twitchirc.ChannelMessage):
    global plebs
    cd_state = do_cooldown(cmd='count_plebs', msg=msg)
    if cd_state:
        return
    fix_pleb_list(msg.channel)
    bot.send(msg.reply(f'@{msg.flags["display-name"]} Counted {len(plebs[msg.channel])} '
                       f'plebs active in chat during the last hour.'))


@bot.add_command('count_chatters')
def count_chatters(msg: twitchirc.ChannelMessage):
    global plebs, subs
    cd_state = do_cooldown(cmd='count_chatters', msg=msg)
    if cd_state:
        return
    fix_pleb_list(msg.channel)
    fix_sub_list(msg.channel)
    bot.send(msg.reply(f'@{msg.flags["display-name"]} Counted {len(plebs[msg.channel]) + len(subs[msg.channel])} '
                       f'chatters active here in the last hour.'))


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


tasks: List[typing.Dict[
    str, typing.Union[sp.Popen, str, twitchirc.ChannelMessage]
]] = []


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


@add_alias(bot, 'qc')
@bot.add_command('quick_clip', required_permissions=['util.clip'])
def command_quick_clip(msg: twitchirc.ChannelMessage):
    cd_state = do_cooldown(cmd='quick_clip', msg=msg)
    if cd_state:
        return
    bot.send(msg.reply(f'@{msg.flags["display-name"]}: Clip is on the way!'))
    qc_proc = sp.Popen(['python3.7', 'clip.py', '-cC', msg.channel], stdout=sp.PIPE)
    tasks.append({'proc': qc_proc, 'owner': msg.user, 'msg': msg})


@bot.add_command('not_active', required_permissions=['util.not_active'])
def command_not_active(msg: twitchirc.ChannelMessage):
    global plebs
    argv = delete_spammer_chrs(msg.text).split(' ')
    if len(argv) < 2:
        bot.send(msg.reply(f'@{msg.user} Usage: not_active <user> Marks the user as not active'))
        return
    text = argv[1:]
    if len(text) == 1:
        print(text[0])
        rem_count = 0
        if text[0] in plebs[msg.channel]:
            del plebs[msg.channel][text[0]]
            rem_count += 1
        if text[0] in subs[msg.channel]:
            del subs[msg.channel][text[0]]
            rem_count += 1
        if not rem_count:
            bot.send(msg.reply(f'@{msg.user} {text[0]!r}: No such chatter found.'))
        else:
            bot.send(msg.reply(f'@{msg.user} {text[0]!r}: Marked person as not active.'))


def check_quick_clips():
    for i in tasks.copy():
        if i['proc'].poll() is not None:  # process exited.
            if i['proc'].poll() not in [0, 2]:
                # sub process didn't return any information for the user and didn't return 0
                more_info = (" Check the logs for more information"
                             if not bot.check_permissions(i["msg"], permissions=['group.bot_admin'])
                             else '')
                bot.send(i['msg'].reply(f'@{i["msg"].flags["display-name"]}, An error was encountered during the '
                                        f'creation of your clip. '
                                        f'Exit code: {i["proc"].poll()}.'
                                        f'{more_info}'))
                print('=' * 80)
                print(b''.join(i['proc'].stdout.readlines()).decode('utf-8', 'replace'))
                print('=' * 80)
            elif i['proc'].poll() == 2:
                # Sub process has information for the user.
                next_line = ''
                error_name = ''
                error_message = ''
                print('=' * 80)

                # pick out the lines that need to be shown to the user
                for line in i['proc'].stdout.readlines():
                    line = line.decode('utf-8', errors='ignore').replace('\n', '')
                    print(line)
                    if line == '@error':
                        next_line = 'name'
                        continue
                    if next_line == 'message':
                        error_message = line
                    if next_line == 'name':
                        error_name = line
                        next_line = 'message'
                print('=' * 80)
                bot.send(i['msg'].reply(f'@{i["msg"].flags["display-name"]}, An error was encountered during the '
                                        f'creation of your clip. Error name: {error_name}, message: {error_message}'))
            else:
                # The process returned 0
                clip_url = 'CLIP URL UNKNOWN'
                print('=' * 80)
                for line in i['proc'].stdout.readlines():
                    line = line.decode('utf-8', errors='ignore').replace('\n', '')
                    print(line)
                    if line.startswith('#'):
                        continue
                    clip_url = line
                print('=' * 80)

                if clip_url == 'CLIP URL UNKNOWN':
                    more_info = (" Check the logs for more information"
                                 if not bot.check_permissions(i["msg"], permissions=['group.bot_admin'])
                                 else '')
                    bot.send(i['msg'].reply(f'@{i["msg"].flags["display-name"]}, An error was encountered during the '
                                            f'creation of your clip. Error name: NO_URL, '
                                            f'message: The sub-program responsible for creating the clip didn\'t '
                                            f'give a url back.{more_info}'))
                    continue
                bot.send(i['msg'].reply(f'@{i["msg"].user}, Your clip is here: {clip_url}'))
            tasks.remove(i)


def any_msg_handler(event: str, msg: twitchirc.Message, *args):
    del event, args, msg
    check_quick_clips()


def chat_msg_handler(event: str, msg: twitchirc.ChannelMessage, *args):
    global plebs
    user = User.get_by_message(msg, no_create=False)
    user.schedule_update(msg)

    if _is_pleb(msg):
        if msg.channel not in plebs:
            plebs[msg.channel] = {}
        plebs[msg.channel][msg.user] = time.time() + 60 * 60
        print(event, '(pleb)', msg)
    else:
        if msg.channel not in subs:
            subs[msg.channel] = {}
        subs[msg.channel][msg.user] = time.time() + 60 * 60
        print(event, '(sub)', msg)


bot.schedule_repeated_event(0.1, 100, flush_users, args=(), kwargs={})


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


@bot.add_command('mb.restart', required_permissions=['util.restart'])
def command_restart(msg: twitchirc.ChannelMessage):
    if 'debug' in msg.text and not prog_args.debug:
        return
    bot.send(msg.reply(f'Restarting MrDestructoid {chr(128299)}'))
    # Restaring MrDestructoid :gun:
    print('.')
    while 1:
        print(f'\033[A\033[KFlushing queues... Non-empty queues: {list(filter(lambda i: bool(i), bot.queue))}')
        bot.flush_queue(1000)
        all_empty = True
        for q in bot.queue:
            if bot.queue[q]:
                all_empty = False
        if all_empty:
            break
    print('\033[A\033[KFlushing queues: DONE!')
    time.sleep(1)

    bot.stop()
    python = f'python{sys.version_info.major}.{sys.version_info.minor}'

    @atexit.register
    def run_on_shutdown():
        if prog_args.debug:
            _exec(python, [python, __file__, '--_restart_from', msg.user, msg.channel, '--debug'])
        else:
            _exec(python, [python, __file__, '--_restart_from', msg.user, msg.channel])

    raise SystemExit('restart.')


reloadables: typing.Dict[str, types.FunctionType] = {}


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
        print(f'Create meta path finder')

    def find_spec(self, fullname, path, target=None):
        print('find spec')
        print(f'{" " * 4}{fullname}\n{" " * 4}{path}\n{" " * 4}{target}')
        if target is None:
            print(f'MEGADANK: target None')
        if target in plugin_meta_path:
            return plugin_meta_path[target][0]

    def find_module(self, fullname, path):
        print('find module')
        print(f'{" " * 4}{fullname}\n{" " * 4}{path}')


sys.meta_path.append(PluginMetaPathFinder())


def load_file(file_name: str) -> typing.Optional[Plugin]:
    file_name = os.path.abspath(file_name)
    print(f'Loading file {file_name}.')

    for name, pl_obj in plugins.items():
        if pl_obj.source == file_name:
            print(' -> ALREADY LOADED')
            return None

    plugin_name = os.path.split(file_name)[1].replace('.py', '')
    print(f' -> Name: {plugin_name}')
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
    print(f' -> OKAY')
    return pl


@bot.add_command('mb.crash', required_permissions=['util.crash'], enable_local_bypass=False)
def command_generate_exception(msg: twitchirc.ChannelMessage):
    raise Exception(f'This is a test exception: {msg.text}')


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
bot.handlers['any_msg'].append(any_msg_handler)
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

bot.join(bot.username.lower())

if 'channels' in bot.storage.data:
    for i in bot.storage['channels']:
        if i in bot.channels_connected:
            print(f'Skipping joining channel: {i}: Already connected.')
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
try:
    bot.run()
except BaseException as e:
    traceback.print_exc()
    bot.call_middleware('fire',
                        {
                            'exception': e
                        },
                        False)
finally:
    print('finally')
    # bot.call_handlers('exit', ())
    for name, pl in plugins.items():
        # noinspection PyBroadException
        try:
            if pl.on_reload is not None:
                pl.on_reload()
        except BaseException as e:
            print(f'Failed to call on_reload for plugin {name!r}')
            traceback.print_exc()
    print('flush cached users')
    user_model.users_lock.acquire()
    for k, v in user_model.cached_users.items():
        user_model.cached_users[k]['expire_time'] = 0
    user_model.users_lock.release()
    flush_users()
    print('flush cached users: done')
    print('update channels and counters')
    bot.storage.auto_save = False
    bot.storage['channels'] = bot.channels_connected
    bot.storage['counters'] = counters
    print('update permissions')
    bot.permissions.fix()
    for i in bot.permissions:
        bot.storage['permissions'][i] = bot.permissions[i]
    bot.storage['plebs'] = plebs
    bot.storage['subs'] = subs
    print('save storage')
    bot.storage.save()
    print('save storage: done')
