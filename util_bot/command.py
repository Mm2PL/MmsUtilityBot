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
import enum
import inspect
import time
import typing

import twitchirc

import util_bot

COMMAND_SUBPREFIX = 'mb.'


class CommandResult(enum.Enum):
    OK = enum.auto()

    OTHER_FAILED = enum.auto()
    ON_COOLDOWN = enum.auto()
    NO_PERMISSIONS = enum.auto()
    BLACKLISTED = enum.auto()
    NOT_WHITELISTED = enum.auto()
    OTHER_FILTERED = enum.auto()

    @classmethod
    def is_fail(cls, target):
        return target > cls.OTHER_FAILED


class CommandCooldown:
    def __init__(self, user, channel, platform, local_bypass=True):
        self.platform = platform
        self.channel = channel
        self.user = user
        self.local_bypass = local_bypass

    def __hash__(self):
        return hash((
            self.platform,
            self.channel,
            self.user,
            self.local_bypass
        ))


class Command(twitchirc.Command):
    parent: 'util_bot.Bot'

    def __init__(self, chat_command: str, function: typing.Callable, parent: 'util_bot.Bot',
                 matcher_function: typing.Optional[typing.Callable[['util_bot.StandardizedMessage', typing.Any],
                                                                   bool]] = None,
                 limit_to_channels: typing.Optional[typing.List[str]] = None,
                 available_in_whispers: bool = True,
                 cooldown: typing.Union[typing.Tuple[int, ...], CommandCooldown] = CommandCooldown(15, 3, 0),
                 aliases: typing.Optional[typing.List[str]] = None):
        super().__init__(chat_command, function, parent, None, True, matcher_function,
                         limit_to_channels, available_in_whispers)
        self.aliases = aliases or []
        if not isinstance(cooldown, CommandCooldown):
            cooldown = CommandCooldown(*cooldown)
        self.cooldown = cooldown

        self._legacy_matcher = None
        self._matcher_function = matcher_function or self.subprefix_matcher

    @property
    def matcher_function(self):
        if self._legacy_matcher:
            return lambda msg, prefix: bool(self._legacy_matcher(msg, self))
        return self._matcher_function

    @matcher_function.setter
    def matcher_function(self, value):
        self._legacy_matcher = value

    async def check_cooldown(self, msg) -> bool:
        per_channel_key, per_platform_key, per_user_key = self.cooldown_keys(msg)

        now = time.time()
        on_cooldown = (util_bot.cooldowns.get(per_user_key, 0) > now
                       or util_bot.cooldowns.get(per_platform_key, 0) > now
                       or util_bot.cooldowns.get(per_channel_key, 0) > now)

        return on_cooldown

    def cooldown_keys(self, msg):
        per_user_key = (self, 'user', (msg.platform, msg.user))
        per_platform_key = (self, 'platform', msg.platform)
        per_channel_key = (self, 'channel', (msg.platform, msg.channel))
        return per_channel_key, per_platform_key, per_user_key

    async def apply_cooldown(self, msg):
        per_channel_key, per_platform_key, per_user_key = self.cooldown_keys(msg)
        now = time.time()

        util_bot.cooldowns[per_channel_key] = now + self.cooldown.channel
        util_bot.cooldowns[per_platform_key] = now + self.cooldown.platform
        util_bot.cooldowns[per_user_key] = now + self.cooldown.user

    async def acall(self, message) -> typing.Optional[str]:
        """
        Async call. Does everything what sacall() does but doesn't return the status.
        Exists because of backward compatibility.
        """
        # noinspection PyTypeChecker
        return (await self.sacall(message))[1]

    async def sacall(self, message: typing.Union['util_bot.StandardizedMessage',
                                                 'util_bot.StandardizedWhisperMessage']) \
            -> typing.Tuple[CommandResult, typing.Optional[str]]:
        """Async call with status. Checks cooldowns, permissions and executes command."""
        if isinstance(message, util_bot.StandardizedWhisperMessage) and self.available_in_whispers is False:
            return CommandResult.BLACKLISTED, self.no_whispers_message
        if self.limit_to_channels is not None and message.channel not in self.limit_to_channels:
            return CommandResult.NOT_WHITELISTED, None
        on_cooldown = await self.check_cooldown(message)
        if on_cooldown:
            missing_perms = await self.parent.acheck_permissions(
                message,
                permissions=['util.no_cooldown'],
                enable_local_bypass=self.cooldown.local_bypass
            )
            if missing_perms:
                return CommandResult.ON_COOLDOWN, None

        if self.permissions_required:
            o = await self.parent.acheck_permissions_from_command(message, self)
            if o:  # a non-empty list of missing permissions.
                return CommandResult.NO_PERMISSIONS, f'Missing permissions: {", ".join(o)}'

        await self.apply_cooldown(message)

        if inspect.iscoroutinefunction(self.function):
            val = await self.function(message)
        else:
            val = self.function(message)

        if (isinstance(val, tuple) and len(val) == 2
                and isinstance(val[0], CommandResult)):
            # checks if val is a Tuple[CommandResult, Any]
            return val
        return CommandResult.OK, val

    def default_matcher(self, msg, prefix, aliases=None):
        if msg.text.startswith(prefix + self.ef_command):
            return prefix + self.ef_command

        for al in self.aliases + (aliases or []):
            if msg.text.startswith(prefix + al + ' '):
                return prefix + al + ' '

        return False

    def subprefix_matcher(self, msg, prefix):
        can_use_no_subprefix = (
                (msg.channel, msg.platform) in util_bot.bot.prefixes or

                (msg.platform in util_bot.bot.prefixes
                 and isinstance(msg, util_bot.StandardizedWhisperMessage))
        )

        if can_use_no_subprefix or self.chat_command.startswith(COMMAND_SUBPREFIX):
            # allow legacy manually subprefixed commands
            has_match_no_prefix = self.default_matcher(msg, prefix)
            if has_match_no_prefix:
                return has_match_no_prefix

        if msg.text.startswith(prefix + COMMAND_SUBPREFIX):
            old_text = msg.text
            msg.text = msg.text.replace(prefix + COMMAND_SUBPREFIX, prefix)
            ret_val = self.default_matcher(msg, prefix)

            msg.text = old_text
            return ret_val
        return False

    def __hash__(self) -> int:
        return hash((
            self.chat_command,
            self.function,
            self.matcher_function,
            self.cooldown
        ))
