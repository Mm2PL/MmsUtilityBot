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

import util_bot

NAME = 'template_plugin'
__meta_data__ = {
    'name': NAME,
    'commands': []
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    no_reload = False
    name = NAME
    commands = []

    def __init__(self, module, source):
        super().__init__(module, source)
