import configparser
import discord
import src.Cogs.player as p
from discord.ext import commands

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')
doam_channel_id = int(config_ini['Doam']['doam_channel_id'])
doam_admin_role = int(config_ini['Doam']['doam_admin_role'])


class Doam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='',
                      aliases=['doam'])
    async def dildoam(self, ctx):
        doam_channel = self.bot.get_channel(doam_channel_id)

        def get_player(msg):
            return msg.author == ctx.author and msg.channel == doam_channel and msg.mentions

        await doam_channel.send('**Team 1** (pitching first) \nPing the pitcher')
        player = await self.bot.wait_for('message', check=get_player)
        pitcher1 = player.mentions[0]

        await doam_channel.send('**Team 1** (pitching first) \nPing the batter')
        player = await self.bot.wait_for('message', check=get_player)
        batter1 = player.mentions[0]

        await doam_channel.send('**Team 2** (batting first) \nPing the pitcher')
        player = await self.bot.wait_for('message', check=get_player)
        pitcher2 = player.mentions[0]

        await doam_channel.send('**Team 2** (batting first) \nPing the batter')
        player = await self.bot.wait_for('message', check=get_player)
        batter2 = player.mentions[0]

        team1_hrs = 0
        team2_hrs = 0
        rounds = 10
        await doam_channel.send(f'{batter2.mention} batting against {pitcher1.mention}')
        for i in range(rounds):
            await doam_channel.send(f'**Round {i+1}**')
            await pitcher1.send(f'**Round {i+1}**')
            result = await doamtime(self.bot, pitcher1, batter2)
            if result:
                team2_hrs += 1
            await doam_channel.send(f'{team2_hrs}/{i+1}')
            await pitcher1.send(f'{team2_hrs}/{i+1}')
        await doam_channel.send(f'{batter1.mention} batting against {pitcher2.mention}')
        for i in range(rounds):
            if team1_hrs <= team2_hrs:
                await doam_channel.send(f'**Round {i+1}**')
                await pitcher2.send(f'**Round {i+1}**')
                result = await doamtime(self.bot, pitcher2, batter1)
                if result:
                    team1_hrs += 1
                await doam_channel.send(f'{team1_hrs}/{i+1}')
                await pitcher2.send(f'{team1_hrs}/{i+1}')
        if team1_hrs == team2_hrs:
            await doam_channel.send(f'**ITS TIME FOR SUDDEN DEATH!!**')
            while team1_hrs == team2_hrs:
                rounds += 1
                await doam_channel.send(f'**Round {rounds}**')
                result = await doamtime(self.bot, pitcher1, batter2)
                if result:
                    team2_hrs += 1
                result = await doamtime(self.bot, pitcher2, batter1)
                if result:
                    team1_hrs += 1
        if team1_hrs > team2_hrs:
            if pitcher1 != batter1:
                await doam_channel.send(f'{pitcher1.mention} and {batter1.mention} win!')
            else:
                await doam_channel.send(f'{pitcher1.mention} wins!')
        elif team1_hrs < team2_hrs:
            if pitcher2 != batter2:
                await doam_channel.send(f'{pitcher2.mention} and {batter2.mention} win!')
            else:
                await doam_channel.send(f'{pitcher2.mention} wins!')


def setup(bot):
    bot.add_cog(Doam(bot))


async def doamtime(bot, pitcher, batter):
    # Get Pitch
    await pitcher.send("Pitch pls")

    def wait_for_pitch(msg):
        return msg.author == pitcher and msg.guild is None and msg.content.isnumeric() and int(msg.content) > 0 and int(msg.content) <= 1000

    pitch = await bot.wait_for('message', check=wait_for_pitch)
    pitch = int(pitch.content)

    # Get Swing
    doam_channel = bot.get_channel(doam_channel_id)
    await doam_channel.send(f'The pitch is in! Swing {batter.mention}')

    def wait_for_swing(msg):
        return msg.author == batter and msg.channel == doam_channel and msg.content.isnumeric() and int(msg.content) > 0 and int(msg.content) <= 1000

    swing = await bot.wait_for('message', check=wait_for_swing)
    swing = int(swing.content)

    diff = p.calculate_diff(pitch, swing)
    result = f'Pitch: {pitch}\nSwing: {swing}\nDiff: {diff}'
    if diff <= 100:
        result += ' -> HR'
        await pitcher.send(result)
        await doam_channel.send(result)
        return True
    else:
        result += ' -> No HR'
        await pitcher.send(result)
        await doam_channel.send(result)
        return False


