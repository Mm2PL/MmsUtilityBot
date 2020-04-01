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

import enum
import json
import typing

import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.orm import relationship


def get(Base, session_scope, all_settings):
    class ChannelSettings(Base):
        __tablename__ = 'channelsettings'

        channel_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'), primary_key=True)
        channel = relationship('User')
        settings_raw = sqlalchemy.Column(sqlalchemy.Text)

        def __repr__(self):
            return f'<ChannelSettings {self._settings!r}>'

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
        def load_all(session=None) -> typing.List['ChannelSettings']:
            if session is None:
                with session_scope() as s:
                    return ChannelSettings._load_all(s)
            else:
                return ChannelSettings._load_all(session)

        def _import(self) -> None:
            self._settings = json.loads(self.settings_raw)
            for name in self._settings:
                if name in all_settings:
                    all_settings[name].call_on_load(self)
                # otherwise, setting is not loaded.

        def _export(self) -> None:
            self.settings_raw = json.dumps(self._settings)

        def fill_defaults(self, forced=True):
            for v in all_settings.values():
                if (v.scope == SettingScope.PER_CHANNEL and self.channel_alias != -1) \
                        and (forced or (v.write_defaults and self.get(v) == v.default_value)):
                    self.set(v, v.default_value)

        def update(self):
            self._export()

        def get(self, setting_name, force_unknown=False) -> typing.Any:
            if force_unknown:
                return self._settings[setting_name]

            setting = Setting.find(setting_name)
            if self.channel_alias != -1 and setting.scope == SettingScope.GLOBAL:
                raise RuntimeError(f'Setting {setting_name!r} is global, it cannot be changed per channel.')

            if setting.name in self._settings:
                return self._settings[setting.name]
            else:
                return setting.default_value

        def set(self, setting_name, value, force_unknown=False) -> None:
            if force_unknown:
                self._settings[setting_name] = value
                return

            setting = Setting.find(setting_name)
            if self.channel_alias != -1 and setting.scope == SettingScope.GLOBAL:
                raise RuntimeError(f'Setting {setting_name!r} is global, it cannot be changed per channel.')

            self._settings[setting.name] = value

        def unset(self, setting_name: str, force_unknown: bool = False) -> None:
            if force_unknown:
                del self._settings[setting_name]
                return

            setting = Setting.find(setting_name)
            if self.channel_alias != -1 and setting.scope == SettingScope.GLOBAL:
                raise RuntimeError(f'Setting {setting_name!r} is global, it cannot be changed per channel.')

            del self._settings[setting.name]


    class Setting:
        default_value: typing.Any
        name: str
        scope: SettingScope

        def call_on_load(self, channel_settings):
            if self.on_load:
                self.on_load(channel_settings)

        def __init__(self, owner, name: str, default_value=..., scope=SettingScope.PER_CHANNEL,
                     write_defaults=False, setting_type=None,
                     on_load: typing.Optional[typing.Callable[[ChannelSettings], None]] = None,
                     help_: typing.Optional[str] = None):
            self.owner = owner
            self.name = name
            self.default_value = default_value
            self.scope = scope
            self.write_defaults = write_defaults
            self.on_load = on_load
            self.help = help_
            if setting_type is not None:
                self.setting_type = setting_type
            else:
                if default_value not in [..., None]:
                    self.setting_type = type(default_value)
                else:
                    self.setting_type = None  # unknown

            self.register()

        @staticmethod
        def find(name: typing.Union[str, 'Setting']):
            if isinstance(name, Setting):
                return name
            if name in all_settings:
                return all_settings[name]
            else:
                raise KeyError(
                    f'Cannot find setting {name}, did you misspell the name or is the plugin that adds it not '
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
            return (f'<Setting {self.name} '
                    f'from plugin {self.owner if isinstance(self.owner, (str, type(None))) else self.owner.name}, '
                    f'scope: {self.scope.name}>')


    return ChannelSettings, Setting


class SettingScope(enum.Enum):
    PER_CHANNEL = 0
    GLOBAL = 1
