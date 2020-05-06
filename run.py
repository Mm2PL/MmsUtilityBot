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
import subprocess
import time
import os
import sys

import typing

if not os.path.exists('restart.log'):
    open('restart.log', 'x').close()

restart_log_file: typing.Optional[typing.TextIO] = None


def reopen_files():
    global restart_log_file
    if restart_log_file:
        restart_log_file.close()

    restart_log_file = open('restart.log', 'a')


def log(message):
    restart_log_file.write(f'[{datetime.datetime.now().isoformat()}] {message}\n')


reopen_files()
bot_args = sys.argv[1:]
last_fail = time.time()
fail_count = 0
while 1:
    try:
        os.remove('ipc_server')
    except FileNotFoundError:
        pass
    while 1:
        log('Refreshing token!')
        refresh_process = subprocess.Popen([f'python{sys.version_info[0]}.{sys.version_info[1]}',
                                            'clip.py', '-r'])
        try:
            ret_code = refresh_process.wait()
        except KeyboardInterrupt:
            refresh_process.wait()
            log('Refresh killed using SIGINT')
            exit(130)

        # noinspection PyUnboundLocalVariable
        if ret_code == 0:  # exit does not ever return.
            break
        elif ret_code == 130:
            raise KeyboardInterrupt(':)')
        else:
            log(f'Failed to refresh token: exit code: {ret_code}')
            if time.time() - last_fail < 60:
                log(f'Waiting {2 ** fail_count}s before next attempt')
                time.sleep(2 ** fail_count)
                fail_count += 1
            else:
                fail_count = 0
            last_fail = time.time()

    while 1:
        log('Starting bot.')
        bot_process = subprocess.Popen([f'python{sys.version_info[0]}.{sys.version_info[1]}',
                                        '-m', 'util_bot', *bot_args])
        try:
            ret_code = bot_process.wait()
        except KeyboardInterrupt:
            bot_process.wait()
            log('Bot killed using SIGINT')
            exit(130)
        if ret_code == 0:
            break
        elif ret_code == 130:
            raise KeyboardInterrupt(':)')
        else:
            log(f'Failed to run bot: exit code: {ret_code}')
            log('Waiting 3s before next attempt')
            time.sleep(3)
