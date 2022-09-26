import discord
from discord.ext import commands
import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import pytz

config_ini = 'config.ini'


class Pitching(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='Bypass asking if they want to keep or change pitch on subs',
                      description='A per-user setting that allows pitchers to disable or enabled whether the bot prompts them to keep or change their pitch on batter substitions and conditional subs.')
    @commands.dm_only()
    async def always_keep(self, ctx, keep: bool):
        player_id = robo_ump.get_player_from_discord(ctx.author.id)
        db.update_database('UPDATE playerData SET keep_pitch=%s WHERE playerID=%s', (keep, player_id))
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Clear the pitcher\'s active list',
                      description='Clears the pitchers list from the datbase. This cannot be undone.')
    @commands.dm_only()
    async def clear_list(self, ctx):
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        data = (None,) + game
        db.update_database(sql, data)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Allows the pitcher to keep or change their pitch when there is a batter substitution',
                      description='When a batter sub comes through, the bot will prompt the original to keep or change their pitch. This command allows the pitcher to keep their pitch for the current at-bat only. To keep the same pitch on all substitutions, use .always_keep')
    @commands.dm_only()
    async def keep_pitch(self, ctx, keep: bool):
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        state = db.fetch_one('SELECT state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
        if state[0] == 'WAITING FOR PITCH CONFIRMATION':
            db.update_database('UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s', ('WAITING FOR PITCH CONFIRMATION',) + game)
            await ctx.message.add_reaction('👍')

    @commands.command(brief='Submit or change a pitch',
                      description='Submit a pitch for the current game. Or, if there is already a pitch on file, changes the pitch (if the swing is not already in).')
    @commands.dm_only()
    async def pitch(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        league, season, session, game_id = game
        pitch_src, swing_submitted, pitch_requested, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes = db.fetch_one('SELECT pitch_src, swing_submitted, pitch_requested, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes FROM pitchData WHERE  league=%s AND season=%s AND session=%s AND game_id=%s', game)
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
            await ctx.message.add_reaction('👍')
        if swing_submitted and not conditional_pitch_src:
            robo_ump.set_state(game[0], game[1], game[2], game[3], 'WAITING FOR RESULT')
        elif not conditional_pitch_src and not swing_submitted:
            robo_ump.set_state(game[0], game[1], game[2], game[3], 'WAITING FOR SWING')
        elif conditional_pitch_requested:
            sql = f'SELECT sheetID, threadURL, {home}Team FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'
            sheet_id, thread_url, team = db.fetch_one(sql, (league, season, session, game_id))
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            conditional_pitcher_name, conditional_pitcher_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (conditional_pitcher,))
            conditional_pitcher_discord = self.bot.get_user(int(conditional_pitcher_discord))
            conditional_pitcher_dm_channel = await conditional_pitcher_discord.create_dm()
            conditional_pitch_src = await conditional_pitcher_dm_channel.fetch_message(int(conditional_pitch_src))
            description = 'The pitch is in, but a conditional sub is in place. Please check if the conditions for the sub applied BEFORE the pitch came in.\n\nIf it does, please put the sub in the ump sheet before proceeding.'
            embed = discord.Embed(title='Conditional Pitch Check', description=description, color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='Pitch Requested', value=pitch_requested)
            embed.add_field(name='Pitch Submitted', value=ctx.message.created_at)
            embed.add_field(name='Conditional Pitcher', value=conditional_pitcher_name)
            embed.add_field(name='Conditional Pitcher ID', value=conditional_pitcher)
            embed.add_field(name='Conditional Pitch Requested', value=conditional_pitch_requested)
            embed.add_field(name='Conditional Pitch Submitted', value=conditional_pitch_src.created_at)
            embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})')
            embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
            ump_hq = robo_ump.read_config(config_ini, 'Channels', 'ump_hq')
            ump_hq = self.bot.get_channel(int(ump_hq))
            await ump_hq.send(embed=embed, view=robo_ump.auto_buttons(self.bot, embed, league, season, session, game_id))
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        else:
            print("I didn't think this would happen?")
        return

    @commands.command(brief='Add a pitch to a list',
                      description='Creates a pitch list if it does not exist. Only one pitch can be submitted at a time.')
    @commands.dm_only()
    async def queue_pitch(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
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

    @commands.command(brief='Submit a steal number to be used if the runner steals',
                      description='Submit a steal number separate from the pitch to be used if the runner steals on the current at-bat. Steal numbers are reset after each at-bat is resulted.')
    @commands.dm_only()
    async def steal_number(self, ctx, pitch: int):
        if not 0 < pitch <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game, home = await robo_ump.fetch_game(ctx, self.bot)
        league, season, session, game_id = game
        swing_src, = db.fetch_one('''SELECT swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (league, season, session, game_id))
        if not swing_src:
            db.update_database('''UPDATE pitchData SET steal_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (ctx.message.id, league, season, session, game_id))
            await ctx.message.add_reaction('👍')
        else:
            await ctx.send("Swing already submitted, cannot change pitch at this time.")

    @commands.command(brief='View the current list or pitches',
                      description='View the current list or pitches on file.')
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


async def setup(bot):
    await bot.add_cog(Pitching(bot))
