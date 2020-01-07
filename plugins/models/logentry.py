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

CAUSE_COMMAND = 0
CAUSE_TASK = 1
CAUSE_API = 2
CAUSE_OTHER = 3
LOG_LEVELS_DISPLAY = {
    -1: 'debug',
    0: '\x1b[32minfo\x1b[m',
    1: '\x1b[33mwarn\x1b[m',  # weak warning
    2: '\x1b[33mWARN\x1b[m',  # warning
    3: '\x1b[31mERR\x1b[m',  # error
    10: '\x1b[5;31mFATAL\x1b[m',  # fatal error
}
CAUSES = {
    CAUSE_OTHER: 'other',
    CAUSE_TASK: 'task',
    CAUSE_API: 'api',
    CAUSE_COMMAND: 'command',
}


def get(Base):
    class LogEntry(Base):
        __tablename__ = 'logs'
        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, nullable=False)
        time = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now, nullable=False)
        source = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
        level = sqlalchemy.Column(sqlalchemy.SmallInteger, nullable=False)
        message = sqlalchemy.Column(sqlalchemy.UnicodeText, nullable=False)

        cause = sqlalchemy.Column(sqlalchemy.SmallInteger, nullable=False)

        @staticmethod
        def static_pretty(source, level, message, cause):
            output = []
            for line in message.split('\n'):
                output.append(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
                              f'[{source}/{LOG_LEVELS_DISPLAY[level]} ({CAUSES[cause]})] '
                              f'{line}')
            return '\n'.join(output)

        @property
        def pretty(self):
            return LogEntry.static_pretty(self.source, self.level, str(self.message), self.cause)


    return LogEntry
