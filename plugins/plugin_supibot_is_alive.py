#  This is a simple utility bot
#  Copyright (C) 2019 Maciej Marciniak
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
import json
import threading
import time
import atexit

import requests

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()

__meta_data__ = {
    'name': 'plugin_supibot_is_alive',
    'commands': []
}
log = main.make_log_function('supibot_is_alive')

with open('supibot_auth.json', 'r') as f:
    supibot_auth = json.load(f)

killer_lock = threading.Lock()


def job_active(job_kill_lock: threading.Lock):
    while 1:
        if job_kill_lock.locked():
            break
        r = requests.put('https://supinic.com/api/bot/active',
                         headers={
                             'Authorization': f'Basic {supibot_auth["id"]}:{supibot_auth["key"]}',
                             'User-Agent': 'Mm\'sUtilityBot/v1.0 (by Mm2PL), Twitch chat bot'
                         })
        if r.status_code == 400:
            log('err', 'Sent Supibot active call, not a bot :(, won\'t attempt again.')
            break

        elif r.status_code == 200:
            log('info', 'Sent Supibot active call. OK')

        elif r.status_code in [401, 403]:
            log('warn', 'Sent Supibot active call. Bad authorization.')
        else:
            log('err', f'Sent Supibot active call. Invalid status code: {r.status_code}, {r.content.decode("utf-8")}')
        time.sleep(60 * 60 * 0.5)


thread = threading.Thread(target=job_active, args=(killer_lock,))
thread.start()


@atexit.register
def auto_kill_job(*args):
    print('Stopping Supibot heartbeat thread.')
    killer_lock.acquire()
    thread.join()
    print('Done.')
