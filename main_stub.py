#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import builtins
import contextlib
import importlib.util
# noinspection PyProtectedMember
import importlib._bootstrap
import io
import os
import sys
import typing

import twitchirc


class Fake:
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
        def no_reload(self) -> str:
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


    class User:
        def __init__(self):
            pass


    class Bot:
        class Storage(dict):
            def save(self):
                pass

            def load(self):
                pass

            @property
            def data(self):
                return self


        def schedule_event(self, *args):
            pass

        def schedule_repeated_event(self, *args):
            pass

        def _call_command_handlers(self):
            pass

        def send(self, *args):
            pass

        def add_command(self, command: str,
                        forced_prefix: typing.Optional[str] = None,
                        enable_local_bypass: bool = True,
                        required_permissions: typing.Optional[typing.List[str]] = None) \
                -> typing.Callable[[typing.Callable[[twitchirc.ChannelMessage],
                                                    typing.Any]], twitchirc.Command]:

            if required_permissions is None:
                required_permissions = []

            def decorator(func: typing.Callable) -> twitchirc.Command:
                cmd = twitchirc.Command(chat_command=command,
                                        function=func, forced_prefix=forced_prefix, parent=self,
                                        enable_local_bypass=enable_local_bypass)
                cmd.permissions_required.extend(required_permissions)
                self.commands.append(cmd)
                return cmd

            return decorator

        @property
        def username(self):
            return 'Fake_Bot'

        def __init__(self):
            self.storage = Fake.Bot.Storage()
            self.commands = []
            self.middleware = []
            self.handlers: typing.Dict[str, typing.List[typing.Callable]] = {
                'pre_disconnect': [],
                'post_disconnect': [],
                'pre_save': [],
                'post_save': [],
                'start': [],
                'recv_join_msg': [],
                'recv_part_msg': [],
                'recv_ping_msg': [],
                'permission_error': [],
                'any_msg': [],
                'chat_msg': []
            }

        async def _acall_forced_prefix_commands(self, *args):
            return


    def load_file(self, file):
        return

    # noinspection PyMethodMayBeStatic
    def make_log_function(self, name):
        def l(lvl, *args, **kwargs):
            return
            # print(f'[{name}/{lvl}]', *args, **kwargs)

        return l

    def add_alias(self, *args):
        return lambda *args: None

    def __init__(self):
        self.bot = Fake.Bot()
        self.Base = object
        self.reloadables = {}


    class FakeSession:
        def add(self, *args, **kwargs):
            pass

        def flush(self, *args, **kwargs):
            pass

        def expunge_all(self, *args, **kwargs):
            pass

        def commit(self, *args, **kwars):
            pass

        def rollback(self, *args, **kwars):
            pass


    @contextlib.contextmanager
    def session_scope(self):
        yield self.FakeSession()


# noinspection PyTypeChecker
sys.modules['main'] = Fake()
plugins = {}
requirements = {
}
print = print
old_print = print


def _print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    old_print(*args, **kwargs)


def patch_output():
    global print
    sys.stdout = io.StringIO()
    print = _print


def check_loaded(file_name):
    file_name = file_name if file_name.endswith('.py') else file_name + '.py'
    if file_name in plugins:
        return plugins[file_name], True
    return None, False


indent = 4
import_stack = [

]


def load_file(file_name, orig_name='', exact_name=False):
    if not exact_name:
        file_name = file_name if file_name.endswith('.py') else file_name + '.py'
    plugin_name = os.path.split(file_name)[1].replace('.py', '')
    # noinspection PyProtectedMember
    spec: importlib._bootstrap.ModuleSpec = importlib.util.spec_from_file_location(plugin_name, file_name)
    module = importlib.util.module_from_spec(spec)
    module.__builtins__ = {i: getattr(builtins, i) for i in dir(builtins)}
    module.__builtins__['__import__'] = custom_import
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError:
        p = os.path.split(file_name)
        if orig_name == '':
            return load_file(os.path.join(p[0], 'plugin_' + p[1]), orig_name=file_name)
        else:
            raise ImportError(f'Cannot import plugin: {orig_name}')
    if hasattr(module, 'Plugin'):
        pl = module.Plugin(module, file_name)
        plugins[file_name + '.Plugin'] = pl
    plugins[file_name] = module
    return module


def add_requirement(importer, plugin_name):
    if importer not in requirements:
        requirements[importer] = []
    requirements[importer].append(plugin_name)


def custom_import(name, globals_=None, locals_=None, fromlist=None, level=None):
    global indent
    reset = '\033[0m' if enable_color else ''
    if name.startswith('plugin_'):
        plugin_name = name.replace('plugin_', 'plugins/', 1)
        mod, was_loaded = check_loaded(plugin_name)
        if was_loaded:
            plus = '\033[32m+' if enable_color else '+'
            if not machine_readable:
                print((indent * ' ') + f'{plus} import {name}{reset}')
            return mod
        else:
            minus = '\033[33m-' if enable_color else '-'
            if not machine_readable:
                print((indent * ' ') + f'{minus} import {name}{reset}')
        indent += 4
        add_requirement(import_stack[-1], plugin_name)
        import_stack.append(plugin_name)
        mod = load_file(plugin_name)
        import_stack.pop()
        indent -= 4

        return mod
    if name not in ['main']:
        if not machine_readable:
            print((indent * ' ') + f'* import {name}{reset}')
        add_requirement(import_stack[-1], name)
        import_stack.append(name)
        indent += 4
        mod = __import__(name, globals_, locals_, fromlist, level)
        indent -= 4
        import_stack.pop()
        return mod
    else:
        return sys.modules['main']


enable_color = True
machine_readable = False
if __name__ == '__main__':
    # graph plugin
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('plugin', help='Create a graph of imports.')
    p.add_argument('--nocolor', '-C', dest='color', action='store_false')
    p.add_argument('--extract-help', '-H', dest='extract_help', action='store_true')
    p.add_argument('--machine-readable', '-m', dest='machine_readable', action='store_true')
    p.add_argument('--all-help', '-A', dest='all_help', action='store_true')
    args = p.parse_args()
    twitchirc.log = lambda *args: None
    enable_color = args.color
    machine_readable = args.machine_readable
    import_stack.append(args.plugin)
    if not machine_readable:
        print(args.plugin)
    try:
        load_file(args.plugin)
    except ImportError:
        load_file(args.plugin, exact_name=True)

    if machine_readable:
        print(requirements)

    if args.extract_help:
        if 'plugins/plugin_help.py' in plugins:
            plugin_help = plugins['plugins/plugin_help.py']
            o = {s: {} for s in plugin_help.all_help.keys()}
            if args.all_help:
                blacklisted_topics = []
            else:
                blacklisted_topics = [
                    'help',
                    'mb.help',

                    'help section',
                    'mb.help section',

                    'help SECTION',
                    'mb.help SECTION',

                    'help topic',
                    'mb.help topic',

                    'help TOPIC',
                    'mb.help TOPIC',

                    'section_doc',
                    'sections',
                    'help sections',
                ]
            for section, topics in plugin_help.all_help.items():
                if not machine_readable:
                    print(f'- Section {section}')
                for k, v in topics.items():
                    if k in blacklisted_topics:
                        continue
                    o[section][k] = v
                    if not machine_readable:
                        print(f'    - {k}: {v}')
            if machine_readable:
                print(o)

        else:
            if not machine_readable:
                print('plugin_help wasn\'t imported')
            else:
                print('{}')
