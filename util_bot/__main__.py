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
import datetime
import gc
import inspect
import os
import sys
import urllib.parse
import time
import typing
from dataclasses import dataclass
from typing import Dict
import argparse
import traceback

import requests
import yasdu
import twitchirc
import json5 as json
from sqlalchemy import create_engine
from twitchirc import Command, Event

from apis.pubsub import PubsubClient
from util_bot import (bot, Plugin, reloadables, load_file, flush_users, User, user_model, Platform, do_cooldown,
                      show_counter_status, init_twitch_auth, UserStateCapturingMiddleware)
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
            user = User.get_by_message(message, True)
            if not user:
                return
            if message.platform == Platform.TWITCH:
                perm_state = bot.permissions.get_permission_state(message)
            else:
                perm_state = []
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
            return f'Not a number: {text}'
        else:
            c[msg.channel] = new_counter_value
        val = c[msg.channel]
        return show_counter_status(val, old_val, counter_name, counter_message, msg)

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


def reload_users():
    User.empty_cache()
    return 'emptied cache.'


reloadables['users'] = reload_users


@bot.add_command('mb.reload', required_permissions=['util.reload'], enable_local_bypass=False)
async def command_reload(msg: twitchirc.ChannelMessage):
    argv = util_bot.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 2)
    if len(argv) == 1:
        return (f'Usage: {command_reload.chat_command} <target>, list of possible reloadable targets: plugin <plugin>'
                f'{", ".join(reloadables.keys())}')
    else:
        if argv[1].lower() == 'plugin':
            if len(argv) < 3:
                return f'Usage: {command_reload.chat_command} plugin <plugin>.'
            plugin_name = argv[2]
            if plugin_name not in util_bot.plugins:
                return f'Plugin not found: {plugin_name}'

            plugin = util_bot.plugins[plugin_name]
            if plugin.no_reload:
                return f'Plugin cannot be reloaded.'

            module_name = os.path.split(plugin.source)[1].replace('.py', '')
            plugin_source = plugin.source  # copy it so it is possible to reload the plugin
            refs: typing.List[typing.Tuple[Plugin, str]] = plugin.referrers()

            # replace references with None
            for obj, ref_name in refs:
                setattr(obj, ref_name, None)

            # unload reloadables from the plugin
            for rel_name, rel in reloadables.copy().items():
                print(rel_name, rel)
                if rel.__module__ == module_name:
                    del reloadables[rel_name]

            # unload commands and settings from the plugin
            plugin_manager = util_bot.plugins['plugin_manager'].module

            for target_obj in (plugin, plugin.module):
                for key in dir(target_obj):
                    value = getattr(target_obj, key)
                    if isinstance(value, plugin_manager.Setting):
                        value.unregister()
                    if isinstance(value, twitchirc.Command):
                        util_bot.bot.commands.remove(value)

            # capture ids
            id_of_plugin = id(plugin)
            id_of_plugin_module = id(plugin.module)

            # delete the plugin's module
            del util_bot.plugins[plugin.name]
            del sys.modules[module_name]
            del plugin

            gc.collect()  # make sure the plugin is truly gone.

            new_plugin = load_file(plugin_source)

            # insert new plugin into old refs
            for obj, ref_name in refs:
                setattr(obj, ref_name, new_plugin)

            if id(new_plugin) == id_of_plugin or id(new_plugin.module) == id_of_plugin_module:
                return f'@{msg.user}, done with warning: ID of plugin is the same. Reloaded plugin {plugin_name}.'
            return f'@{msg.user}, done. Reloaded plugin {plugin_name}.'
        else:
            for name, func in reloadables.items():
                if name.lower() == argv[1].lower():
                    reload_start = time.time()
                    if inspect.iscoroutinefunction(func):
                        try:
                            o = await func()
                        except Exception as e:
                            message = (f'@{msg.user}, async reload failed. Error: {e} '
                                       f'(Time taken: {time.time() - reload_start}s)')
                        else:
                            message = (f'@{msg.user}, async reload done. Output: {o} '
                                       f'(Time taken: {time.time() - reload_start}s)')
                    else:
                        try:
                            o = func()
                        except Exception as e:
                            message = (f'@{msg.user}, sync reload failed. Error: {e} '
                                       f'(Time taken: {time.time() - reload_start}s)')
                        else:
                            message = (f'@{msg.user}, sync reload done. Output: {o} '
                                       f'(Time taken: {time.time() - reload_start}s)')
                    return message

        return f"@{msg.user} Couldn't reload {argv[1]}: no such target."


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
bot.add_command('perm')(util_bot.command_perm)
bot.add_command('join')(util_bot.command_join)
bot.add_command('part')(util_bot.command_part)
if 'counters' in bot.storage.data:
    counters = bot.storage['counters']

pubsub: typing.Optional[PubsubClient] = None

loop = asyncio.get_event_loop()

pubsub_middleware = PubsubMiddleware()

if not os.path.isfile('auth.json'):
    log('err', 'auth.json file not found.')
    log('err', 'Create a file called auth.json')
    log('err', 'Example file: {"twitch": ["bot_username", "bot_oauth"], "discord": "token"}')
    exit(1)

with open('auth.json', 'r') as f:
    other_platform_auth = json.load(f)


async def main():
    global pubsub
    auth = {
        Platform.TWITCH: (bot.storage['self_twitch_name'], 'oauth:' + util_bot.twitch_auth.json_data['access_token'])
    }
    wait = False
    for plat in Platform:
        if plat in auth:
            continue
        if plat.name.casefold() in other_platform_auth:
            auth[plat] = other_platform_auth[plat.name.casefold()]
        else:
            log('warn', f'Failed to load auth for {plat.name} from auth file. Key: {plat.name.casefold()!r}')
            wait = True
    if not auth:
        log('err', 'No platform authentication found')
        log('err', 'Exiting')
        return

    if wait:
        print('Please wait 5 seconds')
        time.sleep(5)

    await bot.init_clients(auth)
    bot.clients[Platform.TWITCH].connection.middleware.append(UserStateCapturingMiddleware())
    bot.username = bot.storage['self_twitch_name']

    if 'self_id' in bot.storage.data:
        uid = bot.storage['self_id']
    else:
        try:
            uid = util_bot.twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']
        except KeyError:
            util_bot.twitch_auth.refresh()
            util_bot.twitch_auth.save()
            uid = util_bot.twitch_auth.new_api.get_users(login=bot.username.lower())[0].json()['data'][0]['id']
        bot.storage['self_id'] = uid

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
    bot.pubsub = pubsub
    bot.middleware.append(pubsub_middleware)
    for i in bot.channels_connected:
        pubsub_middleware.join(twitchirc.Event('join', {'channel': i}, bot, cancelable=False, has_result=False))

    await bot.join(bot.username.lower())

    futures = []
    log('info', 'Spam async inits')
    for plugin in util_bot.plugins.values():
        log('info', f'Call async init for {plugin}')
        futures.append(asyncio.create_task(plugin.async_init()))

    async_init_time = 5.0

    _, pending = await asyncio.wait(futures, timeout=async_init_time,
                                    return_when=asyncio.ALL_COMPLETED)
    # wait for every plugin to initialize before proceeding
    if pending:
        log('err', f'Waiting for async inits timed out after {async_init_time} seconds. '
                   f'Assuming waiting longer will not help, exiting.')

        plugin_objects = list(util_bot.plugins.values())
        table_data = [('State', 'Plugin name', 'Path')]
        for index, fut in enumerate(futures):
            fut: asyncio.Future
            plugin = plugin_objects[index]  # order should be the same.
            done = 'done' if fut.done() else 'TIMED OUT'

            table_data.append((done, plugin.name, plugin.source))
        table = ''
        cols = 3

        # calculate maximum length of elements for each row
        col_max = [len(max(table_data, key=lambda o: len(o[col_id]))[col_id]) for col_id in range(cols)]

        for row in table_data:
            for col_id, col in enumerate(row):
                table += col
                _print(col_max[col_id], repr(col), len(col))
                table += (col_max[col_id] - len(col) + 1) * ' '
            table += '\n'
        _print(table)
        log('warn', table)

        raise TimeoutError('Waiting for async inits timed out')
    log('warn', 'async inits done')
    try:
        done, pending = await asyncio.wait({bot.arun(), pubsub.task}, return_when=asyncio.FIRST_COMPLETED)
    except KeyboardInterrupt:
        await bot.stop()
        return
    for j in done:
        await j  # retrieve any exceptions


was_cleaned_up = False


async def clean_up(trigger_fire=False, exc=None):
    global was_cleaned_up
    if was_cleaned_up:
        return
    was_cleaned_up = True

    dump_path = None
    exception_text = None
    if trigger_fire:
        exception_text = traceback.format_exc()
        if exception_text == 'NoneType: None\n':
            exception_text = None
        dump_path = yasdu.dump(f'Bot_fail_{datetime.datetime.now().isoformat()}.json',
                               comment=exception_text)
        dump_path = os.path.abspath(dump_path)

    if 'discord_ping_webhook' in bot.storage.data:
        requests.post(
            bot.storage['discord_ping_webhook'],
            json={
                "content": "restart",
                "embeds": [
                    {
                        "title": f'{"[DEBUG]" if util_bot.debug else ""}The bot is stopping/restarting',
                        "description": (
                                f'`clean_up()` was hit with `trigger_fire` = `{trigger_fire}`\n'
                                + (
                                    f'The yasdu dump is at `{dump_path}`'
                                    if dump_path
                                    else 'There was no yasdu dump done.'
                                ) + (
                                    ('The exception is: ```' + exception_text + '```') if exception_text else ""
                                )
                        ),
                        "color": 16711680
                    }
                ]
            }
        )

    await bot.stop()

    if pubsub and pubsub.task:
        pubsub.task.cancel()
        try:
            await pubsub.task
        except asyncio.CancelledError:
            pass


try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    print('toplvl Got SIGINT, exiting.')
except BaseException as e:
    traceback.print_exc()
    loop.run_until_complete(clean_up(True, exc=e))
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
    log('debug', 'save storage')
    bot.storage.save()
    log('debug', 'save storage: done')
    log('info', 'Wrapped up')
sys.exit()
