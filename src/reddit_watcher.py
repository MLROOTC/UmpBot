import configparser
import time
import src.Ump.robo_ump as robo_ump
import praw
import re
import traceback
import sys
from dhooks import Webhook

config = configparser.ConfigParser()
config.read('config.ini')
client_id = config['Reddit']['client_id']
client_secret = config['Reddit']['client_secret']
user_agent = config['Reddit']['user_agent']
username = config['Reddit']['username']
root_comment_prefix = 't3_'
child_comment_prefix = 't1_'
debug_hook = Webhook(config['Channels']['error_log_webhook'])

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent
)
subreddit_name = config['Reddit']['subreddit_name']


def check_swing():
    for comment in reddit.subreddit(subreddit_name).stream.comments(skip_existing=True):
        regexp = bool(re.search('([^\d]|^)\d{1,4}([^\d]|$)', comment.body))
        author = f'u/{comment.author}'
        if comment.parent_id[:3] == child_comment_prefix:
            parent_comment = reddit.comment(comment.parent_id[3:])
            if 'steal' in comment.body.lower() and comment.author != username and regexp:
                robo_ump.get_swing_from_reddit(f'https://www.reddit.com{comment.permalink}')
            elif author.lower() in parent_comment.body.lower() and regexp:
                robo_ump.get_swing_from_reddit(f'https://www.reddit.com{comment.permalink}')


debug_hook.send(f'reddit_watcher.py started with python {sys.version}')
while True:
    try:
        check_swing()
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        time.sleep(60)
debug_hook.send('reddit_watcher.py stopped...')
