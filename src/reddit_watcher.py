import configparser
import time
import src.db_controller as db
import praw
from dhooks import Webhook
import re

base_url = 'https://www.reddit.com'
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
hook = Webhook(config['Channels']['swing_alerts_webhook'])
subreddit_name = config['Reddit']['subreddit_name']


def get_discord_ids(thread_url):
    sql = '''SELECT discordID FROM umpData WHERE gameThread=?'''
    return db.fetch_data(sql, (thread_url,))


def check_swing():
    for comment in reddit.subreddit(subreddit_name).stream.comments(skip_existing=True):
        regexp = bool(re.search('([^\d]|^)\d{1,4}([^\d]|$)', comment.body))
        author = 'u/%s' % comment.author
        author = author.lower()
        if comment.parent_id[:3] == child_comment_prefix:
            parent_comment = reddit.comment(comment.parent_id[3:])
            parent_comment_text = parent_comment.body
            parent_comment_text = parent_comment_text.lower()
            if ((author in parent_comment_text) or ('steal'.lower() in comment.body.lower())) and regexp:
                swing_url = '%s%s' % (base_url, comment.permalink)
                swing_alert = '/u/%s has swung!' % comment.author
                game_thread = reddit.submission(comment.submission)
                game_thread_url = "%s%s" % (base_url, game_thread.permalink)
                umps = get_discord_ids(game_thread_url)
                if umps:
                    for ump in umps:
                        swing_alert += ' <@%s>' % ump[0]
                swing_alert += ' [link](<%s>)' % swing_url
                if len(comment.body) <= 100:
                    swing_alert += '```%s```' % comment.body
                hook.send(swing_alert)


while True:
    try:
        check_swing()
    except Exception as e:
        print(e)
        time.sleep(60)
    else:
        time.sleep(360)
