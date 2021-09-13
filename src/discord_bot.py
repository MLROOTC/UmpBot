import random
from dhooks import Webhook
import discord
from discord.ext import commands
import os
import configparser
from discord.ext.commands import CommandNotFound, MissingRole, MissingRequiredArgument, CommandInvokeError
from googleapiclient.errors import HttpError
from asyncio import TimeoutError

intents = discord.Intents.default()
intents.members = True

config = configparser.ConfigParser()
config.read('config.ini')
token = config['Discord']['token']
prefix = config['Discord']['prefix']
ump_admin = int(config['Discord']['ump_admin_role'])
error_log = Webhook(config['Channels']['error_log_webhook'])

bot = commands.Bot(command_prefix=prefix, description='Dottie Rulez', case_insensitive=True, intents=intents)


@bot.event
async def on_ready():
    for filename in os.listdir('Cogs'):
        if filename.endswith('.py'):
            bot.load_extension('Cogs.%s' % filename[:-3])


@bot.command(brief='Otter plz',
             description='I genuinely did not think anybody would need help with this command.')
async def otter(ctx):
    otters = open('otters.txt').read().splitlines()
    await ctx.send(random.choice(otters))


@bot.command(brief='Reloads bot modules',
             description='Unloads and reloads one of the cogs in the ')
@commands.has_role(ump_admin)
async def reload(ctx, extension):
    bot.unload_extension('Cogs.%s' % extension)
    bot.load_extension('Cogs.%s' % extension)
    await ctx.message.add_reaction('✅')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    elif isinstance(error, MissingRole):
        await ctx.send('You don\'t have permission to use that command.')
    elif isinstance(error, MissingRequiredArgument):
        await ctx.send('Missing a required argument. Please use .help %s for more information.' % ctx.command)
    elif isinstance(error, CommandInvokeError):
        if type(error.original) == HttpError:
            if 'HttpError 403' in str(error):
                await ctx.send('[HTTPError 403 Forbidden] - please ensure rslashfakebaseball@gmail.com has permission to edit your ump helper sheet.')
            elif 'HttpError 404' in str(error):
                await ctx.send('[HTTPError 404 Not found] - could not find ump helper sheet, please ensure your sheet ID is valid.')
            elif 'HttpError 500' in str(error):
                await ctx.send('[HTTPError 500 Internal error] - idk wtf just happened but it didn\'t work. Try whatever you just did again.')
                error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
            else:
                await ctx.send('HTTP Error when accessing sheet: %s' % str(error))
                error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
        elif type(error.original) == TimeoutError:
            await ctx.send('The operation has timed out, please try again.')
        else:
            error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))
    else:
        error_log.send("`[%s|%s]-%s:` %s" % (ctx.guild, ctx.channel, ctx.command, str(error)))


bot.run(token)
