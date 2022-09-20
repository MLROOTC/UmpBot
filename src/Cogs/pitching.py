import discord
from discord.ext import commands
import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import pytz

config_ini = 'config.ini'


class Pitching(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def pitch(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid deprecated_pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        league, season, session, game_id = game
        pitch_src, swing_submitted, pitch_requested, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes = db.fetch_one('SELECT pitch_src, swing_submitted, pitch_requested, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes FROM pitchData WHERE  league=%s AND season=%s AND session=%s AND game_id=%s', game)
        if conditional_pitch_requested and not pitch_src:
            player_id, player_name = db.fetch_one('SELECT playerID, playerName FROM playerData WHERE discordID=%s', (ctx.author.id, ))
            sql = f'SELECT sheetID, threadURL, {home}Team FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'
            sheet_id, thread_url, team = db.fetch_one(sql, (league, season, session, game_id))
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            conditional_sub = f'**Pitcher:** {robo_ump.get_player_name(conditional_pitcher)}\n'
            conditional_sub += f'**Notes:** {conditional_pitch_notes}\n'
            conditional_sub += f'**Time:** {conditional_pitch_requested}\n'
            if conditional_pitch_src:
                conditional_sub += '**Pitch**: On file'
            else:
                conditional_sub += '**Pitch**: No swing on file'

            embed = discord.Embed(title='Conditional Pitch Check',
                                  description=f'{ctx.author.mention} has submitted a pitch but there is a conditional sub in place. Please check the conditions of the conditional sub and see whehter it should be used instead.',
                                  color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})')
            embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
            embed.add_field(name='Current Pitcher', value=player_name)
            embed.add_field(name='Pitch Requested', value=pitch_requested)
            embed.add_field(name='Conditional Pitch', value=conditional_sub, inline=False)

            ump_hq = robo_ump.read_config(config_ini, 'Channels', 'ump_hq')
            ump_hq = self.bot.get_channel(int(ump_hq))
            await ump_hq.send(embed=embed, view=robo_ump.auto_buttons(self.bot, embed, league, season, session, game_id))
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        if swing_submitted and pitch_src:
            swing_submitted = pytz.utc.localize(swing_submitted)
            if swing_submitted < ctx.message.created_at:
                await ctx.send('Swing already submitted, cannot change pitch at this time.')
                return
        else:
            if pitch_src:
                await ctx.send(f'Changing pitch from {await robo_ump.parse_pitch(self.bot, ctx.author.id, int(pitch_src))} to {pitch}.')
                sql = '''UPDATE pitchData SET pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                data = (ctx.message.id,) + game
            else:
                sql = '''UPDATE pitchData SET pitch_src=%s, pitch_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                data = (ctx.message.id, ctx.message.created_at) + game
            db.update_database(sql, data)
            if swing_submitted:
                robo_ump.set_state(game[0], game[1], game[2], game[3], 'WAITING FOR RESULT')
            else:
                robo_ump.set_state(game[0], game[1], game[2], game[3], 'WAITING FOR SWING')
            await ctx.message.add_reaction('👍')
        return

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def queue_pitch(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid deprecated_pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        sql = f'''SELECT list_{home} FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        current_list = db.fetch_one(sql, game)
        if not current_list[0]:
            current_list = ''
        else:
            current_list = current_list[0]
        current_list += f'{ctx.message.id} '
        sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        data = (current_list,) + game
        db.update_database(sql, data)
        await ctx.message.add_reaction('👍')
        current_list = current_list.split()
        print_list = '**Current List:**\n'
        for pitch in current_list:
            print_list += f'{await robo_ump.parse_pitch(self.bot, ctx.author.id, int(pitch))}\n'
        await ctx.send(print_list)

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def clear_list(self, ctx):
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        data = (None,) + game
        db.update_database(sql, data)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def view_list(self, ctx):
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        sql = f'''SELECT list_{home} FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        current_list = db.fetch_one(sql, game)
        if current_list[0]:
            current_list = current_list[0].split()
            print_list = '**Current List:**\n'
            for pitch in current_list:
                message = await ctx.fetch_message(int(pitch))
                message = message.content.replace('.queue_pitch ', '')
                print_list += f'{message}\n'
            await ctx.send(print_list)
        else:
            await ctx.send('Current list is empty.')

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def change_pitch(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid deprecated_pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        current_pitch = db.fetch_one('''SELECT pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
        if current_pitch:
            db.update_database('''UPDATE pitchData SET pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
            await ctx.message.add_reaction('👍')
        else:
            await ctx.send("How do I change something that doesn't exist??")
        return

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def steal_number(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid deprecated_pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        steal_number = db.fetch_one('''SELECT steal_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
        if steal_number:
            db.update_database('''UPDATE pitchData SET steal_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
            await ctx.message.add_reaction('👍')
        else:
            await ctx.send("How do I change something that doesn't exist??")

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def keep_pitch(self, ctx, keep: bool):
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        state = db.fetch_one('SELECT state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
        if state[0] == 'WAITING FOR PITCH CONFIRMATION':
            db.update_database('UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s', ('WAITING FOR PITCH CONFIRMATION',) + game)
            await ctx.message.add_reaction('👍')

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def always_keep(self, ctx, keep: bool):
        player_id = robo_ump.get_player_from_discord(ctx.author.id)
        db.update_database('UPDATE playerData SET keep_pitch=%s WHERE playerID=%s', (keep, player_id))
        await ctx.message.add_reaction('👍')


async def setup(bot):
    await bot.add_cog(Pitching(bot))
