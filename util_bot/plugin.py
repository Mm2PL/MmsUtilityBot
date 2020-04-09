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
import typing

import twitchirc


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
