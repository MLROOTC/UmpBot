import configparser
import time
import src.Ump.robo_ump as robo_ump
import praw
import re

config = configparser.ConfigParser()
config.read('config.ini')
client_id = config['Reddit']['client_id']
client_secret = config['Reddit']['client_secret']
user_agent = config['Reddit']['user_agent']
root_comment_prefix = 't3_'
child_comment_prefix = 't1_'

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
            if ((author.lower() in parent_comment.body.lower()) or ('steal'.lower() in comment.body.lower())) and regexp:
                robo_ump.get_swing_from_reddit(f'https://www.reddit.com{comment.permalink}')


while True:
    try:
        check_swing()
    except Exception as e:
        print(e)
        time.sleep(60)
