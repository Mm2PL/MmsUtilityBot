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
        api_url = f'https://{lang.iso6391}.wikipedia.org/w/api.php'

        async with aiohttp.request(
                'get', api_url,
                params={
                    'action': 'opensearch',
                    # 'profile': 'fuzzy',
                    'limit': 10,
                    'search': args[1]
                }
        ) as req:
            data = await req.json()
            print(repr(data))
            articles = data[1]
            best_matching = articles[0]
        async with aiohttp.request(
                'get', api_url,
                params={
                    'action': 'query',
                    'format': 'json',
                    'prop': 'extracts',
                    'redirects': '1',
                    'exchars': 1200,
                    'exintro': 0,
                    'exlimit': 1,
                    'explaintext': 1,
                    'titles': best_matching
                }
        ) as req:
            data = await req.json()
            print(repr(data))
            pages = data['query']['pages']
            page = pages[list(pages.keys())[0]]
            extract = page['extract']

        out = f'@{msg.user}, https://{lang.iso6391}.wikipedia.org/?curid={page["pageid"]} {extract}'
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
