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
import asyncio
import typing

import aiohttp
import regex
# noinspection PyUnresolvedReferences
import twitchirc

import util_bot

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_help as plugin_help
    else:
        raise

import youtube_dl

NAME = 'clip_info'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    name = NAME
    commands = []
    no_reload = False

    CLIP_PATTERN = regex.compile(
        r'https?://clips\.twitch\.tv/(?P<slug>[a-zA-Z0-9]+)'
        r'|https?://www.twitch.tv/[^ /]+/clip/(?P<slug2>[a-zA-Z0-9]+)(\?.+)?'
    )

    def __init__(self, module, source):
        super().__init__(module, source)
        self.c_clip_info = util_bot.bot.add_command('clipinfo')(self.clip_info)

    @property
    def on_reload(self):
        return super().on_reload

    def _extract(self, url: str):
        extractor = youtube_dl.extractor.TwitchClipsIE()

        try:
            data = extractor.extract(url)
        except youtube_dl.utils.ExtractorError as e:
            return 'error'

        if 'formats' in data:
            best = data['formats'][-1]  # formats are sorted as worst to best
            return best['url']
        return None

    async def clip_info(self, msg: util_bot.StandardizedMessage):
        if util_bot.do_cooldown('clipinfo', msg):
            return
        argv = msg.text.split(' ')
        if len(argv) < 2:
            if argv:
                return f'@{msg.user}, {plugin_help.find_topic("clipinfo", plugin_help.SECTION_COMMANDS)}'
        match = self.CLIP_PATTERN.findall(' '.join(argv))
        if not match:
            return f'@{msg.user}, no clip links found :('

        if len(match) > 1:
            return f'@{msg.user}, too many clip links found'

        result = await asyncio.get_event_loop().run_in_executor(None, self._extract, match[0][0] or match[0][1])
        if result == 'error':
            return f'@{msg.user}, error :('
        elif result is None:
            return f'@{msg.user}, extractor returned no urls'
        else:
            return f'@{msg.user}, {result}'
