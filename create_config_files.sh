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

# required, can be filled in with bad info if you don't want Supibot integration
cat > supibot_auth.json << EOF
{
   "id": [your bot's Supibot user alias],
   "key": "your_bots_secret_key00000000000000000000000000000000000000000000"
}
EOF