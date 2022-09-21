import datetime
import random
from dhooks import Webhook
import discord
from discord.ext import commands, tasks
import os
import configparser

from src.Ump import gameplay_loop
from src.Cogs import player

intents = discord.Intents.all()
intents.members = True

config = configparser.ConfigParser()
config.read('config.ini')
token = config['Discord']['token']
prefix = config['Discord']['prefix']
ump_admin = int(config['Discord']['ump_admin_role'])
error_log = Webhook(config['Channels']['error_log_webhook'])
config_ini = 'config.ini'
league_ini = 'league.ini'

bot = commands.Bot(command_prefix=prefix, description='Dottie Rulez', case_insensitive=True, intents=intents)


def read_config(filename, section, setting):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    return ini_file[section][setting]


@bot.event
async def on_ready():
    for filename in os.listdir('Cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'Cogs.{filename[:-3]}')
    # scoreboard.start()
    await gameplay_loop.startup_loop(bot)
    ump_bot.start()
    print('ready')


@bot.command(brief='Restarts the scoreboard task',
             description='')
async def restart_scoreboard(ctx):
    scoreboard.restart()
    await ctx.message.add_reaction('✅')


@bot.command(brief='Restarts the scoreboard task',
             description='')
async def restart_gameplay(ctx):
    ump_bot.restart()
    await ctx.message.add_reaction('✅')


@bot.command(brief='Otter plz',
             description='I genuinely did not think anybody would need help with this command.')
async def otter(ctx):
    otters = open('otters.txt').read().splitlines()
    await ctx.send(random.choice(otters))


@bot.command(brief='Reloads bot modules',
             description='Unloads and reloads one of the cogs in the ')
@commands.has_role(ump_admin)
async def reload(ctx, extension):
    await bot.unload_extension('Cogs.%s' % extension)
    await bot.load_extension('Cogs.%s' % extension)
    await ctx.message.add_reaction('✅')


@tasks.loop(seconds=5*60)
async def scoreboard():
    embed = discord.Embed(title='League Scoreboard', color=discord.Colour.red())
    embed.set_thumbnail(url='https://media.discordapp.net/attachments/583735640177246222/892826404520071238/baseball_snoo.png')
    channel_id = int(read_config(config_ini, 'Channels', 'scoreboard_channel'))
    message_id = int(read_config(config_ini, 'Channels', 'scoreboard_msg'))
    mlr_season = int(read_config(league_ini, 'MLR', 'season'))
    mlr_session = int(read_config(league_ini, 'MLR', 'session'))
    milr_season = int(read_config(league_ini, 'MILR', 'season'))
    milr_session = int(read_config(league_ini, 'MILR', 'session'))
    scoreboard_channel = bot.get_channel(channel_id)
    scoreboard_msg = await scoreboard_channel.fetch_message(message_id)
    mlr_scoreboard = player.scoreboard('mlr', mlr_season, mlr_session)
    milr_scoreboard = player.scoreboard('milr', milr_season, milr_session)
    embed.add_field(name='MLR Scoreboard', value=mlr_scoreboard)
    embed.add_field(name='MiLR Scoreboard', value=milr_scoreboard)
    embed.set_footer(text='Last updated %s' % datetime.datetime.now())
    await scoreboard_msg.edit(content=None, embed=embed)


@tasks.loop(seconds=5*60)
async def ump_bot():
    await gameplay_loop.gameplay_loop(bot)


# @bot.event
# async def on_command_error(ctx, error):
#     if isinstance(error, CommandNotFound):
#         return
#     elif isinstance(error, MissingRole):
#         await ctx.send('You don\'t have permission to use that command.')
#     elif isinstance(error, MissingRequiredArgument):
#         await ctx.send('Missing a required argument. Please use .help %s for more information.' % ctx.command)
#     elif isinstance(error, CommandInvokeError):
#         if type(error.original) == HttpError:
#             if 'HttpError 403' in str(error):
#                 await ctx.send('[HTTPError 403 Forbidden] - please ensure rslashfakebaseball@gmail.com has permission to edit your ump helper sheet.')
#             elif 'HttpError 404' in str(error):
#                 await ctx.send('[HTTPError 404 Not found] - could not find ump helper sheet, please ensure your sheet ID is valid.')
#             elif 'HttpError 500' in str(error):
#                 await ctx.send('[HTTPError 500 Internal error] - idk wtf just happened but it didn\'t work. Try whatever you just did again.')
#                 error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
#             else:
#                 await ctx.send('HTTP Error when accessing sheet: %s' % str(error))
#                 error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
#         elif type(error.original) == TimeoutError:
#             await ctx.send('The operation has timed out, please try again.')
#         else:
#             error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
#     else:
#         error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))


bot.run(token)
