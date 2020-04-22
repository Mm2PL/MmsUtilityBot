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
import json
import threading
import time
import typing

import sqlalchemy
import twitchirc
from sqlalchemy.orm import reconstructor
from twitchirc import ChannelMessage

CACHE_EXPIRE_TIME = 15 * 60


def _is_pleb(msg: twitchirc.ChannelMessage) -> bool:
    print(msg.flags['badges'])
    for i in (msg.flags['badges'] if isinstance(msg.flags['badges'], list) else [msg.flags['badges']]):
        # print(i)
        if i.startswith('subscriber'):
            return False
    return True


modified_users: typing.Dict[int, typing.Dict[str, typing.Union[datetime.datetime, int, ChannelMessage]]] = {
    # base_id
    # 123: {
    #     'last_active': datetime.datetime.now(),
    #     'msg': twitchirc.ChannelMessage(),
    #     'expire_time': time.time() + CACHE_EXPIRE_TIME
    # }
}


# noinspection PyPep8Naming
def get(Base, session_scope, log):
    class UserMeta(Base.__class__):
        cache: typing.Dict[int, typing.Dict[str, typing.Union[float, typing.Any]]] = {
            # 123: {
            #     'expires': time.time() +CACHE_EXPIRE_TIME,
            #     'obj': User
            # }
        }

        def expire_caches(self):
            print('expire caches')
            current_time = time.time()
            for obj_id, obj_data in self.cache.copy().items():
                if obj_data['expires'] < current_time:
                    print(obj_id, 'expired', obj_data)
                    del self.cache[obj_id]

        def add_to_cache(self, obj):
            if obj.id in self.cache:
                print(f'[failed] Add to cache {obj}')
                return
            print(f'Add to cache {obj}')
            print(self.cache)
            self.cache[obj.id] = {
                'expires': time.time() + CACHE_EXPIRE_TIME,
                'obj': obj
            }

        def empty_cache(self):
            self.cache.clear()


    class User(Base, metaclass=UserMeta):
        __tablename__ = 'users'
        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
        twitch_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)
        discord_id = sqlalchemy.Column(sqlalchemy.Integer, unique=True)
        last_known_username = sqlalchemy.Column(sqlalchemy.Text)

        mod_in_raw = sqlalchemy.Column(sqlalchemy.Text)
        sub_in_raw = sqlalchemy.Column(sqlalchemy.Text)

        # last_active = sqlalchemy.Column(sqlalchemy.DateTime)
        # last_message = sqlalchemy.Column(sqlalchemy.UnicodeText)
        # last_message_channel = sqlalchemy.Column(sqlalchemy.Text)

        first_active = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
        permissions_raw = sqlalchemy.Column(sqlalchemy.Text, default='[]')
        permissions = []

        def import_permissions(self):
            self.permissions = json.loads(self.permissions_raw)

        def export_permissions(self):
            self.permissions_raw = json.dumps(self.permissions)

        @reconstructor
        def _reconstructor(self):
            print(f'reconstructor for {self!r}')
            self.import_permissions()
            User.add_to_cache(self)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.first_active = datetime.datetime.now()

        @staticmethod
        def _get_by_message(msg, no_create, session):
            User.expire_caches()
            print(f'get by message {msg}')
            if (hasattr(msg, 'platform') and msg.platform.name == 'TWITCH') or not hasattr(msg, 'platform'):
                for obj_id, obj_data in User.cache.items():
                    if obj_data['obj'].twitch_id == int(msg.flags['user-id']):
                        print(f'load from cache {obj_data}')
                        return obj_data['obj']

                user: User = (session.query(User)
                              .filter(User.twitch_id == msg.flags['user-id'])
                              .first())
            elif hasattr(msg, 'platform') and msg.platform.name == 'DISCORD':
                for obj_id, obj_data in User.cache.items():
                    if obj_data['obj'].discord_id == int(msg.flags['discord-user-id']):
                        print(f'load from cache {obj_data}')
                        return obj_data['obj']

                user: User = (session.query(User)
                              .filter(User.discord_id == msg.flags['discord-user-id'])
                              .first())
            else:
                raise RuntimeError('this shouldn\'t happen: bad message, fetching user')

            if user is None and not no_create:
                if (hasattr(msg, 'platform') and msg.platform.name == 'TWITCH') or not hasattr(msg, 'platform'):
                    user = User(twitch_id=msg.flags['user-id'], last_known_username=msg.user, mod_in_raw='',
                                sub_in_raw='')
                elif hasattr(msg, 'platform') and msg.platform.name == 'DISCORD':
                    user = User(twitch_id=None, last_known_username=msg.user, mod_in_raw='',
                                sub_in_raw='', discord_id=msg.flags['discord-user-id'])
                else:
                    raise RuntimeError('this shouldn\'t happen: bad message, fetching user')
                session.add(user)
                session.commit()
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
        def _get_by_twitch_id(id_: int, session):
            user: User = session.query(User).filter(User.twitch_id == id_).first()
            if user is not None:
                session.refresh(user)
            return user

        @staticmethod
        def get_by_twitch_id(id_: int, session=None):
            User.expire_caches()
            for obj_id, obj_data in User.cache.items():
                if obj_data['obj'].twitch_id == id_:
                    return obj_data['obj']

            if session:
                return User._get_by_twitch_id(id_, session)
            else:
                with session_scope() as s:
                    return User._get_by_twitch_id(id_, s)

        @staticmethod
        def _get_by_local_id(id_: int, session=None):
            user: User = session.query(User).filter(User.id == id_).first()
            if user is not None:
                session.refresh(user)
            return user

        @staticmethod
        def get_by_local_id(id_: int, s=None):
            User.expire_caches()
            if id_ in User.cache:
                return User.cache[id_]['obj']

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

        def _update(self, update, session):
            msg = update['msg']
            if msg.user != self.last_known_username:
                other_users = User.get_by_name(msg.user)
                self.last_known_username = msg.user
                for user in other_users:
                    user: User
                    user.last_known_username = '<UNKNOWN_USERNAME>'
                    session.add(user)
            session.add(self)

        def update(self, update, s=None):
            if s is None:
                with session_scope() as session:
                    self._update(update, session)
            else:
                self._update(update, s)

        def schedule_update(self, msg: twitchirc.ChannelMessage):
            global modified_users
            has_state_change = False
            was_changed = False

            if 'moderator/1' in msg.flags['badges'] or 'broadcaster/1' in msg.flags['badges']:
                if msg.channel not in self.mod_in:
                    self.add_mod_in(msg.channel)
                    has_state_change = True
                    was_changed = True
            else:
                if msg.channel in self.mod_in:
                    self.remove_mod_in(msg.channel)
                    has_state_change = True
                    was_changed = True
            if _is_pleb(msg):
                if msg.channel not in self.sub_in:
                    self.remove_sub_in(msg.channel)
                    has_state_change = True
                    was_changed = True
            else:
                if msg.channel in self.sub_in:
                    self.add_sub_in(msg.channel)
                    has_state_change = True
                    was_changed = True

            if msg.user != self.last_known_username:
                was_changed = True

            old_perms = self.permissions_raw
            self.export_permissions()
            if old_perms != self.permissions_raw:
                was_changed = True
                has_state_change = True
            if was_changed:
                modified_users[self.id] = {
                    'last_active': datetime.datetime.now(),
                    'msg': msg,
                    'expire_time': (time.time() + 10) if has_state_change else (time.time() + CACHE_EXPIRE_TIME)
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
            print(repr(channel))
            channel = channel.lower()
            if channel not in self.mod_in:
                return
            mod_in = self.mod_in
            print(mod_in)
            mod_in.remove(channel)
            print(mod_in)
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


    def _update_users(to_update):
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
                del modified_users[db_id]
        finally:
            log('debug', 'release lock.')
            users_lock.release()

    def flush_users():
        if users_lock.locked():
            return
        users_lock.acquire()
        current_time = int(time.time())
        to_update = {}
        for db_id, user in modified_users.copy().items():
            if user['expire_time'] <= current_time:
                log('debug', f'flush user {db_id}')
                to_update[db_id] = user
        if to_update:
            log('debug', f'users cache is of length {len(modified_users)}, {len(to_update)} are going to be '
                         f'removed from the cache.')

            t = threading.Thread(target=_update_users, args=(to_update,), kwargs={})
            t.start()
        else:
            users_lock.release()

    return User, flush_users


users_lock = threading.Lock()
