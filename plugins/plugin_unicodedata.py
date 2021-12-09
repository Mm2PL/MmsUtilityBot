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

# noinspection PyUnresolvedReferences
import typing
import unicodedata

import util_bot
from plugins.utils import arg_parser

try:
    import plugin_hastebin
except ImportError:
    import plugins.plugin_hastebin as plugin_hastebin_module

    plugin_hastebin: plugin_hastebin_module.Plugin
    exit(1)
try:
    import plugin_chat_cache
except ImportError:
    import plugins.plugin_chat_cache as plugin_chat_cache_module

    plugin_chat_cache: plugin_chat_cache_module.Plugin
    exit(1)

NAME = 'unicodedata'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': []
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    commands = ['unicode']
    name = NAME
    no_reload = False

    def __init__(self, module, source):
        super().__init__(module, source)
        self.command_unicode = util_bot.bot.add_command(
            'unicode',
            cooldown=util_bot.CommandCooldown(1, 0, 0)  # prevent vip spam and that's it
        )(self.command_unicode)

    def _explain_char(self, ch, further):
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = f'[U+{hex(ord(ch))[2:]}]'
        if not further:
            return name + f'({ch})'
        infos = {
            'category': unicodedata.category(ch),
            'direction': unicodedata.bidirectional(ch),
            'east asian width': unicodedata.east_asian_width(ch)
        }

        decomposition = unicodedata.decomposition(ch)
        if decomposition:
            infos['decomposition'] = decomposition

        try:
            infos['digit value'] = unicodedata.digit(ch)
        except ValueError:
            pass
        try:
            infos['decimal value'] = unicodedata.decimal(ch)
        except ValueError:
            pass
        try:
            infos['numeric value'] = unicodedata.numeric(ch)
        except ValueError:
            pass
        comb = unicodedata.combining(ch)
        if comb != 0:
            infos['combining class'] = str(comb)

        mirrored = unicodedata.mirrored(ch)
        if mirrored:
            infos['mirrored'] = 'yes'
        if hasattr(unicodedata, 'is_normalized'):
            forms = []
            for form in ('NFC', 'NFD', 'NFKC', 'NFKD'):
                if unicodedata.is_normalized(form, ch):
                    forms.append(form)
            if forms:
                infos['normalized'] = f'yes: {", ".join(forms)}'
            else:
                infos['normalized'] = 'no'
        else:
            infos['normalized'] = 'unavailable'

        info = ', '.join([
            f'{k}: {v}'
            for k, v in infos.items()
        ])
        return f'{name}: {ch!r} ({info})'

    async def command_unicode(self, msg: util_bot.StandardizedMessage) \
            -> typing.Union[str, typing.Tuple[util_bot.CommandResult, str]]:
        txt = msg.text.split(' ', 1)
        if len(txt) < 2:
            return (util_bot.CommandResult.OTHER_FAILED,
                    f'Usage: unicode <bunch of characters> [--verbose]')
        try:
            args = arg_parser.parse_args(
                txt[1],
                {
                    'user': str,
                    'verbose': bool,
                    arg_parser.POSITIONAL: str,
                },
                strict_escapes=False,
                strict_quotes=False,
                ignore_arg_zero=True,
                defaults={
                    'verbose': False,
                    'user': None
                }
            )
        except arg_parser.ParserError as e:
            return f'@{msg.user}, {e.message}'
        text = ' '.join(map(lambda pair: pair[1], filter(lambda pair: isinstance(pair[0], int), args.items())))
        if args['user']:
            last_messages = plugin_chat_cache.find_messages(
                msg.channel,
                user=args['user'].strip('@,').lower()
            )
            if len(last_messages) == 0 or (args['user'] == msg.user and len(last_messages) < 2):
                return (util_bot.CommandResult.OTHER_FAILED,
                        f'@{msg.user}, User has no known recent messages.')
            if args['user'] == msg.user:
                text = last_messages[-2].text
            else:
                text = last_messages[-1].text

        explained = [self._explain_char(i, False) for i in text]
        out = ', '.join(explained)

        post = False
        why_post = ''
        if len(out) + len(msg.user) + 3 >= 499:
            why_post = 'Message was too long to fit. '
            post = True
        if args['verbose']:
            why_post = ''
            post = True

        if post:
            # message too long
            slug = await plugin_hastebin.upload('\n'.join([self._explain_char(ch, True) for ch in text]))
            return (f'@{msg.user}, {why_post}Here is a hastebin: '
                    f'{plugin_hastebin.hastebin_addr}{slug}')
        elif len(text) == 1:
            return f'@{msg.user}, {self._explain_char(text[0], True)}'
        else:
            return f'@{msg.user}, {out}'
