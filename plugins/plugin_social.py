#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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
import typing

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
try:
    # noinspection PyPackageRequirements
    import plugin_plugin_manager as plugin_manager

except ImportError:
    import plugins.plugin_manager as plugin_manager

    exit()
# noinspection PyUnresolvedReferences
import twitchirc
import twitterscraper

NAME = 'social'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.twitter_account_setting = plugin_manager.Setting(
            self,
            'social.twitter_account',
            default_value=None,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True
        )
        self.c_where_is_channel_owner = main.bot.add_command('whereis')(self.c_where_is_channel_owner)

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    async def get_latest_tweet(self, user):
        return await asyncio.get_event_loop().run_in_executor(None, self._fetch_latest_tweet, user)

    @staticmethod
    def _fetch_latest_tweet(user):
        try:
            tweets = twitterscraper.query_tweets(f'from:{user}', limit=5)
            return sorted(tweets, key=lambda o: o.timestamp, reverse=True)[0]
        except:
            return None

    def on_reload(self):
        pass

    def get_twitter_handle(self, channel: str) -> typing.Optional[str]:
        if channel in plugin_manager.channel_settings:
            return plugin_manager.channel_settings[channel].get(self.twitter_account_setting)
        print('no channel settings')
        return None

    async def c_where_is_channel_owner(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('where_is_channel_owner', msg, global_cooldown=30, local_cooldown=60)
        if cd_state:
            return

        handle = self.get_twitter_handle(msg.channel)
        print(handle)
        if handle is None:
            return f'@{msg.user}, There\'s no Twitter account associated with this channel.'
        else:
            tweet = await self.get_latest_tweet(handle)
            if tweet is None:
                return f'@{msg.user}, Error: cannot find any tweet by @{handle} :('
            return f'@{msg.user}, {tweet.username}\'s (@{handle}) latest tweet: {tweet.text}'

