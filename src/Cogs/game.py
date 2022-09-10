import discord
from discord.ext import commands

import src.assets
import src.db_controller as db
import src.Ump.robo_ump as robo_ump


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    async def dm_swing(self, ctx):
        # TODO
        # Get batter ID
        # See if they are up to bat anywhere
        return

    @commands.command(brief='',
                      description='')
    async def conditional_swing(self, ctx):
        # TODO
        # GM requests conditional sub
        # Log time, notes, find batter
        # Prompt batter for conditional swing
        # Store it all in the DB
        return

    @commands.command(brief='',
                      description='')
    async def conditional_pitch(self, ctx):
        # TODO
        # GM requests conditional sub
        # Log time, notes, find pitcher
        # Prompt batter for conditional pitch
        # Store it all in the DB
        return

    @commands.command(brief='',
                      description='')
    async def request_sub(self, ctx, team: str):
        # TODO
        return

    @commands.command(brief='',
                      description='')
    async def request_auto_k(self, ctx, team: str):
        # TODO
        return

    @commands.command(brief='',
                      description='')
    async def request_auto_bb(self, ctx, team: str):
        # TODO
        # Get current game
        return

    @commands.command(brief='',
                      description='')
    async def game_state(self, ctx, team: str, season: int = None, session: int = None):
        if season and session:
            sql = '''SELECT league, season, session, gameID FROM gameData WHERE (awayTeam=%s OR homeTeam=%s) AND (season=%s AND session=%s) ORDER BY league, season, session, gameID'''
            data = (team, team, season, session)
        else:
            sql = '''SELECT league, season, session, gameID FROM gameData WHERE awayTeam=%s OR homeTeam=%s ORDER BY league, season, session, gameID'''
            data = (team, team)
        games = db.fetch_data(sql, data)
        if games:
            game = games[-1]
            sql = '''SELECT awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
            awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg = db.fetch_one(sql, game)
            sql = '''SELECT current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_notes = db.fetch_one(sql, game)
            color, logo = db.fetch_one('''SELECT color, logo_url FROM teamData WHERE abb=%s''', (team,))
            current_batter = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (current_batter,))
            current_pitcher = db.fetch_one('''SELECT playerName, hand, pitchType, pitchBonus FROM playerData WHERE playerID=%s''', (current_pitcher,))
            if complete:
                winningPitcher = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (winningPitcher,))
                losingPitcher = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (losingPitcher,))
                save = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (save,))
                potg = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (potg,))

            b1 = '○'
            b2 = '○'
            b3 = '○'
            if obc in [1, 4, 5, 7]:
                b1 = '●'
            if obc in [2, 4, 6, 7]:
                b2 = '●'
            if obc in [3, 5, 6, 7]:
                b3 = '●'

            color = discord.Color(value=int(color, 16))
            title = f'{game[0].upper()} {game[1]}.{game[2]} | {awayTeam} vs. {homeTeam}'

            batter_name = current_batter[0]
            pitcher_name = current_pitcher[0]
            while len(batter_name) > 15:
                batter_name = batter_name.split(' ', 1)
                if len(batter_name) > 1:
                    batter_name = batter_name[1]
                else:
                    continue
            while len(pitcher_name) > 15:
                pitcher_name = pitcher_name.split(' ', 1)
                if len(pitcher_name) > 1:
                    pitcher_name = pitcher_name[1]
                else:
                    continue

            description = f'{pitcher_name: <15}  {current_pitcher[1][0]}|{current_pitcher[2]}-{current_pitcher[3]}\n'
            description += f'{batter_name: <15}  {current_batter[1][0]}|{current_batter[2]}\n\n'
            description += f'{awayTeam} {awayScore}     {b2}       '
            if complete:
                description += 'Final\n'
            else:
                description += '   {inning}\n'
            description += f'{homeTeam} {homeScore}   {b1}   {b3}     '
            if not complete:
                description += '{outs} Out'
            embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
            embed.set_thumbnail(url=src.assets.obc_img[str(obc)])
            if complete:
                embed.add_field(name='Winning Pitcher', value=winningPitcher)
                embed.add_field(name='Losing Pitcher', value=losingPitcher)
                embed.add_field(name='Save', value=save)
                embed.add_field(name='Player of the Game', value=potg)
            # embed.add_field(name='', value='')
            await ctx.send(embed=embed)
        return


def setup(bot):
    bot.add_cog(Game(bot))


def get_current_game(team: str):
    # TODO
    return


def create_game_embed():
    return
