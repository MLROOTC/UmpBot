from discord.ext import commands
import src.db_controller as db
import src.Ump.robo_ump as robo_ump


class Pitching(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    async def queue_pitch(self, ctx, pitch: int):
        if not ctx.guild:
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
                print_list += f'{await robo_ump.parse_pitch(ctx, int(pitch))}\n'
            await ctx.send(print_list)
        else:
            await ctx.send('This command only works in DMs.')

    @commands.command(brief='',
                      description='')
    async def clear_list(self, ctx):
        if not ctx.guild:
            game, home = await robo_ump.fetch_game(ctx, self.bot)
            sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            data = (None,) + game
            db.update_database(sql, data)
            await ctx.message.add_reaction('👍')
            return
        else:
            await ctx.send('This command only works in DMs.')
        return

    @commands.command(brief='',
                      description='')
    async def view_list(self, ctx):
        if not ctx.guild:
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
        else:
            await ctx.send('This command only works in DMs.')
        return

    @commands.command(brief='',
                      description='')
    async def change_pitch(self, ctx, pitch: int):
        if not ctx.guild:
            if not 0 < pitch <= 1000:
                await ctx.send('Not a valid pitch dum dum.')
                return
            game, home = await robo_ump.fetch_game(ctx, self.bot)
            current_pitch = db.fetch_one('''SELECT pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
            if current_pitch:
                db.update_database('''UPDATE pitchData SET pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
                await ctx.message.add_reaction('👍')
            else:
                await ctx.send("How do I change something that doesn't exist??")
            return
        else:
            await ctx.send('This command only works in DMs.')
        return

    @commands.command(brief='',
                      description='')
    async def steal_number(self, ctx, pitch: int):
        if not ctx.guild:
            if not 0 < pitch <= 1000:
                await ctx.send('Not a valid pitch dum dum.')
                return
            game, home = await robo_ump.fetch_game(ctx, self.bot)
            steal_number = db.fetch_one('''SELECT steal_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
            if steal_number:
                db.update_database('''UPDATE pitchData SET steal_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', game)
                await ctx.message.add_reaction('👍')
            else:
                await ctx.send("How do I change something that doesn't exist??")
        else:
            await ctx.send('This command only works in DMs.')
        return


def setup(bot):
    bot.add_cog(Pitching(bot))
