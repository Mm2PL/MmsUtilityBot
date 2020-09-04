1. `plugin_active_chatters.py` Commands moved from the main bot that have to do with counting active chatters
1. `plugin_autoflush.py` Automatically flush messages,
1. `plugin_ban_phrase.py` (admin) Add ban phrases to your bot,
1. `plugin_blacklist.py` (admin) Blacklist people or channels from your bot,
1. `plugin_cancer.py` Plugin tuned for my usage, does lots of things that are not the best, responding to messages that 
aren't commands etc.
1. `plugin_chat_cache.py` (util) Cache the chat, utility to be used by other plugins
1. `plugin_converter.py` Allow users to convert between units
1. `plugin_debug.py` (admin) Debug the bot, allows to send messages via the bot or use eval, HOWEVER eval is currently
                             hardcoded to only work with my (Mm2PL) account
1. `plugin_emote_limiter.py` (admin) Limit usage of emotes
1. `plugin_hastebin.py` Allow users to hastebin their message, can be used by other plugins
1. `plugin_help.py` Add interactive help to your bot
1. `plugin_ipc.py` (util) Interprocess communication, required for `web` to work
1. `plugin_logs.py` Save logs in the database
1. `plugin_mailbox_game.py` Adds a system for counting guesses in the mail-game from TLOZ: TWW, originates from #linkus7
1. `plugin_no_perm_message.py` Show a message when the user lacks permissions to run a command
1. `plugin_nuke.py` Timeout or ban users in bulk
1. `plugin_ping.py` Adds a simple `ping` command
1. `plugin_ping_optout.py` Allow users to opt-out of being mentioned by the bot.
1. `plugin_pipes.py` Allows for chaining commands using `[prefix]pipe command | another command > redirection` 
1. `plugin_plot.py` Let users calculate things from chat, allows for plotting with the `plot(func, start, end, step)`
                    function
1. `plugin_prefixes.py` Change the bot's prefix per-channel
1. `plugin_reminders.py` [tbd]
1. `plugin_replay.py` Adds a command that links to the vod.
1. `plugin_simple_command_manager.py` (beta) Manage commands in `commands.json` from chat
1. `plugin_social.py` Adds a command that pulls the latest tweet, however it is not using the official API, and thus it 
acts a bit stupid sometimes due to the library used.
1. `plugin_speedrun.py` Adds a command that shows the world record for the current game
1. `plugin_su.py` (admin) Allows you to pretend you are another user
1. `plugin_suggestions.py` (admin) Allows you to take suggestions for your bot
1. `plugin_supibot_is_alive.py` Adds Supibot integration, will call the api every 30 minutes to say that the bot is alive.
1. `plugin_uptime.py` Adds `uptime`, `downtime`, `title` commands
1. `plugin_vote.py` Adds a simple poll system
1. `plugin_whois.py` Adds a `whois` command that returns information about a Twitch user
<!--
1. `plugin_.py` [tbd]
-->