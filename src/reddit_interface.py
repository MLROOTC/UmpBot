import configparser
import praw
import asyncpraw
from asyncpraw.reddit import Submission

config = configparser.ConfigParser()
config.read('config.ini')

client_id = config['Reddit']['client_id']
client_secret = config['Reddit']['client_secret']
user_agent = config['Reddit']['user_agent']
username = config['Reddit']['username']
password = config['Reddit']['password']

reddit = asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username,
                          password=password)


async def delete_comment(comment_url):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        comment = await reddit.comment(url=comment_url)
        await comment.delete()
        comment = await reddit.comment(url=comment_url)
        if comment.body == '[deleted]':
            return True
        return False


async def delete_thread(thread_url):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        thread = await get_thread_url(thread_url)
        await thread.delete()
        thread = await get_thread_url(thread_url)
        if thread.selftext == '[deleted]':
            return True
        return False


async def edit_thread(thread_url, body):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        submission = await reddit.submission(Submission.id_from_url(thread_url))
        if submission.author.name.lower() == username.lower():
            return await submission.edit(body)
        return False


async def get_comment_async(comment_url):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        return await reddit.comment(url=comment_url)


def get_comment(comment_url):
    with praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password) as reddit:
        return reddit.comment(url=comment_url)


async def get_comment_url(comment_id):
    with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password) as reddit:
        return await reddit.comment(id=comment_id)


async def get_thread_url(thread_url):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        return await reddit.submission(Submission.id_from_url(thread_url))


async def get_thread_async(submission_id):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        return await reddit.submission(submission_id)


def get_thread(submission_id):
    with praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password) as reddit:
        return reddit.submission(submission_id)


async def post_thread(subreddit, title, body):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent, username=username, password=password) as reddit:
        subreddit = await reddit.subreddit(subreddit)
        thread = await subreddit.submit(title, selftext=body)
        return await reddit.submission(thread)


async def post_comment(thread_url, comment):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        submission = await reddit.submission(Submission.id_from_url(thread_url))
        return await submission.reply(comment)


async def reply_comment(parent_comment, body):
    async with asyncpraw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent,
                                username=username, password=password) as reddit:
        comment = await reddit.comment(url=parent_comment)
        return await comment.reply(body)
