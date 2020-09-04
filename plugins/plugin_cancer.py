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
import datetime
import time
import unicodedata
import warnings
from typing import Tuple
import typing

import aiohttp
import regex
from PIL import Image, ImageFilter

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

main.load_file('plugins/plugin_emotes.py')
try:
    import plugin_emotes as plugin_emotes
except ImportError:
    from plugins.plugin_emotes import Plugin as PluginEmotes

    plugin_emotes: PluginEmotes

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
    'asd',
    f'Look, this cancerous feature is only {file_length} characters',
    f'Look, this cancerous feature is only {file_lines} lines',
    'FeelsGoodMan Clap spam',
    '🅱ing @{ping} PepeS',
    'NaM',
    'RECONNECTION DETECTED HONEYDETECTED',
    'HONEYDETECTED /',
    'Am I next in the queue to restart? PepeS',
    'FeelsJavascriptMan new changes?',
    f'Suggest more reconnection messages PagChomp {unicodedata.lookup("WHITE RIGHT POINTING BACKHAND INDEX")} _suggest',
    f'{unicodedata.lookup("EYES")} @{{executor}}',
    'HONEYDETECTED PRÓBA PONOWNEGO NAWIĄZANIA POŁĄCZENIA ZOSTAŁA ZAKOŃCZONA SUKCESEM',
]

COOKIE_PATTERN = regex.compile(
    r'^\[Cookies\] '
    r'\['
    r'(?P<rank>(?:P[1-4]: )?'
    r'(?:[dD]efault|[bB]ronze|[sS]ilver|[gG]old|[pP]latinum|[dD]iamond|[mM]asters|[gG]rand[mM]asters|[lL]eader)'
    r')\] '
    r'(?P<name>[a-z0-9_]+) '
    r'(?!you have already claimed)'
)
COOLDOWN_TIMEOUT = 1.5

PRESTIGE_PATTERN = regex.compile('P([1-4]):')
COOKIE_PRESTIGE_TIMES = {
    0: 2 * 60 * 60,
    1: 75 * 60,
    2: 50 * 60,
    3: 45 * 60,

    # 0: '2h',
    # 1: '1h',
    # 2: '30m',
    # 3: '20m'
}


class Plugin(main.Plugin):
    _sneeze: Tuple[float, typing.Optional[twitchirc.ChannelMessage]]

    def _time_from_rank(self, text) -> int:
        prestige_match = PRESTIGE_PATTERN.findall(text)
        if prestige_match:
            level = int(prestige_match[0])
            if level in COOKIE_PRESTIGE_TIMES:
                return COOKIE_PRESTIGE_TIMES[level]
            else:
                log('warn', f'Unknown prestige level: {level!r}. Message {text!r}')
                return COOKIE_PRESTIGE_TIMES[0]
        else:
            return COOKIE_PRESTIGE_TIMES[0]

    def waytoodank_timer(self):
        if self._sneeze[0] <= time.time() and self._sneeze[1] is not None:
            main.bot.send(self._sneeze[1].reply('WAYTOODANK'))
            self._sneeze = (-1, None)

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

    def _get_pyramid_enabled(self, channel: str):
        return plugin_manager.channel_settings[channel].get(self.pyramid_enabled_setting) is True

    def __init__(self, module, source):
        super().__init__(module, source)
        warnings.simplefilter('error', Image.DecompressionBombWarning)

        self._sneeze = (-1, None)
        self.storage = main.PluginStorage(self, main.bot.storage)

        # region Settings
        self.timeout_setting = plugin_manager.Setting(
            self,
            'cancer.waytoodank_timeout',
            default_value=1.2,
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        self.random_ping_setting = plugin_manager.Setting(
            self,
            'cancer.random_pings',
            default_value=['{my pings run out}'],
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )

        self.pyramid_enabled_setting = plugin_manager.Setting(
            self,
            'cancer.pyramid_enabled',
            default_value=False,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Toggles if the mb.pyramid command is enabled in the channel.'
        )

        self.cookie_optin_setting = plugin_manager.Setting(
            self,
            'cancer.cookie_optin',
            default_value=[],
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
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
        # endregion

        # region Schedule events
        main.bot.schedule_repeated_event(0.1, 1, self.waytoodank_timer, (), {})
        # endregion

        # region Register commands
        self.c_cookie_optin = main.bot.add_command('cookie')(self.c_cookie_optin)
        self.command_pyramid = main.bot.add_command('mb.pyramid', required_permissions=['cancer.pyramid'],
                                                    enable_local_bypass=True)(self.c_pyramid)

        self.command_braillefy = main.bot.add_command('braillefy', enable_local_bypass=True,
                                                      required_permissions=['cancer.braille'])(self.c_braillefy)

        # region Fake Commands
        self._honeydetected = main.bot.add_command('honydetected reconnected')(self._honeydetected)
        self._honeydetected.matcher_function = (
            lambda msg, cmd: (
                    msg.user in ['supibot', 'mm2pl']
                    and (
                            msg.text.startswith('HONEYDETECTED RECONNECTED')
                            or msg.text.startswith(f'pepeL {unicodedata.lookup("MICROSCOPE")}')
                    )
                    and msg.channel in ['supinic', 'mm2pl']
            )
        )

        self._cookie = main.bot.add_command('cookie detection')(self._cookie)
        self._cookie.matcher_function = (
            lambda msg, cmd: (msg.channel in ['supinic', 'mm2pl']
                              and msg.user in ['thepositivebot', 'mm2pl']
                              and msg.text.startswith('\x01ACTION [Cookies]'))
        )
        self._ps_sneeze_cancel = main.bot.add_command('ps sneeze cancel')(self._ps_sneeze_cancel)
        self._ps_sneeze_cancel.matcher_function = (
            lambda msg, cmd: (
                    msg.user == 'supibot' and self._sneeze[1] is not None
                    and (
                            msg.text.startswith(self._sneeze[1].user + ', The playsound\'s cooldown has not passed '
                                                                       'yet! Try again in')
                            or msg.text.startswith(self._sneeze[1].user + ', Playsounds are currently disabled!')
                    )
            )
        )
        self._ps_sneeze_init = main.bot.add_command('ps sneeze init')(self._ps_sneeze_init)
        self._ps_sneeze_init.limit_to_channels = ['supinic', 'mm2pl']
        self._ps_sneeze_init.matcher_function = (
            lambda msg, cmd: (
                msg.text.startswith('$ps sneeze')
            )
        )
        self.c_asd = main.bot.add_command('asd')(self.c_asd)
        self.c_asd.limit_to_channels = ['simon36']
        self.c_asd.matcher_function = (
            lambda msg, cmd: (
                msg.text.startswith('asd')
            )
        )
        # endregion
        # endregion

        # region Help
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

        plugin_help.create_topic('plugin_cancer',
                                 'Plugin dedicated to things that shouldn\'t be done '
                                 '(responding to messages other than commands, spamming).',
                                 section=plugin_help.SECTION_MISC,
                                 links=[
                                     'plugin_cancer.py',
                                     'cancer'
                                 ])
        plugin_help.add_manual_help_using_command('Add yourself to the list of people who will be reminded to eat '
                                                  'cookies', None)(self.c_cookie_optin)
        plugin_help.add_manual_help_using_command('Make a pyramid out of an emote or text. '
                                                  'Usage: pyramid <size> <text...>',
                                                  None)(self.command_pyramid)
        plugin_help.add_manual_help_using_command('Convert an image into braille. '
                                                  'Usage: braillefy (url:URL|emote:EMOTE) [+reverse] '
                                                  '[sensitivity_(r|g|b|a):float] [size_percent:float] '
                                                  '[max_x:int] [pad_y:int]',
                                                  None)(self.command_braillefy)
        # endregion

    async def _ps_sneeze_init(self, msg: twitchirc.ChannelMessage):
        self._sneeze = (time.time() + self.cooldown_timeout, msg)

    async def _ps_sneeze_cancel(self, msg: twitchirc.ChannelMessage):
        # don't respond if the playsound didn't play
        self._sneeze = (-1, None)

    async def _cookie(self, msg: twitchirc.ChannelMessage):
        m = COOKIE_PATTERN.findall(main.delete_spammer_chrs(msg.text.replace('\x01ACTION ', '')))
        print(msg.user, m)
        if m and m[0][1].lower() in self.cookie_optin:
            time_ = self._time_from_rank(msg.text)
            print(time_)
            print('cookie opt in okay')

            params = {
                'username': m[0][1].lower(),
                'text': 'Cookie :)',
                'schedule': (
                        (
                                datetime.datetime.utcnow() + datetime.timedelta(seconds=time_)
                        ).isoformat() + 'Z'
                ),
                'private': 1,
            }
            print(params)
            async with (await main.supibot_api.request('post /bot/reminder/',
                                                       params=params)) as r:
                print(f'request {r}')
                j = await r.json()
                print(j)
                if r.status == 200:
                    main.bot.send(msg.reply(f'@{m[0][1].lower()}, I set up a cookie reminder for you :), '
                                            f'id: {j["data"]["reminderID"]}'))
                else:
                    main.bot.send(msg.reply(f'@{m[0][1].lower()}, monkaS {chr(0x1f6a8)}'
                                            f'failed to create cookie reminder '))

        elif not m:
            log('warn', f'matching against regex failed: {msg.text!r}')

    async def _honeydetected(self, msg: twitchirc.ChannelMessage):
        if msg.text.startswith('pepeL'):  # new reconnection message
            return f'ppL {unicodedata.lookup("KEYBOARD")}'
        random_msg = random.choice(RECONNECTION_MESSAGES)
        random_msg = random_msg.replace('{executor}', msg.user)
        while '{ping}' in random_msg:
            random_msg = random_msg.replace('{ping}', random.choice(self.random_pings), 1)
        return random_msg

    def c_cookie_optin(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('cookie', msg, global_cooldown=60, local_cooldown=60)
        if cd_state:
            return
        if msg.user.lower() in self.cookie_optin:
            self.cookie_optin.remove(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with main.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user} You have been removed from the cookie opt-in list.'
        else:
            self.cookie_optin.append(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with main.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user} You have been added to the cookie opt-in list.'

    async def c_pyramid(self, msg: twitchirc.ChannelMessage):
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
            output = []
            for i in range(1, size):
                output.append(args * i)
            for i in range(size, 0, -1):
                output.append(args * i)
            return output

    def c_asd(self, msg):
        return 'NaM !!!'

    async def c_braillefy(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('braille', global_cooldown=0, local_cooldown=60, msg=msg)
        if cd_state:
            return
        try:
            args = arg_parser.parse_args(
                msg.text.split(' ', 1)[1],
                {
                    'url': str,
                    'emote': str,
                    'sensitivity_r': float,
                    'sensitivity_g': float,
                    'sensitivity_b': float,
                    'sensitivity_a': float,
                    'size_percent': float,
                    'max_y': int,
                    'pad_x': int,
                    'reverse': bool,
                    'hastebin': bool,
                    'sobel': bool
                },
                strict_escapes=True,
                strict_quotes=True
            )
        except arg_parser.ParserError as e:
            return f'Error: {e.message}'

        missing_args = []
        if args['url'] is ... and args['emote'] is ...:
            missing_args.append('url or emote')
        if missing_args:
            return (f'Error: You are missing the {",".join(missing_args)} '
                    f'argument{"s" if len(missing_args) > 1 else ""} to run this command.')

        if args['url'] is not ... and args['emote'] is not ...:
            return f'@{msg.user}, cannot provide both an emote name and a url.'

        num_defined = sum([args[f'sensitivity_{i}'] is not Ellipsis for i in 'rgb'])
        alpha = args['sensitivity_a'] if args['sensitivity_a'] is not Ellipsis else 1
        if num_defined == 3:
            sens: typing.Tuple[float, float, float, float] = (args['sensitivity_r'], args['sensitivity_g'],
                                                              args['sensitivity_b'], alpha)
            is_zero = bool(sum([args[f'sensitivity_{i}'] == 0 for i in 'rgba']))
            if is_zero:
                return f'Error: Sensitivity cannot be zero. MEGADANK'
        elif num_defined == 0:
            sens = (2, 2, 2, 1)
        else:
            return f'Error: you need to define either all sensitivity fields (r, g, b, a) or none.'
        if args['size_percent'] is not ... and args['max_y'] is not ...:
            return f'Error: you cannot provide the size percentage and maximum height at the same time.'

        max_x = 60 if args['size_percent'] is Ellipsis else None
        max_y = (args['max_y'] if args['max_y'] is not Ellipsis else 60) if args['size_percent'] is Ellipsis else None
        size_percent = None if args['size_percent'] is Ellipsis else args['size_percent']

        url = args['url'] if args['url'] is not ... else None
        if url and url.startswith('file://'):
            return f'@{msg.user}, you can\'t do this BabyRage'

        if args['emote'] is not ...:
            channel_id = None
            if isinstance(msg, twitchirc.ChannelMessage):
                channel_id = msg.flags['room-id']
            emote = args['emote']
            if emote.startswith('#') and emote.count(':') == 1:
                channel, emote = emote.split(':')
                channel = channel.lstrip('#')
                users = main.User.get_by_name(channel)
                if users:
                    u = users[0]
                    channel_id = u.twitch_id
                else:
                    async with aiohttp.request('get', f'https://api.ivr.fi/twitch/resolve/{channel}') as req:
                        if req.status == 404:
                            return f'@{msg.user}, {channel}: channel not found'
                        data = await req.json()
                        channel_id = data['id']

            emote_found = await plugin_emotes.find_emote(emote, channel_id=channel_id)
            if emote_found:
                url = emote_found.get_url('3x')
            else:
                return f'@{msg.user}, Invalid url, couldn\'t find an emote matching this.'

        img = await braille.download_image(url)
        img: Image.Image
        if img.format.lower() != 'gif':
            o = await self._single_image_to_braille(args, img, max_x, max_y, sens, size_percent)
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
                    o = await self._single_image_to_braille(args, img, max_x, max_y, sens, size_percent)
                    time_taken = round(time.time() - start_time)
                    frame_time = time.time() - frame_start
                    if frame_time > 1:
                        frame_time = round(frame_time)  # avoid division by zero

                    if frame % self.status_every_frames == 0 and time_taken > self.time_before_status:
                        speed = round(1 / frame_time, 1)
                        speed_msg = (f'@{msg.user}, Converted {frame} frames in '
                                     f'{time_taken} seconds, speed: {speed} fps, '
                                     f'eta: {(img.n_frames - frame) * speed} seconds.')
                        if main.check_spamming_allowed(msg.channel):
                            await main.bot.send(msg.reply(speed_msg))
                        else:
                            if frame % (self.status_every_frames * 2) == 0:
                                await main.bot.send(msg.reply_directly(speed_msg))
                        await asyncio.sleep(0)

        sendable = ' '.join(o.split('\n')[1:])
        if args['hastebin'] is not Ellipsis or len(sendable) > 500:
            return (f'{"This braille was too big to be posted." if not args["hastebin"] is not Ellipsis else ""} '
                    f'Here\'s a link to a hastebin: '
                    f'{plugin_hastebin.hastebin_addr}'
                    f'{await plugin_hastebin.upload(o)}')
        else:
            return sendable

    async def _single_image_to_braille(self, args, img, max_x, max_y, sens, size_percent):
        img, o = await braille.crop_and_pad_image(
            False,
            img,
            max_x,
            max_y,
            '',
            (60, 60),
            size_percent
        )
        if args['sobel'] is not ... and args['sobel']:
            img = img.filter(ImageFilter.FIND_EDGES)
        o += await braille.to_braille_from_image(
            img,
            reverse=True if args['reverse'] is not Ellipsis else False,
            size_percent=size_percent,
            max_x=max_x,
            max_y=max_y,
            sensitivity=sens,
            enable_padding=False,
            pad_size=(60, 60),
            enable_processing=False
        )
        return o
