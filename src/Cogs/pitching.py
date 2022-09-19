from discord.ext import commands
import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import pytz


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
        pitch_src, swing_submitted = db.fetch_one('SELECT pitch_src, swing_submitted FROM pitchData WHERE  league=%s AND season=%s AND session=%s AND game_id=%s', game)
        if swing_submitted:
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
            print_list += f'{await robo_ump.parse_pitch(ctx, int(pitch))}\n'
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


async def setup(bot):
    await bot.add_cog(Pitching(bot))
