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
import contextlib as _ctxlib
import datetime as _dt
import importlib.abc as _import_abc
import importlib.util as _import_util
import os as _os
import sys as _sys
import time as _time
import types as _types
import typing as _t
from types import ModuleType
import builtins as _builtins

# noinspection PyProtectedMember
import importlib._bootstrap as _import_bs
import twitchirc as _twitchirc
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.ext.declarative import declarative_base as _declarative_base
from sqlalchemy.orm import sessionmaker as _sessionmaker

from util_bot.platform import Platform
from util_bot.bot import Bot
from util_bot.constants import *
from util_bot.plugin import Plugin, PluginStorage
from util_bot.uptime import uptime
from util_bot.userstate import UserStateCapturingMiddleware, bot_user_state, check_moderation
from util_bot.pubsub import channel_live_state, init_pubsub
from util_bot.msg import StandardizedMessage, StandardizedWhisperMessage
import plugins.models.user as user_model
# noinspection PyUnresolvedReferences
from apis.supibot import ApiError, SupibotApi, SupibotAuth, SupibotEndpoint
from .base_commands import command_join, command_perm, command_part


def make_log_function(plugin_name: str):
    def log(level, *data, **kwargs):
        if level in console_log_ignore:
            return
        if escalate_errors:
            if level in ['warn', 'WARN']:
                level = 'err'
            elif level in ['err']:
                level = 'fat'
        if level == 'fat':
            _print(f'[{_dt.datetime.now().strftime("%H:%M:%S")}] '
                   f'[{plugin_name}/{LOG_LEVELS[level]}] {" ".join([str(i) for i in data])}',
                   **kwargs)
            bot.stop()
            exit(1)
        data = ' '.join([str(i) for i in data])
        for line in data.split('\n'):
            _print((f'[{_dt.datetime.now().strftime("%H:%M:%S")}] '
                    f'[{plugin_name}/{LOG_LEVELS[level]}] {line}'),
                   **kwargs)

    return log


console_log_ignore = ['debug', 'info']
log = make_log_function('util_bot')
_print = print
bot = Bot()
debug = False
escalate_errors = False
Base = _declarative_base()
cooldowns = {
    # 'global_{cmd}': time.time() + 1,
    # '{user}': time.time()
}
Session = None
plugins = {}


def delete_replace(text, chars):
    for ch in chars:
        text = text.replace(ch, '')
    return text


def delete_spammer_chrs(text):
    return delete_replace(text, f'\U000e0000\x01{chr(0x1f36a)}')


@_ctxlib.contextmanager
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


def init_sqlalchemy(base_address):
    global Session
    db_engine = _create_engine(base_address)
    Base.metadata.create_all(db_engine)
    Session = _sessionmaker(bind=db_engine)


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
        return __import__('util_bot')


reloadables: _t.Dict[str, _types.FunctionType] = {}


def search_for_refs(obj) -> _t.List[_t.Tuple['Plugin', str]]:
    refs = []
    for pl in plugins.values():
        for key in dir(pl):
            value = getattr(pl, key)
            if value is obj:
                refs.append((pl, key))

        for key in dir(pl.module):
            value = getattr(pl.module, key)
            if value is obj:
                refs.append((pl.module, key))
    return refs


class PluginNotLoadedException(Exception):
    def __init__(self, message):
        super().__init__(message)

    def __repr__(self):
        return f'PluginNotLoadedException({self.args})'

    def __str__(self):
        return self.__repr__()


# __import__(name, globals, locals, fromlist, level) -> module

def load_file(file_name: str) -> _t.Optional[Plugin]:
    file_name = _os.path.abspath(file_name)
    log('debug', f'Loading file {file_name}.')

    for name, pl_obj in plugins.items():
        if pl_obj.source == file_name:
            log('debug', ' -> ALREADY LOADED')
            return None

    plugin_name = _os.path.split(file_name)[1].replace('.py', '')
    log('debug', f' -> Name: {plugin_name}')
    # noinspection PyProtectedMember
    spec: _import_bs.ModuleSpec = _import_util.spec_from_file_location(plugin_name, file_name)

    module = _import_util.module_from_spec(spec)

    # noinspection PyShadowingNames
    module.__builtins__ = {i: getattr(_builtins, i) for i in dir(_builtins)}
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
    _sys.modules[plugin_name] = pl.module
    plugins[pl.name] = pl
    log('debug', f' -> OKAY')
    return pl


# noinspection PyProtectedMember
plugin_meta_path: _t.Dict[str, _t.List[_t.Union[_import_bs.ModuleSpec, ModuleType]]] = {
    # 'path': [
    #     'spec',
    #     'module'
    # ]
}


class PluginMetaPathFinder(_import_abc.MetaPathFinder):
    def __init__(self):
        pass

    # noinspection PyUnusedLocal
    def find_spec(self, fullname, path, target=None):
        if target in plugin_meta_path:
            return plugin_meta_path[target][0]

    def find_module(self, fullname, path):
        return


_sys.meta_path.append(PluginMetaPathFinder())

User, flush_users = user_model.get(Base, session_scope, log)


class AliasCommand(_twitchirc.Command):
    pass


def add_alias(bot_obj, alias):
    def decorator(command):
        if hasattr(command, 'aliases'):
            command.aliases.append(alias)
        else:
            command.aliases = [alias]

        async def alias_func(msg: _twitchirc.ChannelMessage):
            return await command.acall(msg)

        alias_func = AliasCommand(alias, alias_func, parent=bot_obj, limit_to_channels=command.limit_to_channels,
                                  matcher_function=command.matcher_function)
        bot_obj.commands.append(alias_func)

        return command

    return decorator


def _is_mod(msg):
    return 'moderator/1' in msg.flags['badges'] or 'broadcaster/1' in msg.flags['badges']


def do_cooldown(cmd: str, msg,
                global_cooldown: int = 10, local_cooldown: int = 30) -> bool:
    global cooldowns

    global_name = f'global_{msg.channel}_{cmd}'
    local_name = f'local_{cmd}_{msg.user}'
    # bot.check_permissions returns a list of missing permissions.
    # if the list is not empty, user has permissions run the code.
    if not bot.check_permissions(msg, ['util.no_cooldown'], enable_local_bypass=True):
        cooldowns[global_name] = _time.time() + global_cooldown
        cooldowns[local_name] = _time.time() + local_cooldown
        return False
    if _is_mod(msg):
        return False
    if msg.user in cooldowns:  # user is timeout from the bot.
        return cooldowns[msg.user] > _time.time()
    if global_name not in cooldowns:
        cooldowns[global_name] = _time.time() + global_cooldown
        cooldowns[local_name] = _time.time() + local_cooldown
        return False
    if cooldowns[global_name] > _time.time():
        return True

    if local_name not in cooldowns:
        cooldowns[global_cooldown] = _time.time() + global_cooldown
        cooldowns[local_name] = _time.time() + local_cooldown
        return False
    if cooldowns[local_name] > _time.time():
        return True

    cooldowns[global_name] = _time.time() + global_cooldown
    cooldowns[local_name] = _time.time() + local_cooldown
    return False


supibot_api: _t.Optional[SupibotApi] = None


def init_supibot_api(auth):
    global supibot_api

    supibot_api = SupibotApi(auth['id'], auth['key'],
                             user_agent='Mm\'sUtilityBot/v1.0 (by Mm2PL), Twitch chat bot')


def black_list_user(user, time_to_black_list):
    global cooldowns
    cooldowns[user] = _time.time() + time_to_black_list


class WayTooDank(BaseException):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return f'<WAYTOODANK {self.message}>'

    def __str__(self):
        return repr(self)


if _os.path.exists('code_sign_public.pem'):
    with open('code_sign_public.pem', 'rb') as f:
        __public_key = load_pem_public_key(f.read(), backend=default_backend())
else:
    __public_key = None


def verify_signed_code(code: str, sign: bytes):
    if not __public_key:  # no public key to load, can't verify, just act like the signature is wrong.
        return False

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


def check_spamming_allowed(channel: str, enable_online_spam=False):
    if channel == 'whispers':
        return False
    if channel in channel_live_state and channel_live_state[channel]:  # channel is live
        return enable_online_spam and check_spamming_allowed(channel, False)
    if channel in bot_user_state:
        return bot_user_state[channel]['mode'] in ('mod', 'vip')
    else:
        return False


def show_counter_status(old_val, val, counter_name, counter_message, msg):
    if val < 0:
        val = 'a lot of'
    print(val)
    if old_val != val:
        return msg.reply(counter_message['true'].format(name=counter_name, old_val=old_val,
                                                        new_val=val))
    else:
        return msg.reply(counter_message['false'].format(name=counter_name, val=val))


twitch_auth = None


def init_twitch_auth():
    global twitch_auth
    # noinspection PyUnresolvedReferences
    import twitch_auth as _ta
    twitch_auth = _ta
