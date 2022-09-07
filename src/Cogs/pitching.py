from discord.ext import commands


class Pitching(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    async def queuepitch(self, ctx):
        return

    @commands.command(brief='',
                      description='')
    async def clearlist(self, ctx):
        return

    @commands.command(brief='',
                      description='')
    async def changepitch(self, ctx):
        return


def setup(bot):
    bot.add_cog(Pitching(bot))
