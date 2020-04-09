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

LOG_LEVELS = {
    'info': '\x1b[32minfo\x1b[m',
    'warn': '\x1b[33mwarn\x1b[m',  # weak warning
    'WARN': '\x1b[33mWARN\x1b[m',  # warning
    'err': '\x1b[31mERR\x1b[m',  # error
    'fat': '\x1b[5;31mFATAL\x1b[m',  # fatal error
    'debug': 'debug'
}
__all__ = ['LOG_LEVELS']
