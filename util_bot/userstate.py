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
from twitchirc import Event

import util_bot


class UserStateCapturingMiddleware(twitchirc.AbstractMiddleware):
    def receive(self, event: Event) -> None:
        msg = event.data.get('message', None)
        if isinstance(msg, twitchirc.UserstateMessage):
            is_vip = 'vip/1' in msg.flags['badges']
            is_mod = 'moderator/1' in msg.flags['badges']
            is_broadcaster = 'broadcaster/1' in msg.flags['badges']

            user_state = {
                'message': msg,
                'mode': None
            }

            if is_mod:
                user_state['mode'] = 'mod'
            elif is_vip:
                user_state['mode'] = 'vip'
            elif is_broadcaster:
                user_state['mode'] = 'mod'
            else:
                user_state['mode'] = 'user'

            bot_user_state[msg.channel] = user_state
            util_bot.bot.call_middleware('userstate', user_state, False)


def check_moderation(channel: str):
    if channel == 'whispers':
        return False
    if channel in bot_user_state:
        return bot_user_state[channel]['mode'] == 'mod'
    else:
        return False


bot_user_state: typing.Dict[str, typing.Dict[str, typing.Union[str, twitchirc.Message, list]]] = {
    # 'channel': {
    #     'message': twitchirc.Message(),
    #     'mode': 'mod' || 'vip' || 'user'
    # }
}
