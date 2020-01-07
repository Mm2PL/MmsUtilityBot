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
import codecs
import enum
import traceback
import typing

import regex as re
import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.orm import relationship


class BanPhraseType(enum.Enum):
    replacement = 0
    deny = 1
    deny_no_warning = 2
    timeout = 3


def get(Base, log, session_scope, User):
    class BanPhrase(Base):
        __tablename__ = 'banphrase'
        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

        channel_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'), index=True)
        channel = relationship('User')

        type = sqlalchemy.Column(sqlalchemy.Enum(BanPhraseType))
        trigger = sqlalchemy.Column(sqlalchemy.Text)
        trigger_is_regex = sqlalchemy.Column(sqlalchemy.Boolean)

        input = sqlalchemy.Column(sqlalchemy.Boolean, index=True)
        output = sqlalchemy.Column(sqlalchemy.Boolean, index=True)

        extra_data = sqlalchemy.Column(sqlalchemy.Text)

        pattern = None

        @staticmethod
        def _load_all(session):
            return session.query(BanPhrase).all()

        @staticmethod
        def load_all(session=None):
            if session is None:
                with session_scope() as s:
                    return BanPhrase._load_all(s)
            else:
                return BanPhrase._load_all(session)

        @property
        def unescaped_trigger(self):
            return codecs.getdecoder("unicode_escape")(self.trigger, 'ignore')[0]

        @property
        def unescaped_warning(self):
            return codecs.getdecoder("unicode_escape")(self.warning, 'ignore')[0]

        @property
        def unescaped_replacement(self):
            return codecs.getdecoder("unicode_escape")(self.replacement, 'ignore')[0]

        def check_and_replace(self, text: str):
            if self.bad:
                return text

            check_result = self.check(text)
            if not check_result:
                return text

            if self.trigger_is_regex:
                if self.type == BanPhraseType.replacement:
                    return self.pattern.sub(self.unescaped_replacement, text)
                elif self.type == BanPhraseType.deny:
                    return self.unescaped_warning
                elif self.type == BanPhraseType.deny_no_warning:
                    return None
            else:
                if self.type == BanPhraseType.replacement:
                    return text.replace(self.unescaped_trigger, self.unescaped_replacement)
                elif self.type == BanPhraseType.deny:
                    return self.unescaped_warning
                elif self.type == BanPhraseType.deny_no_warning:
                    return None

        def check(self, text: str):
            if self.bad:
                return False

            if self.trigger_is_regex:
                self._ensure_pattern_compiled()
                if self.bad:
                    return False
                return len(self.pattern.findall(text))
            else:
                return self.trigger in text

        @staticmethod
        def _get_by_channel(channel: User, session):
            return session.query(BanPhrase).filter(BanPhrase.channel_alias == channel.id).all()

        @staticmethod
        def get_by_channel(channel: User, session: typing.Optional[typing.Any] = None):
            if session is not None:
                return BanPhrase._get_by_channel(channel, session)
            else:
                with session_scope() as s:
                    return BanPhrase._get_by_channel(channel, s)

        @property
        def replacement(self) -> str:
            if self.type == BanPhraseType.replacement:
                return str(self.extra_data)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no replacement')

        @replacement.setter
        def replacement(self, value: str):
            if self.type == BanPhraseType.replacement:
                self.extra_data = str(value)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no replacement')

        @property
        def timeout_length(self) -> int:
            if self.type == BanPhraseType.timeout:
                return int(self.extra_data)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no timeout_length')

        @timeout_length.setter
        def timeout_length(self, value):
            if self.type == BanPhraseType.timeout:
                self.extra_data = str(value)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no timeout_length')

        @property
        def warning(self) -> str:
            if self.type == BanPhraseType.deny:
                return str(self.extra_data)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no warning')

        @warning.setter
        def warning(self, value: str):
            if self.type == BanPhraseType.deny:
                self.extra_data = str(value)
            else:
                raise RuntimeError(f'Ban phrase type {self.type.name} has no warning')

        def _ensure_pattern_compiled(self):
            if self.pattern is not None:
                return
            try:
                self.pattern = re.compile(self.unescaped_trigger)
            except:
                try:
                    self.pattern = re.compile(self.trigger)
                except Exception as e:
                    self.bad = True
                    log('err', f'Bad pattern {self.unescaped_trigger!r}.')
                    for i in traceback.format_exc(limit=1000).split('\n'):
                        i = i.replace('\n', '')
                        log('err', i)

        def __repr__(self):
            return f'<BanPhrase for channel id {self.channel_alias}, {"regex " if self.trigger_is_regex else ""}' \
                   f'trigger: {self.trigger}>'

        def __init__(self, *args, **kwargs):
            self.bad = False
            super().__init__(*args, **kwargs)

        @orm.reconstructor
        def _recreate(self, *args, **kwargs):
            self.bad = False


    return BanPhrase
