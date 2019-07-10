import builtins
import datetime
import importlib.util
import os
import subprocess as sp
import time
import typing
from typing import List, Dict

import json5 as json
import twitchirc

LOG_LEVELS = {
    'info': '\x1b[32minfo\x1b[m',
    'warn': '\x1b[33mwarn\x1b[m',  # weak warning
    'WARN': '\x1b[33mWARN\x1b[m',  # warning
    'err': '\x1b[31mERR\x1b[m',  # error
    'fat': '\x1b[5;31mFATAL\x1b[m',  # fatal error
    'debug': 'debug'
}

with open('password', 'r') as f:
    passwd = f.readline().replace('\n', '')

twitchirc.logging.LOG_FORMAT = '[{time}] [TwitchIRC/{level}] {message}\n'
twitchirc.logging.DISPLAY_LOG_LEVELS = LOG_LEVELS

bot = twitchirc.Bot(address='irc.chat.twitch.tv', username='Mm_sUtilityBot', password=passwd,
                    storage=twitchirc.JsonStorage('storage.json', auto_save=True, default={
                        'permissions': {

                        }
                    }))
bot.prefix = '!'
del passwd
bot.storage: twitchirc.JsonStorage
try:
    bot.storage.load()
except twitchirc.CannotLoadError:
    bot.storage.save()
bot.permissions.update(bot.storage['permissions'])
cooldowns = {
    # 'global_{cmd}': time.time() + 1,
    # '{user}': time.time()
}


class DebugDict(dict):
    def __setitem__(self, key, value):
        print(f'DEBUG DICT: SET {key} = {value}')
        return super().__setitem__(key, value)

    def __getitem__(self, item):
        print(f'DEBUG DICT: {item}')
        return super().__getitem__(item)


def _is_mod(msg: str):
    return 'moderator/1' in msg or 'broadcaster/1' in msg


def make_log_function(plugin_name: str):
    def log(level, *data):
        return print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
                     f'[{plugin_name}/{LOG_LEVELS[level]}] {" ".join([str(i) for i in data])}')

    return log


def do_cooldown(cmd: str, msg: twitchirc.ChannelMessage,
                global_cooldown: int = 1.5 * 60, local_cooldown: int = 2 * 60) -> bool:
    if not bot.check_permissions(msg, ['util.no_cooldown'], enable_local_bypass=True):
        cooldowns[f'global_{cmd}'] = time.time()
        cooldowns[msg.user] = time.time()
        return False
    if _is_mod(msg.text):
        return False
    if f'global_{cmd}' not in cooldowns:
        cooldowns[f'global_{cmd}'] = time.time() + global_cooldown
        cooldowns[msg.user] = time.time() + local_cooldown
        return False
    if cooldowns[f'global_{cmd}'] > time.time():
        return True
    local_name = f'local_{cmd}_{msg.user}'
    if local_name not in cooldowns:
        cooldowns[local_name] = time.time() + global_cooldown
        cooldowns[local_name] = time.time() + local_cooldown
        return False
    if cooldowns[local_name] > time.time():
        return True

    cooldowns[f'global_{cmd}'] = time.time() + global_cooldown
    cooldowns[local_name] = time.time() + local_cooldown
    return False


current_vote = None


# auction_parser = twitchirc.ArgumentParser('!auction', add_help=False)
# auction_parser.add_argument('')
# @bot.add_command('auction')
# def command_auction(msg: twitchirc.ChannelMessage):
#     cd_state = do_cooldown(cmd='auction', msg=msg)
#     if cd_state:
#         return
#     args = msg.text[len(bot.prefix)+len('auction'):]


@bot.add_command('vote', required_permissions=['util.vote'])
def vote_command(msg: twitchirc.ChannelMessage):
    global current_vote
    # cd_state = do_cooldown(cmd='vote', msg=msg)
    # if cd_state:
    #     return
    a = msg.text[len(bot.prefix):].replace('vote ', '', 1)
    print(a)
    if a in ['stop', 'end', 's', 'e', 'sotp']:
        # bot.send(msg.reply('Calculating results...'))
        votes = {}
        # print('\n' * 3)
        for k, v in current_vote['votes'].items():
            print(k, v, v.text)
            num = int(v.text)
            if num not in votes:
                votes[num] = 0
            votes[num] += 1
        # print('\n' * 3)
        current_vote = None
        bot.send(
            msg.reply(
                f'Results (choice -> number of people who voted for it): '
                f'{", ".join([f"{k} -> {v}" for k, v in votes.items()])}'
            )
        )
    else:
        current_vote = {'start': time.time(), 'votes': {}}
        bot.send(msg.reply(f'Setup a new vote.'))


def new_echo_command(command_name: str, echo_data: str,
                     limit_to_channel: typing.Optional[str] = None,
                     command_source='hard-coded') \
        -> typing.Callable[[twitchirc.ChannelMessage], None]:
    @bot.add_command(command_name)
    def echo_command(msg: twitchirc.ChannelMessage):
        if isinstance(limit_to_channel, (str, list)):
            if isinstance(limit_to_channel, list) and msg.channel not in limit_to_channel:
                return
            if isinstance(limit_to_channel, str) and msg.channel != limit_to_channel:
                return

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


counters = {}


def new_counter_command(counter_name, counter_message, limit_to_channel: typing.Optional[str] = None,
                        command_source='hard-coded'):
    global counters
    counters[counter_name] = {}

    @bot.add_command(counter_name)
    def command(msg: twitchirc.ChannelMessage):
        global counters
        # if (limit_to_channel != msg.channel
        #         or (isinstance(limit_to_channel, list) or msg.channel not in limit_to_channel)):
        #     return
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
        modified = False
        old_val = c[msg.channel]
        print(repr(text), msg.text)
        if text.startswith('+1'):
            c[msg.channel] += 1
            modified = True
        elif text.startswith('-1'):
            c[msg.channel] -= 1
            modified = True
        elif text.startswith('='):
            text = text[1:]
            print(text)
            if text.isnumeric() or text[0].startswith('-') and text[1:].isnumeric():
                c[msg.channel] = int(text)
                modified = True
            else:
                bot.send(msg.reply(f'Not a number: {text}'))

        val = c[msg.channel]
        if c[msg.channel] < 0:
            val = 'a lot of'
        print(val)
        if modified:
            bot.send(msg.reply(counter_message['true'].format(name=counter_name, old_val=old_val,
                                                              new_val=val)))
        else:
            bot.send(msg.reply(counter_message['false'].format(name=counter_name, val=val)))

    command.source = command_source
    return command


# new_counter_command('bonk', {
#     True: 'Bonk counter (from {old_val}) => {new_val}',
#     False: 'Strimer has {name}ed {val} times.'
# })
tasks: List[typing.Dict[
    str, typing.Union[sp.Popen, str, twitchirc.ChannelMessage]
]] = []


def add_alias(bot_obj, alias):
    def decorator(command):
        if hasattr(command, 'aliases'):
            command.aliases.append(alias)
        else:
            command.aliases = [alias]

        @bot_obj.add_command(alias)
        def alias_func(msg: twitchirc.ChannelMessage):
            return command(msg)

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


@bot.add_command('mb.cooldowns', required_permissions=['util.cooldowns'])
def command_list_cooldowns(msg: twitchirc.ChannelMessage):
    bot.send(msg.reply(f''))


@bot.add_command('not_active', required_permissions=['util.not_active'])
def command_not_active(msg: twitchirc.ChannelMessage):
    global plebs
    text = msg.text.replace(bot.prefix + 'not_active ', '', 1).split(' ')
    print(text)
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
            bot.send(msg.reply(f'@{msg.user} {text[0]!r}: No such pleb or sub found.'))
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
    del event, msg, args
    check_quick_clips()


def chat_msg_handler(event: str, msg: twitchirc.ChannelMessage, *args):
    global plebs
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
    if current_vote:
        if msg.text.isnumeric():
            current_vote['votes'][msg.user] = msg


@bot.add_command('mb.reload', required_permissions=['util.reload'])
def command_reload(msg: twitchirc.ChannelMessage):
    print('=' * 80)
    print('Removing commands from source commands.json...')

    for num, cmd in enumerate(bot.commands):
        if hasattr(cmd, 'source') and cmd.source == 'commands.json':
            del bot.commands[num]
    print('=' * 80)
    print('Re-adding commands...')
    load_commands()
    print('DONE!')
    print('=' * 80)
    bot.send(msg.reply(f'@{msg.user} Reloaded all of the custom echo commands.'))


def new_command_from_command_entry(entry: typing.Dict[str, str]):
    if 'name' in entry and 'message' in entry:
        if 'channel' in entry:
            if entry['type'] == 'echo':
                new_echo_command(entry['name'], entry['message'], entry['channel'], command_source='commands.json')
            elif entry['type'] == 'counter':
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


class Plugin:
    @property
    def name(self):
        return self.meta['name']

    @property
    def commands(self):
        return self.meta['commands']

    def __init__(self, module, source):
        self.module = module
        self.meta = module.__meta_data__
        self.source = source


plugins: Dict[str, Plugin] = {}


def custom_import(name, globals_=None, locals_=None, fromlist=None, level=None):
    if name.startswith('plugin.'):
        return plugins[name.replace('plugin.', '', 1)].module
    if name not in ['main']:
        return __import__(name, globals_, locals_, fromlist, level)
    else:
        return __import__('__main__')


# __import__(name, globals, locals, fromlist, level) -> module


def load_file(file_name: str) -> typing.Optional[Plugin]:
    file_name = os.path.abspath(file_name)

    for name, pl_obj in plugins.items():
        if pl_obj.source == file_name:
            return

    # noinspection PyProtectedMember
    spec: importlib._bootstrap.ModuleSpec = importlib.util.spec_from_file_location(file_name, file_name)

    module = importlib.util.module_from_spec(spec)

    # noinspection PyShadowingNames
    module.__builtins__ = {i: getattr(builtins, i) for i in dir(builtins)}
    module.__builtins__['__import__'] = custom_import

    spec.loader.exec_module(module)
    pl = Plugin(module, source=file_name)
    module.__builtins__['print'] = lambda *args, **kwargs: make_log_function(pl.name)('info', *args, str(kwargs))
    plugins[pl.name] = pl.name
    return pl


try:
    load_commands()
except FileNotFoundError:
    with open('commands.json', 'w') as f:
        json.dump({}, f)

bot.handlers['chat_msg'].append(chat_msg_handler)
bot.handlers['any_msg'].append(any_msg_handler)
twitchirc.get_join_command(bot)
twitchirc.get_part_command(bot)
twitchirc.get_perm_command(bot)
twitchirc.get_no_permission_generator(bot)
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
load_file('plugins/auto_load.py')
try:
    bot.run()
finally:
    bot.storage.auto_save = False
    bot.storage['channels'] = bot.channels_connected
    bot.storage['counters'] = counters
    bot.storage['permissions'].update(bot.permissions.users)
    bot.storage['permissions'].update(bot.permissions.groups)
    bot.storage['plebs'] = plebs
    bot.storage['subs'] = subs
    bot.storage.save()
