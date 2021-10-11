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

import datetime

import sqlalchemy
import twitchirc
import yasdu
from sqlalchemy.orm import relationship, joinedload


def get(Base, session_scope, blacklists, expire_queue):
    class BlacklistEntry(Base):
        __tablename__ = 'blacklist'
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        target_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'))
        target = relationship('User', foreign_keys=[target_alias])

        command = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # command name

        channel_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'))
        channel = relationship('User', foreign_keys=[channel_alias])

        expires_on = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
        is_active = sqlalchemy.Column(sqlalchemy.Boolean, default=True)

        def _check_expire(self):
            if self.expires_on is not None and self.expires_on <= datetime.datetime.now():
                blacklists.remove(self)
                expire_queue.put(self)

        @staticmethod
        def _load_all(session):
            return (session.query(BlacklistEntry)
                    .options(joinedload('*'))
                    .all())

        @staticmethod
        def load_all(session=None):
            if session is None:
                with session_scope() as s:
                    return BlacklistEntry._load_all(s)
            else:
                return BlacklistEntry._load_all(session)

        def _check_channel(self, message: twitchirc.ChannelMessage):
            if self.channel is None:
                return True
            return self.channel.last_known_username.lower() == message.channel.lower()

        def _check_user(self, message: twitchirc.ChannelMessage):
            if self.target is None:
                return True
            return message.user.lower() == self.target.last_known_username.lower()

        def _check_command(self, command: twitchirc.Command):
            if self.command is None:
                return True
            return command.chat_command.lower().rstrip(' ') == self.command.lower().rstrip(' ')

        def check(self, message: twitchirc.ChannelMessage, cmd: twitchirc.Command):
            if self.is_active is False:
                return False
            # if self._validate() is False:
            #     return False
            self._check_expire()
            return self._check_channel(message) and self._check_command(cmd) and self._check_user(message)


    return BlacklistEntry
