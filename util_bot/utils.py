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
import asyncio


async def watch(fd):
    future = asyncio.Future()
    loop = asyncio.get_event_loop()
    loop.add_reader(fd, future.set_result, None)
    future.add_done_callback(lambda f: loop.remove_reader(fd))
    await future


class Reconnect(RuntimeError):
    def __init__(self, platform):
        self.platform = platform


def counter_difference(text, counter):
    if text.startswith('-'):
        text = text[1:]
        print(text)
        if text.isnumeric():
            return counter - int(text)
        else:
            return None
    elif text.startswith('+'):
        text = text[1:]
        print(text)
        if text.isnumeric():
            return counter + int(text)
        else:
            return None
    elif text.startswith('='):
        text = text[1:]
        print(text)
        if text.isnumeric() or text[0].startswith('-') and text[1:].isnumeric():
            return int(text)
        else:
            return None
    return counter
