#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import atexit
import queue
import threading
import typing

import requests

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'hastebin'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)
HASTEBIN_ADDR = 'https://www.kotmisia.pl/haste/'


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.to_create_queue = queue.Queue()
        self.link_queue = queue.Queue()
        self.c_hastebin = main.bot.add_command('hastebin')(self.c_hastebin)
        plugin_help.add_manual_help_using_command('Create a hastebin of the message you provided.')(self.c_hastebin)

        main.bot.schedule_repeated_event(0.1, 10, self.send_link, (), {})
        self.thread = threading.Thread(target=self.threaded_hastebin, args=(self.to_create_queue, self.link_queue))
        self.thread.start()

    @atexit.register
    def on_exit(self):
        self.to_create_queue.put(None)

    def threaded_hastebin(self, in_q: queue.Queue, out_q: queue.Queue):
        while 1:
            elem = in_q.get()
            if elem is None:
                break
            elem: typing.Tuple[str, twitchirc.ChannelMessage]
            data, msg = elem
            r = requests.post(f'{HASTEBIN_ADDR}documents',
                              data=data.encode('utf-8'))
            response = r.json()
            out_q.put(msg.reply(f'@{msg.user} Here\'s your hastebin link {HASTEBIN_ADDR}{response["key"]}'))

    def c_hastebin(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('hastebin', msg, global_cooldown=0, local_cooldown=30)
        if cd_state:
            return
        data = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)[1]
        self.to_create_queue.put((data, msg))

    def send_link(self, *args, **kwargs):
        del args, kwargs
        if self.link_queue.empty():
            return
        elem = self.link_queue.get_nowait()
        if isinstance(elem, twitchirc.ChannelMessage):
            main.bot.send(elem)

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
