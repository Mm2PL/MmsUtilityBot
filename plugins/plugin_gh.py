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
import regex

import util_bot

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)

NAME = 'gh'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': []
}
log = util_bot.make_log_function(NAME)

ISSUE_PATTERN = regex.compile(
    r'(?:\b|^)([^ #:.]*[^/ ])'
    r'(?:'
    + (
        r'#(?P<issue>\d+)'
        r'|@(?P<commit>[a-zA-Z0-9~^]{4,40})'
    )
    + r')'
    + r'(?:\b|$)'
)
CVE_PATTERN = regex.compile(
    r'(?:\b|^)(?P<cve>CVE)-(?P<year>\d{4})-(?P<number>\d{4,})'
)
REPO_MAP = {
    'chatterino1': 'fourtf/Chatterino',
    'chatterino2': 'Chatterino/Chatterino2',

    'c1': 'fourtf/Chatterino',
    'c2': 'Chatterino/Chatterino2',
    'ch1': 'fourtf/Chatterino',
    'ch2': 'Chatterino/Chatterino2',
    'd2': 'Mm2PL/chatterino2',

    'c2a': 'Chatterino/api',
    'c2api': 'Chatterino/api',

    'c2wiki': 'chatterino/wiki',
    'ch2wiki': 'chatterino/wiki',
    'c2w': 'chatterino/wiki',

    'pajbot': 'pajbot/pajbot',
    'pajbot1': 'pajbot/pajbot',
    'pajbot2': 'pajbot/pajbot2',
    'pajbot3': 'pajbot/pajbot3',

    'pb': 'pajbot/pajbot',
    'pb1': 'pajbot/pajbot',
    'pb2': 'pajbot/pajbot2',
    'pb3': 'pajbot/pajbot3',

    'mm_sutilitybot': 'Mm2PL/MmsUtilityBot',
    'mmsbot': 'Mm2PL/MmsUtilityBot',

    'spm': 'Supinic/supibot-package-manager',
    'supinic.com': 'Supinic/supinic.com',
    'supi-core': 'Supinic/supi-core',
    'supicore': 'Supinic/supi-core',
    'supibot': 'Supinic/supibot',
    'dankerino': 'Mm2PL/chatterino2',
    'dankchat': 'flex3r/DankChat',
    'dc': 'flex3r/DankChat',
}
ISSUE_LINK_FORMAT = 'https://github.com/{repo}/issues/{id}'
COMMIT_LINK_FORMAT = 'https://github.com/{repo}/commit/{hash}'


class Plugin(util_bot.Plugin):
    no_reload = False
    name = NAME
    commands = []

    @property
    def issue_linker_optin(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(
            self.issue_linker_optin_setting)

    def _issuelinker_enabled_setting_on_load(self, channel_settings: plugin_manager.ChannelSettings):
        is_enabled = channel_settings.get(self.issuelinker_enabled_setting)
        username = channel_settings.channel.last_known_username
        if is_enabled and username not in self._issue_linker_channels:
            self._issue_linker_channels.append(username)
        elif not is_enabled and username in self._issue_linker_channels:
            self._issue_linker_channels.remove(username)

    def __init__(self, module, source):
        super().__init__(module, source)
        self._issue_linker_channels = []
        self.issue_linker_optin_setting = plugin_manager.Setting(
            self,
            'cancer.issue_linker_optin',
            default_value=[],
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )

        self.issuelinker_enabled_setting = plugin_manager.Setting(
            self,
            'cancer.issuelinker_enabled',
            default_value=False,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Toggles if the issue linker is enabled in the channel. Also requires user opt-in. '
                  'See _help issuelinker.',
            on_load=self._issuelinker_enabled_setting_on_load
        )

        self.c_issue_optin = util_bot.bot.add_command(
            'issuelinker',
            cooldown=util_bot.CommandCooldown(10, 5, 0)
        )(self.c_issue_optin)
        self.c_issue_optin.limit_to_channels = self._issue_linker_channels  # ref
        plugin_help.add_manual_help_using_command('Add yourself to the list of people who will have links issue '
                                                  'posted when an issue is mentioned. Format is '
                                                  r'(owner/repo|repo_alias)#issue_number. '
                                                  r'CVE-year-number is also linked.'
                                                  'Usage: issuelinker',
                                                  None)(self.c_issue_optin)

        self.c_link_issue = util_bot.bot.add_command(
            'issue link detection',
            cooldown=util_bot.CommandCooldown(5, 1, 0)  # 1s channel cooldown to avoid bots triggering it
        )(self.c_link_issue)
        self.c_link_issue.limit_to_channels = self._issue_linker_channels  # ref
        self.c_link_issue.matcher_function = (
            lambda msg, cmd: (
                    ('#' in msg.text or '@' in msg.text) and ISSUE_PATTERN.search(msg.text)
                    or ('CVE-' and CVE_PATTERN.search(msg.text))
            )
        )

    async def c_link_issue(self, msg: util_bot.StandardizedMessage):
        if msg.user not in self.issue_linker_optin:
            return util_bot.CommandResult.NOT_WHITELISTED, None
        valid_issue_links = ISSUE_PATTERN.findall(msg.text)
        valid_issue_links.extend(CVE_PATTERN.findall(msg.text))
        if not valid_issue_links:
            return util_bot.CommandResult.OTHER_FILTERED, None
        links = []
        for repo, issue, commit in valid_issue_links:
            if repo == 'CVE':
                year, number = issue, commit
                links.append(f'https://nvd.nist.gov/vuln/detail/CVE-{year}-{number}')
            else:
                repo = REPO_MAP.get(repo.casefold(), repo)
                if '/' not in repo:
                    continue
                if issue:
                    links.append(ISSUE_LINK_FORMAT.format(repo=repo, id=issue))
                elif commit:
                    links.append(COMMIT_LINK_FORMAT.format(repo=repo, hash=commit))

        return (util_bot.CommandResult.OK, ' '.join(links)) if links else (util_bot.CommandResult.OTHER_FILTERED, None)

    async def c_issue_optin(self, msg: util_bot.StandardizedMessage):
        if msg.user.lower() in self.issue_linker_optin:
            self.issue_linker_optin.remove(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with util_bot.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user} You have been removed from the issue-linker opt-in list.'
        else:
            self.issue_linker_optin.append(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with util_bot.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user} You have been added to the issue-linker opt-in list.'
