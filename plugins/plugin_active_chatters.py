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
import time
import typing

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'active_chatters'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.plebs = {
            # '{chat_name}': {
            # '{username}': time.time() + 60 * 60  # Expiration time
            # }
        }
        self.subs = {
            # '{chat_name}': {
            # '{username}': time.time() + 60 * 60  # Expiration time
            # }
        }
        self.count_chatters = main.bot.add_command('count_chatters', available_in_whispers=False)(self.count_chatters)
        self.count_subs_command = main.bot.add_command('count_subs',
                                                       available_in_whispers=False)(self.count_subs_command)
        self.count_plebs_command = main.bot.add_command('count_plebs',
                                                        available_in_whispers=False)(self.count_plebs_command)
        self.command_not_active = main.bot.add_command('not_active',
                                                       available_in_whispers=False)(self.command_not_active)

    def fix_sub_list(self, chat: str):
        rem_count = 0
        # print(f'plebs: {subs}')
        if chat not in self.subs:
            self.subs[chat] = {}
            return
        for k, v in self.subs[chat].copy().items():
            if v < time.time():
                del self.subs[chat][k]
                rem_count += 1
        print(f'Removed {rem_count} expired sub entries.')

    def fix_pleb_list(self, chat: str):
        rem_count = 0
        if chat not in self.plebs:
            self.plebs[chat] = {}
            return
        if chat not in self.subs:
            self.subs[chat] = {}
        print(f'plebs: {self.plebs[chat]}')
        for k, v in self.plebs[chat].copy().items():
            if k in self.subs[chat]:
                del self.plebs[chat][k]
                rem_count += 1
                continue
            if v < time.time():
                del self.plebs[chat][k]
                rem_count += 1
        print(f'Removed {rem_count} expired pleb entries.')

    def count_subs_command(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown(cmd='count_subs', msg=msg)
        if cd_state:
            return
        self.fix_sub_list(msg.channel)
        return (
            f'@{msg.flags["display-name"]} Counted {len(self.subs[msg.channel])} subs active in chat during the last '
            f'hour.'
        )

    def count_plebs_command(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown(cmd='count_plebs', msg=msg)
        if cd_state:
            return
        self.fix_pleb_list(msg.channel)
        return (f'@{msg.flags["display-name"]} Counted {len(self.plebs[msg.channel])} '
                f'plebs active in chat during the last hour.')

    def count_chatters(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown(cmd='count_chatters', msg=msg)
        if cd_state:
            return
        self.fix_pleb_list(msg.channel)
        self.fix_sub_list(msg.channel)
        return (f'@{msg.flags["display-name"]} Counted {len(self.plebs[msg.channel]) + len(self.subs[msg.channel])} '
                f'chatters active here in the last hour.')

    def command_not_active(self, msg: twitchirc.ChannelMessage):
        argv = main.delete_spammer_chrs(msg.text).split(' ')
        if len(argv) < 2:
            return f'@{msg.user} Usage: not_active <user> Marks the user as not active'
        text = argv[1:]
        if len(text) == 1:
            print(text[0])
            rem_count = 0
            if text[0] in self.plebs[msg.channel]:
                del self.plebs[msg.channel][text[0]]
                rem_count += 1
            if text[0] in self.subs[msg.channel]:
                del self.subs[msg.channel][text[0]]
                rem_count += 1
            if not rem_count:
                return f'@{msg.user} {text[0]!r}: No such chatter found.'
            else:
                return f'@{msg.user} {text[0]!r}: Marked person as not active.'

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    @property
    def on_reload(self):
        return super().on_reload

    def _is_pleb(self, msg: twitchirc.ChannelMessage) -> bool:
        for i in (msg.flags['badges'] if isinstance(msg.flags['badges'], list) else [msg.flags['badges']]):
            if i.startswith('subscriber'):
                return False
        return True

    def chat_msg_handler(self, event, msg, *args):
        if self._is_pleb(msg):
            if msg.channel not in self.plebs:
                self.plebs[msg.channel] = {}
            self.plebs[msg.channel][msg.user] = time.time() + 60 * 60
        else:
            if msg.channel not in self.subs:
                self.subs[msg.channel] = {}
            self.subs[msg.channel][msg.user] = time.time() + 60 * 60
