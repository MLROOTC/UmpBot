import configparser
import discord
from discord.ext import commands

import src.assets
import src.db_controller as db
import src.Ump.robo_ump as robo_ump

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ump_hq = self.bot.get_channel(int(config_ini['Channels']['ump_hq']))

    @commands.command(brief='',
                      description='')
    async def dm_swing(self, ctx, swing: int):
        if not ctx.guild:
            if not 0 < swing <= 1000:
                await ctx.send('Not a valid pitch dum dum.')
                return
            game, home = await robo_ump.fetch_game(ctx, self.bot)
            data = (ctx.message.id, ctx.message.created_at) + game
            db.update_database('''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
            await ctx.message.add_reaction('👍')
            return
        else:
            await ctx.send('This command only works in DMs.')
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
    async def request_sub(self, ctx, team: str, player_out: str, player_in: str, position: str):
        # TODO

        return

    @commands.command(brief='',
                      description='')
    async def request_position_change(self, ctx, team: str, player: str, old_pos: str, new_pos: str):
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
        game = fetch_game(team, season, session)
        if game:
            game = fetch_game(team, season, session)
            sql = '''SELECT awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
            awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg = db.fetch_one(sql, game)
            sql = '''SELECT current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src = db.fetch_one(sql, game)
            color, logo = db.fetch_one('''SELECT color, logo_url FROM teamData WHERE abb=%s''', (team,))
            current_batter = db.fetch_one('''SELECT playerName, hand, batType FROM playerData WHERE playerID=%s''', (current_batter,))
            current_pitcher = db.fetch_one('''SELECT playerName, hand, pitchType, pitchBonus FROM playerData WHERE playerID=%s''', (current_pitcher,))

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
            if complete:
                description = ''
            else:
                description = f'{pitcher_name: <15}  {current_pitcher[1][0]}|{current_pitcher[2]}-{current_pitcher[3]}\n'
                description += f'{batter_name: <15}  {current_batter[1][0]}|{current_batter[2]}\n\n'
            description += f'{awayTeam: <4} {awayScore: <2}     {b2}     '
            if complete:
                description += 'Final\n'
            else:
                description += f'   {inning}\n'
            description += f'{homeTeam: <4} {homeScore: <2}   {b1}   {b3}   '
            if not complete:
                description += f'{outs} Out'
            embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
            embed.set_thumbnail(url=src.assets.obc_img[str(obc)])
            if complete:
                embed.add_field(name='Winning Pitcher', value=robo_ump.get_player_name(winningPitcher), inline=True)
                embed.add_field(name='Losing Pitcher', value=robo_ump.get_player_name(losingPitcher), inline=True)
                if save:
                    embed.add_field(name='Save', value=robo_ump.get_player_name(save), inline=True)
                embed.add_field(name='Player of the Game', value=robo_ump.get_player_name(potg), inline=True)
            else:
                if pitch_requested:
                    if pitch_src:
                        embed.add_field(name='Pitch', value=f'Pitch submitted at {pitch_submitted}', inline=True)
                    else:
                        embed.add_field(name='Pitch', value=f'Pitch request sent at {pitch_requested}', inline=True)
                else:
                    embed.add_field(name='Pitch', value='-', inline=True)
                if swing_requested:
                    if swing_src:
                        embed.add_field(name='Swing', value=f'Swing submitted at {swing_submitted}', inline=True)
                    else:
                        embed.add_field(name='Swing', value=f'AB posted at {swing_requested}', inline=True)
                else:
                    embed.add_field(name='Swing', value='-', inline=True)
                if conditional_pitch_requested:
                    if conditional_pitch_src:
                        embed.add_field(name='Conditional Pitch', value='Conditional pitch submitted.', inline=False)
                    else:
                        embed.add_field(name='Conditional Pitch', value='Waiting for pitch.', inline=False)
                else:
                    embed.add_field(name='Conditional Pitch', value='-', inline=False)
                if conditional_swing_requested:
                    if conditional_swing_src:
                        embed.add_field(name='Conditional Swing', value='Conditional swing submitted.', inline=True)
                    else:
                        embed.add_field(name='Conditional Pitch', value='Waiting for swing.', inline=True)
                else:
                    embed.add_field(name='Conditional Swing', value='-', inline=True)
            await ctx.send(embed=embed)
        return


async def setup(bot):
    await bot.add_cog(Game(bot))


def get_current_game(team: str):
    # TODO
    return


def fetch_game(team, season, session):
    if season and session:
        sql = '''SELECT league, season, session, gameID FROM gameData WHERE (awayTeam=%s OR homeTeam=%s) AND (season=%s AND session=%s) ORDER BY league, season, session, gameID'''
        data = (team, team, season, session)
    else:
        sql = '''SELECT league, season, session, gameID FROM gameData WHERE awayTeam=%s OR homeTeam=%s ORDER BY league, season, session, gameID'''
        data = (team, team)
    games = db.fetch_data(sql, data)
    if games:
        return games[-1]
    return None
