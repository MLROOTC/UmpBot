from discord.ext import commands
import src.db_controller as db


class Pitching(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='',
                      description='')
    async def queue_pitch(self, ctx):
        if not ctx.guild:
            game, home = await fetch_game(ctx, self.bot)
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
            current_list = current_list.split()
            print_list = '**Current List:**\n'
            for pitch in current_list:
                message = await ctx.fetch_message(int(pitch))
                message = message.content.replace('.queue_pitch ', '')
                print_list += f'{message}\n'
            await ctx.send(print_list)
        else:
            await ctx.send('This command only works in DMs.')

    @commands.command(brief='',
                      description='')
    async def clear_list(self, ctx):
        if not ctx.guild:
            game, home = await fetch_game(ctx, self.bot)
            sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            data = (None,) + game
            db.update_database(sql, data)
            await ctx.send('List cleared.')
            return
        else:
            await ctx.send('This command only works in DMs.')
        return

    @commands.command(brief='',
                      description='')
    async def view_list(self, ctx):
        if not ctx.guild:
            game, home = await fetch_game(ctx, self.bot)
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
    async def change_pitch(self, ctx):
        if not ctx.guild:
            game, home = await fetch_game(ctx, self.bot)
            return
        else:
            await ctx.send('This command only works in DMs.')
        return

    @commands.command(brief='',
                      description='')
    async def steal_number(self, ctx):
        if not ctx.guild:
            game, home = await fetch_game(ctx, self.bot)
            return
        else:
            await ctx.send('This command only works in DMs.')
        return


def setup(bot):
    bot.add_cog(Pitching(bot))


async def fetch_game(ctx, bot):
    pitcher_id = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (ctx.author.id,))
    if pitcher_id:
        active_games = db.fetch_data('''SELECT league, season, session, game_id, home_pitcher, away_pitcher FROM pitchData WHERE (home_pitcher=%s OR away_pitcher=%s)''', (pitcher_id[0], pitcher_id[0]))
        if not active_games:
            await ctx.send("I couldn't find any active games you are pitching in.")
            return None
        if len(active_games) == 1:
            if active_games[0][4] == pitcher_id[0]:
                return active_games[0][0:4], 'home'
            elif active_games[0][5] == pitcher_id[0]:
                return active_games[0][0:4], 'away'
            else:
                await ctx.send('Are you even pitching right now??')
        else:
            prompt = f'**Multiple games found. Please select a game:** \n```'
            for i in range(len(active_games)):
                game = active_games[i]
                game_data = db.fetch_one('''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', game[0:4])
                prompt += f'{i+1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if game[4] == pitcher_id[0]:
                return active_games[game_number-1][0:4], 'home'
            elif game[5] == pitcher_id[0]:
                return active_games[game_number-1][0:4], 'away'
            else:
                await ctx.send('Are you even pitching right now??')
    else:
        await ctx.send("I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None
