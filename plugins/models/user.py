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
import threading
import time
import typing

import sqlalchemy
import twitchirc
from twitchirc import ChannelMessage

CACHE_EXPIRE_TIME = 15 * 60


def _is_pleb(msg: twitchirc.ChannelMessage) -> bool:
    print(msg.flags['badges'])
    for i in (msg.flags['badges'] if isinstance(msg.flags['badges'], list) else [msg.flags['badges']]):
        # print(i)
        if i.startswith('subscriber'):
            return False
    return True


cached_users: typing.Dict[int, typing.Dict[str, typing.Union[datetime.datetime, int, ChannelMessage]]] = {
    # base_id
    # 123: {
    #     'last_active': datetime.datetime.now(),
    #     'msg': twitchirc.ChannelMessage(),
    #     'expire_time': time.time() + CACHE_EXPIRE_TIME
    # }
}


# noinspection PyPep8Naming
def get(Base, session_scope, log):
    class User(Base):
        __tablename__ = 'users'
        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
        twitch_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)
        last_known_username = sqlalchemy.Column(sqlalchemy.Text)

        mod_in_raw = sqlalchemy.Column(sqlalchemy.Text)
        sub_in_raw = sqlalchemy.Column(sqlalchemy.Text)

        last_active = sqlalchemy.Column(sqlalchemy.DateTime)
        last_message = sqlalchemy.Column(sqlalchemy.UnicodeText)
        last_message_channel = sqlalchemy.Column(sqlalchemy.Text)

        first_active = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.first_active = datetime.datetime.now()

        @staticmethod
        def _get_by_message(msg, no_create, session):
            user: User = (session.query(User)
                          .filter(User.twitch_id == msg.flags['user-id'])
                          .first())

            if user is None and not no_create:
                user = User(twitch_id=msg.flags['user-id'], last_known_username=msg.user, mod_in_raw='',
                            sub_in_raw='')
                session.add(user)
            session.expunge(user)
            return user

        @staticmethod
        def get_by_message(msg: twitchirc.ChannelMessage, no_create=False, session=None):
            if session is None:
                with session_scope() as s:
                    return User._get_by_message(msg, no_create, s)
            else:
                return User._get_by_message(msg, no_create, session)

        @staticmethod
        def get_by_twitch_id(id_: int):
            with session_scope() as session:
                user: User = session.query(User).filter(User.twitch_id == id_).first()
                if user is not None:
                    session.refresh(user)
                return user

        @staticmethod
        def _get_by_local_id(id_: int, session=None):
            user: User = session.query(User).filter(User.id == id_).first()
            if user is not None:
                session.refresh(user)
            return user

        @staticmethod
        def get_by_local_id(id_: int, s=None):
            if s is None:
                with session_scope() as session:
                    return User._get_by_local_id(id_, session)
            else:
                return User._get_by_local_id(id_, s)

        @staticmethod
        def _get_by_name(name: str, session):
            users: typing.List[User] = session.query(User).filter(User.last_known_username == name).all()
            for user in users:
                session.refresh(user)
            return users

        @staticmethod
        def get_by_name(name: str, s=None) -> typing.List[typing.Any]:
            if s is None:
                with session_scope() as session:
                    return User._get_by_name(name, session)
            else:
                return User._get_by_name(name, s)

        def _update(self, msg, update, session):
            self.last_active = update['last_active']
            self.last_message = msg.text
            self.last_message_channel = msg.channel
            if 'moderator/1' in msg.flags['badges'] or 'broadcaster/1' in msg.flags['badges']:
                self.add_mod_in(msg.channel)
            else:
                self.remove_mod_in(msg.channel)
            if _is_pleb(msg):
                self.remove_sub_in(msg.channel)
            else:
                self.add_sub_in(msg.channel)
            if msg.user != self.last_known_username:
                other_users = User.get_by_name(msg.user)
                self.last_known_username = msg.user
                for user in other_users:
                    user: User
                    user.last_known_username = '<UNKNOWN_USERNAME>'
                    session.add(user)
            session.add(self)

        def update(self, update, s=None):
            msg = update['msg']
            if s is None:
                with session_scope() as session:
                    self._update(msg, update, session)
            else:
                self._update(msg, update, s)

        def schedule_update(self, msg: twitchirc.ChannelMessage):
            global cached_users
            cached_users[self.id] = {
                'last_active': datetime.datetime.now(),
                'msg': msg,
                'expire_time': time.time() + CACHE_EXPIRE_TIME
            }

        @property
        def mod_in(self):
            return [] if self.mod_in_raw == '' else self.mod_in_raw.replace(', ', ',').split(',')

        @property
        def sub_in(self):
            return [] if self.sub_in_raw == '' else self.sub_in_raw.replace(', ', ',').split(',')

        def add_sub_in(self, channel):
            channel = channel.lower()
            if channel in self.sub_in:
                return
            sub_in = self.sub_in
            sub_in.append(channel)
            self.sub_in_raw = ', '.join(sub_in)

        def remove_sub_in(self, channel):
            channel = channel.lower()
            if channel not in self.sub_in:
                return
            sub_in = self.sub_in
            sub_in.remove(channel)
            self.sub_in_raw = ', '.join(sub_in)

        def remove_mod_in(self, channel):
            channel = channel.lower()
            if channel not in self.mod_in:
                return
            mod_in = self.mod_in
            mod_in.remove(channel)
            self.mod_in_raw = ', '.join(mod_in)

        def add_mod_in(self, channel):
            channel = channel.lower()
            if channel in self.mod_in:
                return
            mod_in = self.mod_in
            mod_in.append(channel)
            self.mod_in_raw = ', '.join(mod_in)

        def __repr__(self):
            return f'<User {self.last_known_username}, alias {self.id}>'


    def flush_users():
        # print('flush users: pre lock')
        if users_lock.locked():
            return
        # print('flush users: post lock')
        users_lock.acquire()
        current_time = int(time.time())
        to_update = {}
        for db_id, user in cached_users.copy().items():
            if user['expire_time'] <= current_time:
                log('debug', f'flush user {db_id}')
                to_update[db_id] = user
        if to_update:
            # print(f'updating users: {to_update}')
            log('debug', f'users cache is of length {len(cached_users)}, {len(to_update)} are going to be removed from the '
                  f'cache.')

            def _update_users():
                try:
                    with session_scope() as session:
                        for db_id, update in to_update.copy().items():
                            log('debug', db_id, 'updating dankCircle')
                            if db_id is None:
                                log('debug', 'create new')
                                user = User.get_by_message(update['msg'])
                                user.update(update, session)
                                continue

                            user = User.get_by_local_id(db_id)
                            user.update(update, session)
                    log('debug', 'Deleting to_updates.')
                    for db_id in to_update:
                        del cached_users[db_id]
                finally:
                    log('debug', 'release lock.')
                    users_lock.release()

            t = threading.Thread(target=_update_users, args=(), kwargs={})
            t.start()
        else:
            users_lock.release()

    return User, flush_users


users_lock = threading.Lock()

