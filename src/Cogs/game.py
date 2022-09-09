from discord.ext import commands


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    async def dm_swing(self, ctx):
        # Get batter ID
        # See if they are up to bat anywhere
        return

    @commands.command(brief='',
                      description='')
    async def conditional_swing(self, ctx):
        # GM requests conditional sub
        # Log time, notes, find batter
        # Prompt batter for conditional swing
        # Store it all in the DB
        return

    @commands.command(brief='',
                      description='')
    async def conditional_pitch(self, ctx):
        # GM requests conditional sub
        # Log time, notes, find pitcher
        # Prompt batter for conditional pitch
        # Store it all in the DB
        return

    @commands.command(brief='',
                      description='')
    async def request_sub(self, ctx, ):

        return

    @commands.command(brief='',
                      description='')
    async def request_auto_k(self, ctx):
        return

    @commands.command(brief='',
                      description='')
    async def request_auto_bb(self, ctx):
        # Get current game
        return

    @commands.command(brief='',
                      description='')
    async def game_state(self, ctx, team):
        return


def setup(bot):
    bot.add_cog(Game(bot))
