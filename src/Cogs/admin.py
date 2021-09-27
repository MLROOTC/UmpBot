import configparser
import discord
from dhooks import Webhook
from discord.ext import commands
import src.db_controller as db

config = configparser.ConfigParser()
config.read('config.ini')
ump_admin = int(config['Discord']['ump_admin_role'])
error_log = Webhook(config['Channels']['error_log_webhook'])
league_config = 'league.ini'


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        config = configparser.ConfigParser()
        config.read('config.ini')

    @commands.command(brief='Sets the webhook URL for team servers',
                      description='Adds a webhook URL into the database for results to get posted to different servers.'
                                  ' Accepts the abbreviated team name and the URL as arguments.')
    @commands.has_role(ump_admin)
    async def add_webhook(self, ctx, team, *, url):
        sql = '''UPDATE teamData SET webhook_url = %s WHERE abb=%s'''
        db.update_database(sql, (url, team.upper()))
        db_team = db.fetch_data('''SELECT * FROM teamData WHERE abb = %s''', (team,))
        if db_team[0][4] == url:
            await ctx.send('Webhook URL set successfully.')
        else:
            await ctx.send('Something went wrong.')

    @commands.command(brief='Add an upmire to the database',
                      description='Adds a discord user to the umpire table in the database. @ the discord user and then'
                            ' provide their player ID.\n\nNote: Tech role is required to use this command.')
    @commands.has_role(ump_admin)
    async def add_ump(self, ctx, member: discord.Member, player_id):
        player_id = int(player_id)
        sql = '''SELECT * FROM playerData WHERE playerID=%s'''
        player = db.fetch_data(sql, (int(player_id),))
        ump_data = (player[0][1], member.id, player_id)
        sql = '''INSERT INTO umpData(umpName, discordID, playerID) VALUES (%s, %s, %s)'''
        db.update_database(sql, ump_data)
        await ctx.send('%s added to ump database.' % member.display_name)

    @commands.command(brief='Gets discord IDs for players')
    @commands.has_role(ump_admin)
    async def get_discord_ids(self, ctx):
        for guild in self.bot.guilds:
            for member in guild.members:
                user = db.fetch_data('''SELECT discordName, discordID FROM playerData WHERE discordName=%s''', (str(member),))
                if user:
                    user = user[0]
                    if not user[1]:
                        db.update_database('''UPDATE playerData SET discordID=%s WHERE discordName=%s''', (member.id, str(member)))
                        user = db.fetch_data('''SELECT discordName, discordID FROM playerData WHERE discordName=%s''', (str(member),))
                        if user[0][1]:
                            error_log.send('Added discord ID to database for <@%s>' % member.id)
                        else:
                            error_log.send('Failed to set user ID for <@%s>' % member.id)
        await ctx.send('Done.')

    @commands.command(brief='Removes a discord user as an umpire',
                      description='Adds a discord user to the umpire table in the database. @ the discord user as an '
                                  'argument.\n\nNote: Tech role is required to use this command.')
    @commands.has_role(ump_admin)
    async def remove_ump(self, ctx, member: discord.Member):
        sql = '''DELETE FROM umpData WHERE discordID=%s'''
        db.update_database(sql, (member.id,))
        await ctx.send('%s removed from ump database.' % member.display_name)

    @commands.command(brief='Removes a team\'s existing webhook URL',
                      description='Removes a webhook URL from the database.\n\nNote: Tech role is required to use this'
                                  ' command.')
    @commands.has_role(ump_admin)
    async def remove_webhook(self, ctx, team):
        sql = '''UPDATE teamData SET webhook_url = %s WHERE abb=%s'''
        db.update_database(sql, ('', team.upper()))
        db_team = db.fetch_data('''SELECT * FROM teamData WHERE abb = %s''', (team,))
        if db_team[0][4] == '':
            await ctx.send('Webhook URL reset successfully.')
        else:
            await ctx.send('Something went wrong.')

    @commands.command(brief='Set season number',
                      description='Set season number in the config.')
    @commands.has_role(ump_admin)
    async def set_season(self, ctx, league, season):
        write_config(league_config, league, 'season', season)
        await ctx.send('Season set to %s.' % read_config(league_config, league, 'season'))

    @commands.command(brief='Set session number',
                      description='Sets session number in the config.')
    @commands.has_role(ump_admin)
    async def set_session(self, ctx, league, season):
        write_config(league_config, league, 'session', season)
        await ctx.send('Session set to %s.' % read_config(league_config, league, 'session'))

def setup(bot):
    bot.add_cog(Admin(bot))


def read_config(filename, section, setting):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    return ini_file[section][setting]


def write_config(filename, section, setting, value):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    ini_file.set(section, setting, value)
    with open(filename, 'w') as configfile:
        ini_file.write(configfile)

