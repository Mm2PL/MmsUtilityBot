#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms1 of the GNU General Public License as published by
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
import dataclasses
from typing import List, Optional

import aiohttp

import util_bot.languages
from plugins.utils import arg_parser

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugin_help

NAME = 'wiki'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': []
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    no_reload = False
    name = NAME
    commands = []

    def __init__(self, module, source):
        super().__init__(module, source)
        self.command_wiki = util_bot.bot.add_command(
            'wiki',
        )(self.command_wiki)
        plugin_help.add_manual_help_using_command(
            'Search Wikipedia. Usage: wiki "<search text>" [lang:language name]'
        )(self.command_wiki)

    async def command_wiki(self, msg: util_bot.StandardizedMessage):
        try:
            args = arg_parser.parse_args(
                msg.text,
                {
                    'lang': util_bot.LanguageData.get_by_name_or_code,
                    1: str,
                },
                defaults={
                    'lang': util_bot.LanguageData.get_by_name_or_code('english')
                }
            )
        except arg_parser.ParserError as e:
            return f'@{msg.user}, {e.message}'
        if not args.get(1):
            return f'@{msg.user}, Usage: wiki "<search text>" [lang:language name]'
        lang: util_bot.LanguageData = args['lang']
        assert lang.iso6391.isalpha(), 'Arbitrary url injection attempt?'
        wiki = MediaWikiAPI(f'https://{lang.iso6391}.wikipedia.org')
        articles = await wiki.opensearch(args[1])
        best_matching = articles[0]
        article = await wiki.get_article(best_matching)

        out = f'@{msg.user}, {article.html_url()} {article.extract}'
        return self._clip_message(
            out,
            (499 - len('/w  ') - len(msg.user)) if isinstance(msg, util_bot.StandardizedWhisperMessage)
            else 499
        )

    def _clip_message(self, text: str, length: int) -> str:
        output = ''
        for i, word in enumerate(text.split(' ')):
            if len(output) + len(word) >= length - 3:
                output += '...'
                break
            if i == 0:
                output = word
            else:
                output += ' ' + word
        return output


class MediaWikiAPI:
    def __init__(self, base_url):
        self.base_url = base_url

    @property
    def api_url(self):
        return self.base_url + '/w/api.php'

    async def opensearch(self, search: str, limit=10) -> List[str]:
        """
        Search this MediaWiki instance

        :return: Article names as strings
        """
        async with aiohttp.request(
                'get', self.api_url,
                params={
                    'action': 'opensearch',
                    # 'profile': 'fuzzy',
                    'limit': limit,
                    'search': search
                }
        ) as req:
            data = await req.json()
            print(repr(data))
            articles = data[1]
            return articles

    async def get_article(self, title: str) -> 'MediaWikiArticle':
        async with aiohttp.request(
                'get', self.api_url,
                params={
                    'action': 'query',
                    'format': 'json',
                    'prop': 'extracts',
                    'redirects': '1',
                    'exchars': 1200,
                    'exintro': 0,
                    'exlimit': 1,
                    'explaintext': 1,
                    'titles': title
                }
        ) as req:
            data = await req.json()
            print(repr(data))
            pages = data['query']['pages']
            page = pages[list(pages.keys())[0]]
            return MediaWikiArticle.from_json(page, self)


@dataclasses.dataclass
class MediaWikiArticle:
    pageid: int
    ns: int
    title: str
    extract: Optional[str]
    wiki_api: MediaWikiAPI

    @classmethod
    def from_json(cls, data, wiki_api):
        return cls(
            **data,
            wiki_api=wiki_api
        )

    def html_url(self):
        return f'{self.wiki_api.base_url}?curid={self.pageid}'
