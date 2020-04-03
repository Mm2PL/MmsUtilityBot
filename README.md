# Mm's utility bot
This is a code repository of the [Twitch bot](https://www.twitch.tv/mm_sutilitybot).

# Installing

1. Clone the repo, for example using `git clone https://github.com/Mm2PL/MmsUtilityBot`
2. Install requirements from `requirements.txt` using pip (`pip install -r requirements.txt`)
3. Create necessary configuration files:<br>
    ```shell script
    cat > storage.json << EOF
    {
      "permissions": {
           "your lower case twitch username": ["twitchirc.bypass.permission"]
       }
    }
    EOF
   
    # optional, only required if you are running the bot with the debug flag
    cp storage.json storage_debug.json
    
    cat > twitch_api.json << EOF
    {
    "access_token": "your_Twitch_access_token012345",
    "client_id": "your_Twitch_client_id012345678",
    "client_secret": "your_Twitch_client_secret01234",
    }
    EOF
   
    cat > commands.json << EOF
    [
      {
        "_comment": "Example echo command",
        "type": "echo",
        "channel": [
          "list_of_channels"
        ],
        "message": "Your message, executor is {user}, command name is {cmd}, argument 0 is {0}, all arguments are {+}",
      },
      {
        "_comment": "Example counter command",
        "type": "counter",
        "channel": [
          "list_of_channels"
        ],
        "message": {
          "_comment": "true is sent when the counters value changed, false otherwise",
          "false": "Counter didn't change, name is {name}, value is {val}",
          "true": "Counter changed, name is {name}, old value is {old_val}, {new_val}"
        }
      }
    ]
    EOF
   
   # required, can be filled in with bad info if you don't want Supibot integration
   cat > supibot_auth.json << EOF
   {
       "id": [your bot's Supibot user alias],
       "key": "your_bots_secret_key00000000000000000000000000000000000000000000"
   }
   EOF
    ```
4. Pick a database, for local testing you can use sqlite, for production you can use MariaDB,
    1. Path for sqlite is `sqlite:///PATH/TO/DB`
    2. For MariaDB or Mysql it is `mysql+pymysql://user:passowrd@host/db_name`
5. Create a key pair for signing code. Make sure to store the private key somewhere safe, if you are running the bot in a vm or on an external host, don't send the key there
    You can use the included `generate_keys.py` script to do this for you.
    Your keys should look a bit like this:
    ```
    -----BEGIN RSA PUBLIC KEY-----
    [all sorts of letters, numbers, slashes, pluses]
    -----END RSA PUBLIC KEY-----
    ```
   Save the public part as `code_sign_public.pem` on the target machine,
   
6. Start the bot
    1. For production `python util_bot.py --base-addr YOUR_DATABASE_ADDRESS`
    2. For debug `python util_bot.py --debug --base-addr YOUR_DATABASE_ADDRESS`
    
    NOTE: debug mode doesn't do much right now, it just uses `storage_debug.json` instead of `storage.json`
8. Stop the bot using `Control+c`, it is fine to press it again when the bot is not outputing anything, but still running
9. Fine tune the config:
    1. Open `storage.json` with your favourite text editor
    2. (optional) beatify the file somehow
    3. Find `"plugins":`
    4. Add desired plugins from the [list](list_of_plugins.md)
    
# Using in noninteractive ways
The `main_stub.py` is a version of the main file (`util_bot.py`) that doesn't require a connection to Twitch or the db.

## Creating dependency graphs
Run `python main_stub.py path/to/plugin` to generate a human readable graph, 
 - yellow means it's a plugin, 
 - green that it is a plugin and was loaded before
 
Example graph of `plugin_cancer`:
```
plugins/plugin_cancer.py
    * import asyncio
    * import datetime
    * import time
    * import warnings
    * import typing
    * import typing
    * import regex
    * import PIL
    * import utils
        * import plugins.utils
        * import helpers
            * import plugins.helpers
            - [yellow]import plugin_plugin_help
                * import argparse
                * import shlex
                * import typing
                * import typing
                * import twitchirc
                - [yellow]import plugin_plugin_manager
                    * import asyncio
                    * import traceback
                    * import typing
                    * import typing
                    * import twitchirc
                    * import twitchirc
                    * import plugins.models.channelsettings
                    * import plugins.models.channelsettings
                - [yellow]import plugin_plugin_prefixes
                    * import shlex
                    * import typing
                    + [green] import plugin_plugin_manager
                    * import twitchirc
            + [green] import plugin_plugin_manager
            - [yellow] import plugin_hastebin
                * import queue
                * import typing
                * import aiohttp
                + [green] import plugin_plugin_help
                + [green] import plugin_plugin_manager
                * import twitchirc
            - [yellow] import plugin_emotes
                * import abc
                * import typing
                * import aiohttp
                * import twitchirc
            * import random
            * import twitchirc
```

## Extracting help
Run `python main_stub.py path/to/plugin -H` to generate a human readable graph and extract help
Example: 
```
[snip, import graph]

- Section 0
    - braillefy sensitivity_r: (2, 'braillefy sensitivity')
    - braillefy sensitivity_g: (2, 'braillefy sensitivity')
    - braillefy sensitivity_b: (2, 'braillefy sensitivity')
    - braillefy sensitivity_a: (2, 'braillefy sensitivity')
    - braillefy size_percent: (2, 'braillefy size')
    - braillefy max_x: (2, 'braillefy size')
    - braillefy pad_y: (2, 'braillefy size')
    - plugin_cancer.py: (7, 'plugin_cancer')
    - cancer: (7, 'plugin_cancer')
    - ed: (7, '+ed')
    - enterdungeon: (7, '+ed')
    - +enterdungeon: (7, '+ed')
- Section 1
    - hastebin: Create a hastebin of the message you provided.
    - cookie: Add yourself to the list of people who will be reminded to eat cookies
    - mb.pyramid: Make a pyramid out of an emote or text. Usage: pyramid <size> <text...>
    - braillefy: Convert an image into braille. Usage: braillefy url:URL [+reverse] [sensitivity_(r|g|b|a):FLOAT] [size_percent:FLOAT] [max_x:INT (default 60)] [pad_y:INT (60)]
- Section 2
    - braillefy url: URL pointing to image you want to convert.
    - braillefy reverse: Should the output braille be reversed.
    - braillefy sensitivity: Per-channel sensitivity of the converter. r(ed), g(reen), b(lue), a(lpha)
    - braillefy size: Size of the image. Defaults: max_x = 60, pad_y = 60, size_percent=[undefined]. max_x, pad_y are in pixels.
- Section 7
    - me: What do you need help with? Do you need one of these? https://en.wikipedia.org/wiki/List_of_suicide_crisis_lines
    - plugin_cancer: Plugin dedicated to things that shouldn't be done (responding to messages other than commands, spamming).
    - +ed: The `cancer` plugin sends a message containing +ed every five minutes to activate HuwoBot.
```

## Machine readable exports
You can use the `-m` flag to make `main_stub.py` return machine readable exports in JSON format.
