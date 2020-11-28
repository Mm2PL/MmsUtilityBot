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
import re
import typing

import twitchirc

from util_bot.platform import Platform


class StandardizedMessage(twitchirc.ChannelMessage):
    def __init__(self, text: str, user: str, channel: str, platform: Platform, outgoing=False, parent=None,
                 source_message=None):
        super().__init__(text, user, channel, outgoing=outgoing, parent=parent)
        self.platform = platform
        self.source_message = source_message

    def moderate(self):
        if self.platform != Platform.TWITCH:
            raise NotImplementedError('moderate() is not implemented outside of twitch, yet')
        return super().moderate()

    def reply(self, text: str, force_slash=False):
        if not force_slash and text.startswith(('.', '/')):
            text = '/ ' + text
        if self.platform == Platform.DISCORD:
            text = re.sub(r'@(<@\d+>)', r'\1', text)
        new = StandardizedMessage(text=text, user='OUTGOING', channel=self.channel, platform=self.platform)
        new.outgoing = True
        new.flags['in_reply_to'] = self
        return new

    def reply_directly(self, text: str):
        if self.platform == Platform.DISCORD:
            text = re.sub(r'@(<@\d+>)', r'\1', text)
        new = StandardizedWhisperMessage('OUTGOING', user_to=self.user, text=text, platform=self.platform,
                                         outgoing=True)
        new.flags['in_reply_to'] = self
        return new

    def __repr__(self):
        return (f'StandardizedMessage(text={self.text!r}, user={self.user!r}, channel={self.channel!r}, '
                f'platform={self.platform!r})')

    def __str__(self):
        return f'[{self.platform.name}] #{self.channel} <{self.user}> {self.text}'

    def __bytes__(self):
        if self.platform == Platform.TWITCH:
            return super().__bytes__()
        else:
            raise NotImplementedError(f'Unable to convert an instance of StandardizedMessage for platform '
                                      f'{self.platform.name} to bytes')

    @property
    def user_mention(self):
        return self.parent.clients[self.platform].format_mention(self)


class StandardizedWhisperMessage(twitchirc.WhisperMessage):
    def __init__(self, user_from, user_to, text, platform: Platform,
                 flags: typing.Optional[typing.Dict[str, str]] = None, outgoing=False,
                 source_message=None):
        if flags is None:
            flags = {}

        super().__init__(flags, user_from, user_to, text, outgoing=outgoing)
        self.platform = platform
        self.source_message = source_message

    def __repr__(self):
        return (f'StandardizedWhisperMessage(platform={self.platform!r}, user_from={self.user_from!r}, '
                f'user_to={self.user_to!r}, text={self.text!r})')

    def __str__(self):
        return super().__str__()

    def __bytes__(self):
        return super().__bytes__()

    @property
    def user(self):
        return self.user_from

    def reply(self, text: str):
        if self.platform == Platform.DISCORD:
            text = re.sub(r'@(<@\d+>)', r'\1', text)
        new = StandardizedWhisperMessage(user_from=self.user_to, user_to=self.user_from, text=text,
                                         platform=self.platform, flags=None, outgoing=True)
        new.flags['in_reply_to'] = self
        return new
