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
import asyncio
import time
import warnings
from typing import Tuple
import typing

import regex
from PIL import Image

try:
    from utils import arg_parser

except ImportError:
    from plugins.utils import arg_parser

try:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from helpers import braille
except ImportError:
    from plugins.helpers import braille

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit(1)
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

main.load_file('plugins/plugin_hastebin.py')
try:
    import plugin_hastebin as plugin_hastebin
except ImportError:
    from plugins.plugin_hastebin import Plugin as PluginHastebin

    plugin_hastebin: PluginHastebin

import random

import twitchirc

__meta_data__ = {
    'name': 'plugin_cancer',
    'commands': []
}

log = main.make_log_function('cancerous_plugin')
with open(__file__, 'r') as f:
    lines = f.readlines()
    file_lines = len(lines)
    file_length = sum([len(i) for i in lines])

del lines

RECONNECTION_MESSAGES = [
    'WYKRYTOMIÓD RECONNECTED!',
    'HONEYDETECTED YET ANOTHER SPAM MESSAGE',
    'Look, I made Supi\'s packets come back PagChomp',
    'asd',
    f'Look, this cancerous "feature" is only {file_length} characters',
    f'Look, this cancerous "feature" is only {file_lines} lines',
    'FeelsGoodMan Clap spam',
    '🅱ing @{ping} PepeS'
]

COOKIE_PATTERN = regex.compile(
    rf'^\[Cookies\] '
    rf'\[(?P<rank>(?:P[1-4]: )?'
    rf'(?:[dD]efault|[bB]ronze|[sS]ilver|[gG]old|[pP]latinum|[dD]iamond|[mM]asters|[gG]rand[mM]asters|[lL]eader))\] '
    rf'(?P<name>[a-z0-9_]+) \U0001f3ab'
)
RAID_PATTERN = regex.compile(
    r'A Raid Event at Level \[[0-9]+\] has appeared\. Type \+join to join the raid! The raid '
    r'will begin in [0-9]+ seconds!'
)
ED_FAIL_PATTERN = regex.compile(
    r', you have already entered the dungeon recently, [0-9]:(?P<time>[0-9]{2}:[0-9]{2}) left until you can enter '
    r'again! ⌛'
)
COOLDOWN_TIMEOUT = 1.5

PRESTIGE_PATTERN = regex.compile('P([1-4]):')
COOKIE_PRESTIGE_TIMES = {
    0: '2h',
    1: '1h',
    2: '30m',
    3: '20m'
}


class Plugin(main.Plugin):
    _sneeze: Tuple[float, typing.Optional[twitchirc.ChannelMessage]]

    def _time_from_rank(self, text) -> str:
        prestige_match = PRESTIGE_PATTERN.findall(text)
        if prestige_match:
            level = int(prestige_match[0])
            if level in COOKIE_PRESTIGE_TIMES:
                return COOKIE_PRESTIGE_TIMES[level]
            else:
                log('warn', f'Unknown prestige level: {level!r}. Message {text!r}')
                return COOKIE_PRESTIGE_TIMES[0] + ' monkaS unknown prestige level.'
        else:
            return COOKIE_PRESTIGE_TIMES[0]

    def chan_msg_handler(self, event: str, msg: twitchirc.ChannelMessage):
        if msg.user in ['supibot', 'mm2pl'] and msg.text.startswith('HONEYDETECTED RECONNECTED') \
                and msg.channel == 'supinic':
            random_msg = random.choice(RECONNECTION_MESSAGES)
            while '{ping}' in random_msg:
                random_msg = random_msg.replace('{ping}', random.choice(self.random_pings), 1)
            main.bot.send(msg.reply(random_msg))
        if msg.channel in ['supinic', 'mm2pl'] and msg.user in ['thepositivebot', 'linkusbanned'] \
                and msg.text.startswith('\x01ACTION [Cookies]'):
            m = COOKIE_PATTERN.findall(main.delete_spammer_chrs(msg.text.replace('\x01ACTION ', '')))
            if m and m[0][1].lower() in self.cookie_optin:
                time_ = self._time_from_rank(msg.text)

                main.bot.send(msg.reply(f'$remind {m[0][1].lower()} cookie :) in {time_}'))
            elif not m:
                log('warn', f'matching against regex failed: {msg.text!r}')

        if msg.text.startswith('$ps sneeze') and msg.channel in ['supinic', 'mm2pl']:
            self._sneeze = (time.time() + self.cooldown_timeout, msg)

        if msg.user == 'supibot' and self._sneeze[1] is not None and (
                msg.text.startswith(
                    self._sneeze[1].user + ', The playsound\'s cooldown has not passed yet! Try again in')
                or msg.text.startswith(self._sneeze[1].user + ', Playsounds are currently disabled!')
        ):
            # don't respond if the playsound didn't play
            self._sneeze = (-1, None)

        if msg.channel == self.ed_channel:
            m = RAID_PATTERN.match(msg.text)
            if m:
                main.bot.send(msg.reply('+join'))

            if msg.text.casefold().startswith(main.bot.username.casefold()):
                text = regex.sub(main.bot.username, '', msg.text, flags=regex.I)
                print(repr(text))
                m2 = ED_FAIL_PATTERN.match(text)
                if m2:
                    new_time = m2.group('time')
                    minutes, seconds = new_time.split(':')
                    try:
                        self.next_ed_time = time.time() + (int(minutes) * 60) + int(seconds)
                        print('updated timer!!')
                    except Exception as e:
                        log('err', f'Pepega: {e}')

    def waytoodank_timer(self):
        if self._sneeze[0] <= time.time() and self._sneeze[1] is not None:
            main.bot.send(self._sneeze[1].reply('WAYTOODANK'))
            self._sneeze = (-1, None)
        self._enter_dungeon()

    @property
    def cooldown_timeout(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(self.timeout_setting)

    @property
    def random_pings(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(self.random_ping_setting)

    @property
    def cookie_optin(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(self.cookie_optin_setting)

    @property
    def status_every_frames(self):
        return (plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name]
                .get(self.status_every_frames_setting))

    @property
    def time_before_status(self):
        return (plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name]
                .get(self.time_before_status_setting))

    @property
    def ed_channel(self):
        return (plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name]
                .get(self.ed_channel_setting))

    def _get_pyramid_enabled(self, channel: str):
        return plugin_manager.channel_settings[channel].get(self.pyramid_enabled_setting) is True

    def __init__(self, module, source):
        super().__init__(module, source)
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        self.timeout_setting = plugin_manager.Setting(self,
                                                      'cancer.waytoodank_timeout',
                                                      default_value=1.2,
                                                      scope=plugin_manager.SettingScope.GLOBAL,
                                                      write_defaults=True)

        self.status_every_frames_setting = plugin_manager.Setting(
            self,
            'cancer.status_every_frames',
            default_value=10,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        self.time_before_status_setting = plugin_manager.Setting(
            self,
            'cancer.time_before_status',
            default_value=5,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        self.ed_channel_setting = plugin_manager.Setting(
            self,
            'cancer.ed_channel',
            default_value=None,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )

        self._sneeze = (-1, None)
        self.storage = main.PluginStorage(self, main.bot.storage)
        main.bot.handlers['chat_msg'].append(self.chan_msg_handler)

        self.random_ping_setting = plugin_manager.Setting(self,
                                                          'cancer.random_pings',
                                                          default_value=['{my pings run out}'],
                                                          scope=plugin_manager.SettingScope.GLOBAL,
                                                          write_defaults=True)

        self.pyramid_enabled_setting = plugin_manager.Setting(self,
                                                              'cancer.pyramid_enabled',
                                                              default_value=False,
                                                              scope=plugin_manager.SettingScope.PER_CHANNEL,
                                                              write_defaults=True)

        self.cookie_optin_setting = plugin_manager.Setting(self,
                                                           'cancer.cookie_optin',
                                                           default_value=[],
                                                           scope=plugin_manager.SettingScope.GLOBAL,
                                                           write_defaults=True)

        # register commands
        self.command_pyramid = main.bot.add_command('mb.pyramid', required_permissions=['cancer.pyramid'],
                                                    enable_local_bypass=True)(self.c_pyramid)
        plugin_help.add_manual_help_using_command('Make a pyramid out of an emote or text. '
                                                  'Usage: pyramid <size> <text...>',
                                                  None)(self.command_pyramid)

        self.command_braillefy = main.bot.add_command('braillefy', enable_local_bypass=True,
                                                      required_permissions=['cancer.braille'])(self.c_braillefy)
        plugin_help.add_manual_help_using_command('Convert an image into braille. '
                                                  'Usage: braillefy url:URL [+reverse] '
                                                  '[sensitivity_(r|g|b|a):FLOAT] [size_percent:FLOAT] '
                                                  '[max_x:INT (default 60)] [pad_y:INT (60)]',
                                                  None)(self.command_braillefy)

        # arguments.
        plugin_help.create_topic('braillefy url',
                                 'URL pointing to image you want to convert.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('braillefy reverse',
                                 'Should the output braille be reversed.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('braillefy sensitivity',
                                 'Per-channel sensitivity of the converter. r(ed), g(reen), b(lue), a(lpha)',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'braillefy sensitivity_r',
                                     'braillefy sensitivity_g',
                                     'braillefy sensitivity_b',
                                     'braillefy sensitivity_a'
                                 ])

        plugin_help.create_topic('braillefy size',
                                 'Size of the image. Defaults: max_x = 60, pad_y = 60, '
                                 'size_percent=[undefined]. max_x, pad_y are in pixels.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'braillefy size_percent',
                                     'braillefy max_x',
                                     'braillefy pad_y',
                                 ])

        self.c_cookie_optin = main.bot.add_command('cookie')(self.c_cookie_optin)
        plugin_help.add_manual_help_using_command('Add yourself to the list of people who will be reminded to eat '
                                                  'cookies', None)(self.c_cookie_optin)

        main.bot.schedule_repeated_event(0.1, 1, self.waytoodank_timer, (), {})

        plugin_help.create_topic('plugin_cancer',
                                 'Plugin dedicated to things that shouldn\'t be done '
                                 '(responding to messages other than commands, spamming).',
                                 section=plugin_help.SECTION_MISC,
                                 links=[
                                     'plugin_cancer.py',
                                     'cancer'
                                 ])

        plugin_help.create_topic('+ed',
                                 'The `cancer` plugin sends a message containing +ed every five minutes to '
                                 'activate HuwoBot.',
                                 section=plugin_help.SECTION_MISC,
                                 links=[
                                     'ed',
                                     'enterdungeon',
                                     '+enterdungeon'
                                 ])
        self.next_ed_time = 0
        main.bot.schedule_event(0.1, 1, self._enter_dungeon, (), {})

    def _enter_dungeon(self):
        if self.ed_channel is None:
            return
        if time.time() < self.next_ed_time:
            return
        msg = twitchirc.ChannelMessage('+ed', main.bot.username, self.ed_channel, outgoing=True, parent=main.bot)
        main.bot.send(msg)
        log('info', 'Queued enter dungeon message :)')
        self.next_ed_time = time.time() + 10 * 60 + 1

    def c_cookie_optin(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('cookie', msg, global_cooldown=60, local_cooldown=60)
        if cd_state:
            return
        if msg.user.lower() in self.cookie_optin:
            self.cookie_optin.remove(msg.user.lower())
            return f'@{msg.user} You have been removed from the cookie opt-in list.'
        else:
            self.cookie_optin.append(msg.user.lower())
            return f'@{msg.user} You have been added to the cookie opt-in list.'

    def c_pyramid(self, msg: twitchirc.ChannelMessage):
        if not self._get_pyramid_enabled(msg.channel):
            return f'@{msg.user}, This command is disabled here.'
        cd_state = main.do_cooldown('pyramid', msg, global_cooldown=60, local_cooldown=60)
        if cd_state:
            return
        t = main.delete_spammer_chrs(msg.text).split(' ', 1)
        if len(t) == 1:
            return f'@{msg.user}, Usage: pyramid <size> <text...>'
        args = t[1].rstrip()
        size = ''
        for arg in args.split(' '):
            arg: str
            if arg.isnumeric():
                size = arg
                break  # prefer first number!
        if size != '':
            args: str = args.replace(size, '', 1).rstrip() + ' '
            size = int(size)
            if not args.strip(' '):
                return f'@{msg.user}, Nothing to send. NaM'
            for i in range(1, size):
                main.bot.send(msg.reply(args * i))
            for i in range(size, 0, -1):
                main.bot.send(msg.reply(args * i))

    async def c_braillefy(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('braille', global_cooldown=0, local_cooldown=60, msg=msg)
        if cd_state:
            return
        try:
            args = arg_parser.parse_args(msg.text.split(' ', 1)[1], {
                'url': str,
                'sensitivity_r': float,
                'sensitivity_g': float,
                'sensitivity_b': float,
                'sensitivity_a': float,
                'size_percent': float,
                'max_y': int,
                'pad_y': int,
                'reverse': bool,
                'hastebin': bool
            }, strict_escapes=True, strict_quotes=True)
        except arg_parser.ParserError as e:
            return f'Error: {e.message}'
        missing_args = arg_parser.check_required_keys(args, ['url'])
        if missing_args:
            return (f'Error: You are missing the {",".join(missing_args)} '
                    f'argument{"s" if len(missing_args) > 1 else ""} to run this command.')

        num_defined = sum([args[f'sensitivity_{i}'] is not Ellipsis for i in 'rgb'])
        alpha = args['sensitivity_a'] if args['sensitivity_a'] is not Ellipsis else 1
        if num_defined == 3:
            sens: typing.Tuple[float, float, float, float] = (args['sensitivity_r'], args['sensitivity_g'],
                                                              args['sensitivity_b'], alpha)
            is_zero = bool(sum([args[f'sensitivity_{i}'] == 0 for i in 'rgba']))
            if is_zero:
                return f'Error: Sensitivity cannot be zero. MEGADANK'
        elif num_defined == 0:
            sens = (1, 1, 1, 1)
        else:
            return f'Error: you need to define either all sensitivity fields (r, g, b, a) or none.'
        if args['size_percent'] is not ... and args['max_y'] is not ...:
            return f'Error: you cannot provide the size percentage and maximum height at the same time.'

        max_x = 60 if args['size_percent'] is Ellipsis else None
        max_y = (args['max_y'] if args['max_y'] is not Ellipsis else 60) if args['size_percent'] is Ellipsis else None
        size_percent = None if args['size_percent'] is Ellipsis else args['size_percent']

        img = await braille.download_image(args['url'])
        img: Image.Image
        if img.format.lower() != 'gif':
            img, o = await braille.crop_and_pad_image(True,
                                                      img,
                                                      max_x,
                                                      max_y,
                                                      '',
                                                      (60,
                                                       args['pad_y'] if args['pad_y'] is not Ellipsis else 60),
                                                      size_percent)
            o += await braille.to_braille_from_image(img,
                                                     reverse=True if args['reverse'] is not Ellipsis else False,
                                                     size_percent=size_percent,
                                                     max_x=max_x,
                                                     max_y=max_y,
                                                     sensitivity=sens,
                                                     enable_padding=True,
                                                     pad_size=(60,
                                                               args['pad_y'] if args['pad_y'] is not Ellipsis else 60),
                                                     enable_processing=False)
        else:
            missing_permissions = main.bot.check_permissions(msg, ['cancer.braille.gif'],
                                                             enable_local_bypass=False)
            if missing_permissions:
                o = 'Note: missing permissions to convert a gif. \n'
            else:
                o = ''
                frame = -1
                start_time = time.time()
                while 1:
                    try:
                        img.seek(frame + 1)
                    except EOFError:
                        break
                    frame += 1
                    o += f'\nFrame {frame}\n'
                    frame_start = time.time()
                    o += await braille.to_braille_from_image(img.copy(),
                                                             reverse=True if args['reverse'] is not Ellipsis else False,
                                                             size_percent=size_percent,
                                                             max_x=max_x,
                                                             max_y=max_y,
                                                             sensitivity=sens,
                                                             enable_padding=True,
                                                             pad_size=(60,
                                                                       (args['pad_y'] if args['pad_y'] is not Ellipsis
                                                                        else 60)),
                                                             enable_processing=True)
                    time_taken = round(time.time() - start_time)
                    frame_time = round(time.time() - frame_start)

                    if frame % self.status_every_frames == 0 and time_taken > self.time_before_status:
                        speed = round(1 / frame_time)
                        main.bot.send(msg.reply(f'@{msg.user}, ppCircle Converted {frame} frames in '
                                                f'{time_taken} seconds, speed: {round(speed)} fps, '
                                                f'eta: {(img.n_frames - frame) * speed} seconds.'))
                        await asyncio.sleep(0)

        sendable = ' '.join(o.split('\n')[1:])
        if args['hastebin'] is not Ellipsis or len(sendable) > 500:
            return (f'{"This braille was too big to be posted." if not args["hastebin"] is not Ellipsis else ""} '
                    f'Here\'s a link to a hastebin: '
                    f'{plugin_hastebin.hastebin_addr}'
                    f'{await plugin_hastebin.upload(o)}')
        else:
            return sendable
