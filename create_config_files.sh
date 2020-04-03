#!/usr/bin/env bash

cat > storage.json << EOF
{
  "permissions": {
       "your lower case twitch username": ["twitchirc.bypass.permission"]
   }
}
EOF

cat > twitch_api.json << EOF
{
  "access_token": "your_Twitch_access_token012345",
  "client_id": "your_Twitch_client_id012345678",
  "client_secret": "your_Twitch_client_secret01234"
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