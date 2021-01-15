#  This is a simple utility bot
#  Copyright (C) 2021 Mm2PL
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

from util_bot import Platform


class ChannelMode(enum.Enum):
    FULL_READ_WRITE = enum.auto()  # everything is allowed
    WHITELISTED_READ_WRITE = enum.auto()  # only some commands and non-command sends will be allowed
    EXISTS = enum.auto()  # bot knows channel exists, no interaction inside of the channel is allowed
    PARENT = enum.auto()  # means that the channel can't have messages sent to it directly but you need to pick a child


class Channel:
    name: str
    id: str
    platform: Platform
    mode: ChannelMode

    def __init__(self, name: str, id_: str, platform: Platform, mode: ChannelMode):
        self.name = name
        self.id = id_
        self.platform = platform
        self.mode = mode

    def __hash__(self):
        if self.platform == Platform.TWITCH:
            return hash((self.name, self.platform))
        else:
            return hash((self.id, self.platform))
