# Quick Setup Guide

## Config.ini
- rename config-template.ini to config.ini
- add usernames and passwords for the following:
```
[Discord]
token = yourTokenHere

[Reddit]
client_id=yourclientidhere
client_secret=yourclientsecrethere
username=botUsernameHere
password=botPasswordHere

[MySQL]
host=host.ip.address
username=username
password=password
```

For DEVELOPMENT ONLY change the following to:
```
[Database]
database_name = MLR-Dev
```

- To deploy for production, leave the database name as just `MLR`.
- Do not forget to save the file when you're done. 
- Any changes to this file will require a restart of the bot and/or Ump Ping script.

## Discord Bot
- Minimum Python version is 3.7 or later
- The following libraries are required
  - asyncpraw
  - praw
  - mysql
  - configparser
  - dhooks
  - discord
  - discord.ext
  - googleapiclient
  - google_auth_oauthlib
  - google.auth.transport.requests
- Follow this tutorial to authorize a google application and generate a token.pickle: https://developers.google.com/sheets/api/quickstart/python
- To run, just run discord_bot.py

## Ump Ping Script
- must be run as a separate script from the bot
- run reddit_watcher.py
