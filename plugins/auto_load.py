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

try:
    # noinspection PyPackageRequirements
    import main
    # wtf PyCharm, why do you think `main` is an installable package
except ImportError:
    import util_bot as main


    def log(level, *msg):
        print(level, *msg)


    exit()

import twitchirc

__meta_data__ = {
    'name': 'auto_load',
    'commands': []
}
log = main.make_log_function('auto_load')

log('info', 'Plugin `auto_load` loaded')

if 'plugins' in main.bot.storage.data:
    for i in main.bot.storage['plugins']:
        log('info', f'Trying to load file: {i}')
        try:
            main.load_file(i)
        except Exception as e:
            log('warn', f'Failed to load: {e}')
else:
    main.bot.storage['plugins'] = []


@main.bot.add_command('load_plugin', required_permissions=['util.load_plugin'], enable_local_bypass=False)
def command_load_plugin(msg: twitchirc.ChannelMessage):
    argv = msg.text.split(' ')
    if len(argv) > 1:
        argv.pop(0)  # Remove the command name
    try:
        pl = main.load_file(argv[0])
        main.bot.send(msg.reply(f'Successfully loaded plugin: {pl.name}'))
    except Exception as e:
        main.bot.send(msg.reply(f'An exception was encountered: {e!r}'))
