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
import abc
import typing

import aiohttp

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'emotes'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.bttv = BttvEmoteCache()
        self.ffz = FFZEmoteCache()
        self.twitch = TwitchEmoteCache()

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

    async def find_emote(self, name, channel_id: str = None) -> typing.Optional['Emote']:
        if channel_id is not None:
            try:
                return await self.bttv.find_channel_emote(name, channel_id)
            except KeyError:
                pass
            try:
                return await self.ffz.find_channel_emote(name, channel_id)
            except KeyError:
                pass
        try:
            return await self.bttv.find_global_emote(name)
        except KeyError:
            pass
        try:
            return await self.ffz.find_global_emote(name)
        except KeyError:
            pass
        try:
            return await self.twitch.find_global_emote(name)
        except KeyError:
            pass


class Emote:
    def __init__(self, name: str, url: str, id_: str, urls=None, **kwargs):
        if urls is None:
            urls = {}
        self.urls = urls
        self.name = name
        self.url = url
        self.id_ = id_
        self.other_data = kwargs

    def get_url(self, size: str):
        if size in self.urls:
            return self.urls[size]
        return self.url.format(size)

    def __repr__(self):
        return f'<Emote: {self.name}>'


class EmoteCache(abc.ABC):
    def __init__(self):
        self.channels = {}
        self.globals = {}

    async def find_global_emote(self, name: str) -> Emote:
        if not self.globals:
            await self.load_globals()

        return self.globals[name]

    async def find_channel_emote(self, name: str, channel_id: str) -> Emote:
        if channel_id not in self.channels:
            await self.load_channel(channel_id)

        return self.channels[channel_id][name]

    @abc.abstractmethod
    async def load_globals(self):
        pass

    @abc.abstractmethod
    async def load_channel(self, channel_id: str):
        pass


class BttvEmoteCache(EmoteCache):
    def __init__(self):
        super().__init__()
        self.global_url = 'https://api.betterttv.net/3/cached/emotes/global'
        self.channel_url = 'https://api.betterttv.net/3/cached/users/twitch/{}'
        self.emote_url = 'https://cdn.betterttv.net/emote/{id}/{size}'

    def _parse_emote(self, emote: dict, channel=False) -> Emote:
        if channel:
            return Emote(emote['code'], self.emote_url.format(id=emote['id'], size='{}'), emote['id'],
                         image_type=emote['imageType'], user=emote['user'])
        else:
            return Emote(emote['code'], self.emote_url.format(id=emote['id'], size='{}'), emote['id'],
                         image_type=emote['imageType'], user_id=emote['userId'])

    def _parse_globals(self, global_emotes: dict):
        output = {}
        for emote in global_emotes:
            e = self._parse_emote(emote)
            output[e.name] = e
        return output

    def _parse_channel_emotes(self, channel_emotes: dict):
        emotes = {}
        for emote in channel_emotes['channelEmotes']:
            e = self._parse_emote(emote)
            emotes[e.name] = e

        for emote in channel_emotes['sharedEmotes']:
            e = self._parse_emote(emote, channel=True)
            emotes[e.name] = e
        return emotes

    async def load_globals(self):
        async with aiohttp.request('get', self.global_url) as r:
            log('info', f'Loaded BTTV global emotes, status {r.status}')
            if r.status == 200:
                self.globals = self._parse_globals(await r.json())
            else:
                log('error', f'Bad status: {r.status}\n'
                             f'{r.content}')

    async def load_channel(self, channel_id: str):
        async with aiohttp.request('get', self.channel_url.format(channel_id)) as r:
            log('info', f'Loaded BTTV channel emotes for channel id {channel_id!r}, status {r.status}')
            if r.status == 200:
                self.channels[channel_id] = self._parse_channel_emotes(await r.json())
            else:
                log('error', f'Bad status: {r.status}\n'
                             f'{r.content}')


class FFZEmoteCache(EmoteCache):
    def __init__(self):
        super().__init__()
        self.global_url = 'https://api.frankerfacez.com/v1/set/global'
        self.channel_url = 'https://api.frankerfacez.com/v1/room/id/{}'

    # noinspection PyMethodMayBeStatic
    def _parse_emotes(self, source: dict):
        emotes = {}
        for emote_set in source['sets'].values():
            for emote in emote_set['emoticons']:
                print(emote)
                emote['urls'] = {int(k): v for k, v in emote['urls'].items()}
                e = Emote(emote['name'], 'https:' + (emote['urls'][max(emote['urls'].keys())]), emote['id'],
                          modifier=emote['modifier'], hidden=emote['hidden'],
                          urls={k: 'http:' + v for k, v in emote['urls'].items()})
                emotes[e.name] = e
        return emotes

    async def load_globals(self):
        async with aiohttp.request('get', self.global_url) as r:
            log('info', f'Loaded FFZ global emotes, status {r.status}')
            if r.status == 200:
                self.globals = self._parse_emotes(await r.json())
            else:
                log('error', f'Bad status: {r.status}\n'
                             f'{r.content}')

    async def load_channel(self, channel_id: str):
        async with aiohttp.request('get', self.channel_url.format(channel_id)) as r:
            log('info', f'Loaded FFZ channel emotes for channel id {channel_id!r}, status {r.status}')
            if r.status == 200:
                self.channels[channel_id] = self._parse_emotes(await r.json())
            elif r.status == 203:
                self.channels[channel_id] = []
            else:
                log('error', f'Bad status: {r.status}\n'
                             f'{r.content}')


class TwitchEmoteCache(EmoteCache):
    async def load_globals(self):
        async with aiohttp.request('get', self.global_url) as r:
            log('info', f'Loaded Twitch global emotes (emote set 0) with status {r.status}')
            data = await r.json()
            for e in data['emotes']:
                e['channel'] = data['channel']
                e['channelid'] = data['channelid']
                e['channellogin'] = data['channellogin']
                e['tier'] = data['tier']
                self.globals[e] = self._parse_emote(e)

    async def load_channel(self, channel_id: str):
        # twitch has no channel emotes
        pass

    def __init__(self):
        super().__init__()
        self.channel_url = 'https://api.ivr.fi/twitch/emotes/{}'
        self.global_url = 'https://api.ivr.fi/twitch/emoteset/0'

    async def find_global_emote(self, name: str) -> typing.Optional[Emote]:
        if name in self.globals:
            log('info', f'Using cached Twitch global emote {name!r}')
            return self.globals[name]

        async with aiohttp.request('get', self.channel_url.format(name)) as r:
            log('info', f'Tried loading Twitch global emote {name!r} with status {r.status}')
            if r.status == 404:
                self.globals[name] = None
                return

            self.globals[name] = self._parse_emote(await r.json())
            return self.globals[name]

    async def find_channel_emote(self, name: str, channel_id: str):
        return

    def _parse_emote(self, data: dict):
        return Emote(data['emotecode'], data.get('emoteurl_3x') or data.get('url'), data['emoteid'], {
            '1x': data['emoteurl_1x'],
            '2x': data['emoteurl_2x'],
            '3x': data['emoteurl_3x'] or data.get('url')
        }, **data)
