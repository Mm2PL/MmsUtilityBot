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
import asyncio.subprocess
import typing

# noinspection PyUnresolvedReferences
import twitchirc

import util_bot

util_bot.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)

NAME = 'memes'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.ed_process = None
        self.ed_chat = None
        self.ed_command = util_bot.bot.add_command('STANDARDEDITOR', available_in_whispers=False,
                                                   required_permissions=['memes.ed'])(self.ed_command)
        self.command_insert_into_ed = util_bot.bot.add_command('[ed]', available_in_whispers=False)(self.ed_meme)
        self.command_insert_into_ed.matcher_function = lambda *_: True
        self.command_insert_into_ed.limit_to_channels = []

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

    async def ed_command(self, msg):
        if not self.ed_process:
            self.ed_process = await asyncio.subprocess.create_subprocess_exec('./ed_meme.sh', stdin=-1, stdout=-1,
                                                                              stderr=-1)
            self.ed_chat = msg.channel
            self.command_insert_into_ed.limit_to_channels = [msg.channel]
            while 1:
                line = await self.ed_process.stdout.readline()
                log('warn', 'ed -> ' + repr(line))
                line = line.decode()
                line = line.strip('\n\r\t ')
                await util_bot.bot.send(msg.reply(line))
                await util_bot.bot.flush_queue()
        else:
            return 'already running nam'

    async def ed_meme(self, msg):
        log('warn', 'ed <- ' + msg.text)
        if self.ed_process:
            await self.ed_process.stdin.write(msg.text.encode())