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
import inspect
import urllib.parse
import time
import typing
from dataclasses import dataclass
from typing import Dict
import argparse
import traceback

import twitchirc
import json5 as json
from sqlalchemy import create_engine
from twitchirc import Command, Event

from apis.pubsub import PubsubClient
from util_bot import (bot, Plugin, reloadables, load_file, flush_users, User, user_model, Platform, do_cooldown,
                      UserStateCapturingMiddleware, show_counter_status, init_twitch_auth)
import util_bot
from util_bot.msg import StandardizedMessage
from util_bot.pubsub import init_pubsub, PubsubMiddleware
from util_bot.utils import counter_difference


@dataclass
class Args:
    escalate: bool
    debug: bool
    restart_from: typing.List[str]


base_address = None
debug = False
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
        util_bot.debug = True
        debug = True
    if prog_args.base_addr:
        base_address = prog_args.base_addr
init_twitch_auth()
passwd = 'oauth:' + util_bot.twitch_auth.json_data['access_token']
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

if base_address:
    db_engine = create_engine(base_address)
else:
    if 'database_passwd' not in storage.data:
        raise RuntimeError('Please define a database password in storage.json.')

    db_engine = create_engine(f'mysql+pymysql://mm_sbot:{urllib.parse.quote(storage["database_passwd"])}'
                              f'@localhost/mm_sbot')

# bot = twitchirc.Bot(address='irc.chat.twitch.tv', username='Mm_sUtilityBot', password=passwd,
#                     storage=storage, no_atexit=True)
# bot.prefix = '!'
bot.prefix = '!'
bot.storage = storage

# noinspection PyTypeHints
bot.storage: twitchirc.JsonStorage
try:
    bot.storage.load()
except twitchirc.CannotLoadError:
    bot.storage.save()
bot.permissions.update(bot.storage['permissions'])
bot.handlers['exit'] = []
bot.storage.auto_save = False

session_scope = util_bot.session_scope_local_thread

log = util_bot.make_log_function('main')
_print = print
print = lambda *args, **kwargs: log('info', *args, **kwargs)


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

counters = {}


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


def chat_msg_handler(event: str, msg: StandardizedMessage, *args):
    if msg.platform == Platform.TWITCH:
        user = User.get_by_message(msg, no_create=True)
        # don't store data there is no need for
        if user:  # user exists, make sure data is up to date
            user.schedule_update(msg)
            # needed in case someone gets/loses moderator status

    # ignore other platforms


bot.schedule_repeated_event(0.1, 100, flush_users, args=(), kwargs={})

bot.middleware.append(UserStateCapturingMiddleware())


def reload_users():
    User.empty_cache()
    return 'emptied cache.'


reloadables['users'] = reload_users


@bot.add_command('mb.reload', required_permissions=['util.reload'], enable_local_bypass=False)
async def command_reload(msg: twitchirc.ChannelMessage):
    argv = util_bot.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)
    if len(argv) == 1:
        return (f'Usage: {command_reload.chat_command} <target>, list of possible reloadable targets: '
                f'{", ".join(reloadables.keys())}')
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

with open('supibot_auth.json', 'r') as f:
    supibot_auth = json.load(f)

util_bot.init_supibot_api(supibot_auth)
try:
    load_commands()
except FileNotFoundError:
    with open('commands.json', 'w') as f:
        json.dump({}, f)

# make sure that the plugin manager loads before everything else.
load_file('plugins/plugin_manager.py')

load_file('plugins/auto_load.py')

util_bot.init_sqlalchemy(base_address)
twitchirc.logging.log = util_bot.make_log_function('TwitchIRC')
twitchirc.log = util_bot.make_log_function('TwitchIRC')

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

pubsub: typing.Optional[PubsubClient] = None

loop = asyncio.get_event_loop()

pubsub_middleware = PubsubMiddleware()

# async def _wait_for_pubsub_task(pubsub):
#     while 1:
#         try:
#             print('await pubsub task')
#             await pubsub.task
#             print('pubsub task end')
#         except asyncio.CancelledError:
#             return
#             continue

with open('discord_auth.json', 'r') as f:
    try:
        discord_auth = json.load(f)
    except Exception as e:
        print('Failed to load credentials for discord, disabling support')
        print('Please wait 1s')
        time.sleep(1)


async def main():
    global pubsub
    name = bot.storage['self_twitch_name']
    auth = {
        Platform.TWITCH: (name, passwd)
    }
    if discord_auth:
        if 'access_token' not in discord_auth:
            print('Failed to load `access_token` from Discord auth file.')
            print('Please wait 1s')
            time.sleep(1)
        auth[Platform.DISCORD] = discord_auth['access_token']
    await bot.init_clients(auth)
    bot.username = name

    try:
        uid = util_bot.twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']
    except KeyError:
        util_bot.twitch_auth.refresh()
        util_bot.twitch_auth.save()
        uid = util_bot.twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']

    await bot.aconnect()
    bot.cap_reqs(False)

    if 'channels' in bot.storage.data:
        for i in bot.storage['channels']:
            if i in bot.channels_connected:
                log('info', f'Skipping joining channel: {i}: Already connected.')
                continue
            await bot.join(i)

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
            bot.send(msg)
            bot.flush_queue(1000)

        bot.schedule_event(1, 15, _send_restart_message, (), {})

    pubsub = await init_pubsub(util_bot.twitch_auth.new_api.auth.token)

    temp = util_bot.make_log_function('pubsub')
    pubsub.log_function = lambda *text, **kwargs: temp('debug', *text, **kwargs)

    pubsub.listen([
        f'chat_moderator_actions.{uid}.{uid}'
    ])
    bot.middleware.append(pubsub_middleware)
    for i in bot.channels_connected:
        pubsub_middleware.join(twitchirc.Event('join', {'channel': i}, bot, cancelable=False, has_result=False))

    await bot.join(bot.username.lower())
    try:
        await asyncio.wait({bot.arun(), pubsub.task}, return_when=asyncio.FIRST_EXCEPTION)
    except KeyboardInterrupt:
        await bot.stop()
        return


was_cleaned_up = False


async def clean_up(trigger_fire=False):
    global was_cleaned_up
    if was_cleaned_up:
        was_cleaned_up = True
        return
    if trigger_fire:
        await bot.acall_middleware('fire', {'exception': e}, False)
    await bot.stop()


try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    print('toplvl Got SIGINT, exiting.')
except BaseException as e:
    traceback.print_exc()
    loop.run_until_complete(clean_up(True))
finally:
    loop.run_until_complete(clean_up())
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
    # bot.storage['plebs'] = plebs
    # bot.storage['subs'] = subs
    log('debug', 'save storage')
    bot.storage.save()
    log('debug', 'save storage: done')
    log('info', 'Wrapped up')