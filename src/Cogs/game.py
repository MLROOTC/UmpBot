import configparser
import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import src.reddit_interface as reddit
import src.assets as assets
import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.sheets_reader as sheets

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')
league_ini = configparser.ConfigParser()
league_ini.read('league.ini')

ump_warden_role = int(config_ini['Discord']['ump_warden_role'])
umpire_role = int(config_ini['Discord']['umpire_role'])
ump_helper_role = int(config_ini['Discord']['ump_helper'])
lom_role = int(config_ini['Discord']['lom_role'])
standings_channel = int(config_ini['Channels']['standings_channel'])


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ump_hq = self.bot.get_channel(int(config_ini['Channels']['ump_hq']))

    @commands.command(brief='Update database with missing PA Logs',
                      description='Update database with missing PA Logs',
                      aliases=['audit'])
    @commands.has_role(lom_role)
    async def audit_games(self, ctx, season: int = None, session: int = None):
        games = db.fetch_data('SELECT sheetID, awayTeam FROM gameData WHERE season=%s AND session=%s AND complete=%s', (season, session, 0))
        for game in games:
            sheet_id, team = game
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            await ctx.send(f'Auditing game log for {league.upper()} {season}.{session}.{game_id}...')
            robo_ump.audit_game_log(league, season, session, game_id, sheet_id)
        await ctx.send('Done.')

    @commands.command(brief='Checks a reddit comment to see if it contains a valid swing',
                      description='Checks a given reddit comment to see if it contains a valid swing. This is typically done automatically by a separate script, but sometimes reddit sux and we need a way to trigger it outside of the reddit_watcher script. ',
                      aliases=['checkswing', 'check'])
    @commands.has_role(umpire_role)
    async def check_swing(self, ctx, reddit_comment: str):
        await robo_ump.get_swing_from_reddit_async(reddit_comment)
        await ctx.message.add_reaction('⚾')
        return

    @commands.command(brief='Set up a conditional sub for the current pitcher',
                      description='Logs the time the conditional pitch was requested, prompts the pitcher for a conditional pitch, waits for a response, and then logs the conditional pitch and time responded to in the database. If the original pitcher submits a pitch, the bot will automatically request that an umpire verify that the conditions of the sub have not been met before proceeding with the current ab-bat.',
                      aliases=['conditionalpitch'])
    async def conditional_pitch(self, ctx, team: str, pitcher: discord.Member, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            notes = '-'
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            game = robo_ump.fetch_game_team(team, season, session)
            league, season, session, game_id = game
            conditional_pitcher = robo_ump.get_player_from_discord(pitcher.id)
            if conditional_pitcher:
                conditional_pitch_requested = robo_ump.convert_to_unix_time(ctx.message.created_at)
                data = (conditional_pitcher, conditional_pitch_requested, notes, league, season, session, game_id)
                sql = '''UPDATE pitchData SET conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                db.update_database(sql, data)
                await pitcher.send(f'{ctx.author.mention} has requested a conditional pitch for {team.upper()}. Please reply with a pitch number to be used at the following condition: {notes}')
                robo_ump.log_msg(f'Conditional pitch requested for {league} {season}.{session}.{game_id} - {pitcher}({conditional_pitcher})')

                def wait_for_response(msg):
                    return msg.content.isnumeric() and 0 < int(msg.content) <= 1000 and msg.author == pitcher and msg.channel.guild is None

                await ctx.send('Conditional pitch request sent to pitcher.')
                conditional_pitch = await self.bot.wait_for('message', check=wait_for_response)
                # check to make sure the GM didn't do a second conditional sub afterwards and they are still the conditional pitcher
                conditional_pitcher_id, = db.fetch_one('SELECT conditional_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
                if conditional_pitcher == conditional_pitcher_id:
                    sql = '''UPDATE pitchData SET conditional_pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                    db.update_database(sql, (conditional_pitch.id,) + game)
                    robo_ump.log_msg(f'Conditional pitch submitted for {league} {season}.{session}.{game_id}')
                    await conditional_pitch.add_reaction('👍')
                    await ctx.send('Conditional pitch submitted.')
                else:
                    await pitcher.send('Conditional pitch is no longer necessary.')
            else:
                await ctx.send(f'Could not find a player account linked to {pitcher}')

    @commands.command(brief='Set up a conditional sub for the current batter',
                      description='Logs the time the conditional swing was requested, prompts the conditional batter for a swing, waits for a response, and then logs the conditional swing and time they responded to in the database. If the original batter submits a swing, the bot will automatically request that an umpire verify that the conditions of the sub have not been met before proceeding with the current ab-bat.',
                      aliases=['conditionalswing'])
    async def conditional_swing(self, ctx, team: str, batter: discord.Member, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            notes = '-'
            await ctx.message.add_reaction('👍')
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            game = robo_ump.fetch_game_team(team, season, session)
            league, season, session, game_id = game
            season, session = robo_ump.get_current_session(team)
            game = robo_ump.fetch_game_team(team, season, session)
            conditional_batter = robo_ump.get_player_from_discord(batter.id)
            if conditional_batter:
                conditional_swing_requested = robo_ump.convert_to_unix_time(ctx.message.created_at)
                data = (conditional_batter, conditional_swing_requested, notes) + game
                sql = '''UPDATE pitchData SET conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                db.update_database(sql, data)
                await batter.send(f'{ctx.author.mention} has requested a conditional swing for {team.upper()}. Please reply with a swing number to be used at the following condition: {notes}')
                robo_ump.log_msg(f'Conditional swing requested for {league} {season}.{session}.{game_id} - {batter}({conditional_batter})')

                def wait_for_response(msg):
                    return msg.content.isnumeric() and 0 < int(msg.content) <= 1000 and msg.author == batter and msg.channel.guild is None

                await ctx.send('Conditional swing request sent to batter.')
                conditional_swing = await self.bot.wait_for('message', check=wait_for_response)
                conditional_batter_id, = db.fetch_one('SELECT conditional_batter FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
                if conditional_batter == conditional_batter_id:
                    sql = '''UPDATE pitchData SET conditional_swing_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                    db.update_database(sql, (conditional_swing.id,) + game)
                    robo_ump.log_msg(f'Conditional swing submitted for {league} {season}.{session}.{game_id}')
                    await conditional_swing.add_reaction('👍')
                    await ctx.send('Conditional swing submitted.')
                else:
                    await batter.send('Conditional swing is no longer necessary.')
            else:
                await ctx.send(f'Could not find a player account linked to {batter}')

    @commands.command(brief='Swing via Discord DM',
                      description='Submit a swing to the bot via Discord DM',
                      aliases=['swing'])
    @commands.dm_only()
    async def dm_swing(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_swing(ctx, self.bot)
        data = (ctx.message.id, robo_ump.convert_to_unix_time(ctx.message.created_at)) + game
        league, season, session, game_id = game
        dm_channel = await ctx.author.create_dm()
        robo_ump.log_msg(f'{league} {season}.{season}.{game_id} Player ID:{robo_ump.get_player_from_discord(ctx.author.id)}:DiscordID:{ctx.author.id}:ChannelID:{ctx.channel.id}:MessageID:{ctx.message.id}:DM Channel:{ctx.author.dm_channel.id}:DM Channel:{dm_channel.id}:D')
        db.update_database('''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        state, = db.fetch_one('SELECT state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
        pitch_src, = db.fetch_one('SELECT pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
        await ctx.message.add_reaction('👍')
        if pitch_src and state != 'PAUSED':
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
        robo_ump.log_msg(f'{ctx.author.name} swung via DM for {game[0]} {game[1]}.{game[2]}.{game[3]} ')

    @commands.command(brief='Set awards and close out the game in the database',
                      description='Set awards, update the game thread, adudit the game log, clear out pitch data from the database, marks the game as complete, and sends an endgame ping in main.')
    @commands.has_role(umpire_role)
    async def finalize(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        away_team, away_score, home_team, home_score, reddit_thread, = db.fetch_one('SELECT awayTeam, awayScore, homeTeam, homeScore, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)

        scoring_plays = sheets.read_sheet(sheet_id, assets.calc_cell2['scoring_plays'])
        pitcher_performance = sheets.read_sheet(sheet_id, assets.calc_cell2['pitcher_performance'])
        line_score = sheets.read_sheet(sheet_id, assets.calc_cell2['line_score'])
        line_1 = line_score[0][0]
        line_1 = line_1.replace('|', ' ')
        line_1 = line_1.replace('*', '')
        line_2 = line_score[2][0]
        line_2 = line_2.replace('|', ' ')
        line_2 = line_2.replace('*', '')
        line_3 = line_score[3][0]
        line_3 = line_3.replace('|', ' ')
        line_3 = line_3.replace('*', '')

        confirm = Button(label="Finalize Game", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

        async def send_request(interaction):
            await interaction.response.defer(thinking=True)
            awards = sheets.read_sheet(sheet_id, assets.calc_cell2['awards'])[0]
            if len(awards) == 4:
                await interaction.message.edit(content='Closing out game', view=None, embed=embed)
                # Get awards from game sheet
                winning_pitcher = awards[0]
                losing_pitcher = awards[1]
                save = awards[2]
                potg = awards[3]
                winning_pitcher_id = robo_ump.get_player_id(winning_pitcher)
                losing_pitcher_id = robo_ump.get_player_id(losing_pitcher)
                save_id = robo_ump.get_player_id(save)
                potg_id = robo_ump.get_player_id(potg)

                # Update backend of the sheet and update the game thread
                robo_ump.set_state(league, season, session, game_id, 'FINALIZING')
                sheets.update_sheet(sheet_id, assets.calc_cell2['game_complete'], True)
                sheets.update_sheet(sheet_id, assets.calc_cell2['current_situation'], False)
                sheets.update_sheet(sheet_id, assets.calc_cell2['next_up'], False)
                sheets.update_sheet(sheet_id, assets.calc_cell2['due_up'], False)
                await reddit.edit_thread(reddit_thread, robo_ump.get_box_score(sheet_id))

                # Update the database
                sql = 'UPDATE pitchData SET home_pitcher=%s, away_pitcher=%s, current_pitcher=%s, current_batter=%s, pitch_requested=%s, pitch_submitted=%s, pitch_src=%s, steal_src=%s, list_home=%s, list_away=%s, swing_requested=%s, swing_submitted=%s, swing_src=%s, conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s, conditional_pitch_notes=%s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'
                data = (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, league, season, session, game_id)
                db.update_database(sql, data)
                sql = 'UPDATE gameData SET complete=%s, winningPitcher=%s, losingPitcher=%s, save=%s, potg=%s, state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s'
                data = (True, winning_pitcher_id, losing_pitcher_id, save_id, potg_id, 'COMPLETE', league, season, session, game_id)
                db.update_database(sql, data)

                # ping in main
                role_ids = db.fetch_data('SELECT role_id FROM teamData WHERE abb=%s OR abb=%s', (away_team, home_team))
                game_discussion_ping = ''
                for role in role_ids:
                    game_discussion_ping += f'<@&{role[0]}> '
                for i in range(len(embed.fields)):
                    if embed.fields[i].name == 'Ump Sheet':
                        embed.remove_field(i)
                embed.add_field(name='Winning Pitcher', value=winning_pitcher)
                embed.add_field(name='Losing Pitcher', value=losing_pitcher)
                if save:
                    embed.add_field(name='Save', value=save)
                embed.add_field(name='Player of the Game', value=potg)
                channel = robo_ump.get_game_discussion(self.bot, league)
                await channel.send(content=game_discussion_ping, embed=embed)
                await interaction.followup.send(content='Game closed.')
                if (1 <= session <= 16) and league.upper() in 'MLR':
                    standings = self.bot.get_channel(standings_channel)
                    await standings.send(f'<@140306370359459840> game complete: {away_team} {away_score} - {home_team} {home_score}')

        async def cancel_request(interaction):
            await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
            return

        confirm.callback = send_request
        cancel.callback = cancel_request

        view = View(timeout=None)

        view.add_item(confirm)
        view.add_item(cancel)

        # Scoring plays
        scoring_play_list = ''
        if scoring_plays:
            for scoring_play in scoring_plays:
                scoring_play_list += f'{scoring_play[0]}\n'
        # Pitcher performance
        pitcher_list = ''
        for line in pitcher_performance:
            if line:
                pitcher_pair = line[0].split('|')
                pitcher_1_name = pitcher_pair[0]
                pitcher_1_ip = pitcher_pair[1]
                pitcher_1_h = pitcher_pair[2]
                pitcher_1_er = pitcher_pair[3]
                pitcher_1_BB = pitcher_pair[4]
                pitcher_1_SO = pitcher_pair[5]
                pitcher_1_ERA = pitcher_pair[6]
                if pitcher_1_name != '--':
                    pitcher_list += f'**{pitcher_1_name}** - **{pitcher_1_ip}** IP **{pitcher_1_h}** H **{pitcher_1_er}** ER **{pitcher_1_BB}**  BB **{pitcher_1_SO}** Ks **{pitcher_1_ERA}**'
                    if pitcher_1_ERA != 'Pitching Debut':
                        pitcher_list += ' ERA'
                    pitcher_list += '\n'
                if len(pitcher_pair) >= 13:
                    pitcher_2_name = pitcher_pair[7]
                    pitcher_2_ip = pitcher_pair[8]
                    pitcher_2_h = pitcher_pair[9]
                    pitcher_2_er = pitcher_pair[10]
                    pitcher_2_BB = pitcher_pair[11]
                    pitcher_2_SO = pitcher_pair[12]
                    pitcher_2_ERA = pitcher_pair[13]
                    if pitcher_2_name != '--':
                        pitcher_list += f'**{pitcher_2_name}** - **{pitcher_2_ip}** IP **{pitcher_2_h}** H **{pitcher_2_er}** ER **{pitcher_2_BB}**  BB **{pitcher_2_SO}** Ks **{pitcher_2_ERA}**'
                        if pitcher_2_ERA != 'Pitching Debut':
                            pitcher_list += ' ERA'
                        pitcher_list += '\n'

        embed = discord.Embed(title=f'{away_team} @ {home_team}', description=f'**Final Score**\n```   {line_1}\n{line_2}\n{line_3}```\r\n**{away_team.upper()}** - {away_score}\n**{home_team.upper()}** - {home_score}')
        embed.add_field(name='Scoring Plays', value=f'```{scoring_play_list}```', inline=False)
        embed.add_field(name='Pitching Lines', value=f'{pitcher_list}', inline=False)
        embed.add_field(name='Game Thread', value=f'[Link]({reddit_thread})')
        embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
        await ctx.send(content=f'Open the **Ump Sheet** and set the awards on the **Calc** tab. When done, click the **Finalize Game** button.', embed=embed, view=view)

    @commands.command(brief='Forces the bot to result an at-bat',
                      description='Forces the bot to result an at-bat',
                      aliases=['force'])
    @commands.has_role(umpire_role)
    async def force_result(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        await robo_ump.result(self.bot, league, season, session, game_id)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Get the current game state',
                      description='Get the current game state',
                      aliases=['state', 'gamestate', 'game'])
    async def game_state(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        game = robo_ump.fetch_game_team(team, season, session)
        if game:
            sql = '''SELECT sheetID, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
            sheet_id, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg, state = db.fetch_one(sql, game)
            sql = '''SELECT current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src = db.fetch_one(sql, game)
            color, logo = db.fetch_one('''SELECT color, logo_url FROM teamData WHERE abb=%s''', (team,))
            color = discord.Color(value=int(color, 16))
            title = f'{game[0].upper()} {game[1]}.{game[2]} | {awayTeam} vs. {homeTeam}'
            embed = discord.Embed(title=title, color=color, url=threadURL)
            if state in ['SETUP', 'WAITING FOR LINEUPS']:
                description = f'{awayTeam: <4} {awayScore: <2}     ○     T1\n'
                description += f'{homeTeam: <4} {homeScore: <2}   ○   ○   {outs} Out'
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
            elif state in ['WAITING FOR PITCH', 'WAITING FOR SWING', 'WAITING FOR RESULT', 'SUB REQUESTED', 'AUTO REQUESTED', 'WAITING FOR PITCHER CONFIRMATION', 'WAITING FOR UMP CONFIRMATION', 'PAUSED']:
                matchup_names = sheets.read_sheet(sheet_id, assets.calc_cell2['current_matchup'])
                matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
                scoring_plays = sheets.read_sheet(sheet_id, assets.calc_cell2['scoring_plays'])
                pitcher_performance = sheets.read_sheet(sheet_id, assets.calc_cell2['pitcher_performance'])
                line_score = sheets.read_sheet(sheet_id, assets.calc_cell2['line_score'])

                line_1 = line_score[0][0]
                line_1 = line_1.replace('|', ' ')
                line_1 = line_1.replace('*', '')
                line_2 = line_score[2][0]
                line_2 = line_2.replace('|', ' ')
                line_2 = line_2.replace('*', '')
                line_3 = line_score[3][0]
                line_3 = line_3.replace('|', ' ')
                line_3 = line_3.replace('*', '')
                line_score = f"   {line_1}\n{line_2}\n{line_3}"

                scoring_play_list = ''
                if scoring_plays:
                    for scoring_play in scoring_plays:
                        scoring_play_list += f'{scoring_play[0]}\n'

                pitcher_list = ''
                for line in pitcher_performance:
                    pitcher_pair = line[0].split('|')
                    pitcher_1_name = pitcher_pair[0]
                    pitcher_1_ip = pitcher_pair[1]
                    pitcher_1_h = pitcher_pair[2]
                    pitcher_1_er = pitcher_pair[3]
                    pitcher_1_BB = pitcher_pair[4]
                    pitcher_1_SO = pitcher_pair[5]
                    pitcher_1_ERA = pitcher_pair[6]
                    if pitcher_1_name != '--':
                        pitcher_list += f'**{pitcher_1_name}** - **{pitcher_1_ip}** IP **{pitcher_1_h}** H **{pitcher_1_er}** ER **{pitcher_1_BB}**  BB **{pitcher_1_SO}** Ks **{pitcher_1_ERA}**'
                        if pitcher_1_ERA != 'Pitching Debut':
                            pitcher_list += ' ERA'
                        pitcher_list += '\n'
                    if len(pitcher_pair) >= 13:
                        pitcher_2_name = pitcher_pair[7]
                        pitcher_2_ip = pitcher_pair[8]
                        pitcher_2_h = pitcher_pair[9]
                        pitcher_2_er = pitcher_pair[10]
                        pitcher_2_BB = pitcher_pair[11]
                        pitcher_2_SO = pitcher_pair[12]
                        pitcher_2_ERA = pitcher_pair[13]
                        if pitcher_2_name != '--':
                            pitcher_list += f'**{pitcher_2_name}** - **{pitcher_2_ip}** IP **{pitcher_2_h}** H **{pitcher_2_er}** ER **{pitcher_2_BB}**  BB **{pitcher_2_SO}** Ks **{pitcher_2_ERA}**'
                            if pitcher_2_ERA != 'Pitching Debut':
                                pitcher_list += ' ERA'
                            pitcher_list += '\n'
                if matchup_names:
                    batter_name = matchup_names[0][0]
                    pitcher_name = matchup_names[0][2]
                else:
                    return None
                if matchup_info:
                    batter_id, batter_type, batter_hand, pitcher_id, pitcher_type, pitcher_hand, pitcher_bonus = matchup_info[0]
                else:
                    return None

                # Setting up OBC text
                b1 = '○'
                b2 = '○'
                b3 = '○'
                if obc in [1, 4, 5, 7]:
                    b1 = '●'
                if obc in [2, 4, 6, 7]:
                    b2 = '●'
                if obc in [3, 5, 6, 7]:
                    b3 = '●'

                # Shorten names to last name only if longer than 15 characters
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

                description = f'{line_score}\n\n'
                current_at_bat = f'{awayTeam: <4} {awayScore: <2}     {b2}        {inning}\n'
                current_at_bat += f'{homeTeam: <4} {homeScore: <2}   {b3}   {b1}   {outs} Out\n\n'
                current_at_bat += f'{pitcher_name: <15}  {pitcher_hand[0]}|{pitcher_type}-{pitcher_bonus}\n'
                current_at_bat += f'{batter_name: <15}  {batter_hand[0]}|{batter_type}'
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
                embed.add_field(name='Current At Bat', value=f'```{current_at_bat}```', inline=False)
                if pitch_requested:
                    if pitch_src:
                        embed.add_field(name='Pitch', value=f'Pitch submitted at <t:{pitch_submitted}:T>', inline=True)
                    else:
                        embed.add_field(name='Pitch', value=f'Pitch request sent at <t:{pitch_requested}:T>', inline=True)
                else:
                    embed.add_field(name='Pitch', value='-', inline=True)
                if swing_requested:
                    if swing_src:
                        embed.add_field(name='Swing', value=f'Swing submitted at <t:{swing_submitted}:T>', inline=True)
                    else:
                        embed.add_field(name='Swing', value=f'AB posted at <t:{swing_requested}:T>', inline=True)
                else:
                    embed.add_field(name='Swing', value='-', inline=True)
                if conditional_pitch_requested:
                    if conditional_pitch_src:
                        embed.add_field(name='Conditional Pitch', value='Conditional pitch submitted', inline=True)
                    else:
                        embed.add_field(name='Conditional Pitch', value='Waiting for pitch', inline=True)
                else:
                    embed.add_field(name='Conditional Pitch', value='-', inline=True)
                if conditional_swing_requested:
                    if conditional_swing_src:
                        embed.add_field(name='Conditional Swing', value='Conditional swing submitted', inline=True)
                    else:
                        embed.add_field(name='Conditional Swing', value='Waiting for swing', inline=True)
                else:
                    embed.add_field(name='Conditional Swing', value='-', inline=True)
                if scoring_play_list:
                    embed.add_field(name='Scoring Plays', value=f'```{scoring_play_list}```', inline=False)
                else:
                    embed.add_field(name='Scoring Plays', value=f'-', inline=False)
                if pitcher_list:
                    embed.add_field(name='Pitching Lines', value=f'{pitcher_list}', inline=False)
            elif state in ['FINALIZING', 'COMPLETE']:
                description = f'{awayTeam: <4} {awayScore: <2}     ○     Final\n'
                description += f'{homeTeam: <4} {homeScore: <2}   ○   ○   '
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
                if complete:
                    embed.add_field(name='Winning Pitcher', value=robo_ump.get_player_name(winningPitcher), inline=True)
                    embed.add_field(name='Losing Pitcher', value=robo_ump.get_player_name(losingPitcher), inline=True)
                    if save:
                        embed.add_field(name='Save', value=robo_ump.get_player_name(save), inline=True)
                    embed.add_field(name='Player of the Game', value=robo_ump.get_player_name(potg), inline=True)
            embed.set_thumbnail(url=logo)
            embed.add_field(name='Status', value=state.title())
            embed.add_field(name='View on Reddit', value=f'[Link]({threadURL})')
            await ctx.send(embed=embed)
        return

    @commands.command(brief='GM Steal via DM',
                      description='Allows GMs to submit steals via discord DM.',
                      aliases=['gmsteal'])
    @commands.dm_only()
    async def gm_steal(self, ctx, team: str, swing: int):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            # TODO restrict to only the GM of the team that's currently batting
            if not 0 < swing <= 1000:
                await ctx.send('Not a valid pitch dum dum.')
                return
            steal_type_options = []
            for steal_type in assets.steal_types:
                steal_type_options.append(discord.SelectOption(label=steal_type))
            steal_type_select = Select(placeholder='Steal Type', options=steal_type_options)

            async def steal_dropdown(interaction):
                await interaction.response.defer()
                season, session = robo_ump.get_current_session(team)
                league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
                sheet_id = robo_ump.get_sheet(league, season, session, game_id)
                gm_player_id = robo_ump.get_player_from_discord(ctx.author.id)
                data = (ctx.message.id, robo_ump.convert_to_unix_time(ctx.message.created_at), gm_player_id, league, season, session, game_id)
                event = robo_ump.set_event(sheet_id, steal_type_select.values[0])
                db.update_database('''UPDATE pitchData SET swing_src=%s, swing_submitted=%s, current_batter=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
                await ctx.message.add_reaction('👍')
                await ctx.send(f'Event set to {event}')
                robo_ump.log_msg(f'{ctx.author.name} issued a GM steal via DMs for {league} {season}.{session}.{game_id}')
                sql = 'SELECT pitch_requested, pitch_src, swing_requested, swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'
                pitch_requested, pitch_src, swing_requested, swing_src = db.fetch_one(sql, (league, season, session, game_id))
                if pitch_src and swing_src:
                    robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
                return

            view = View(timeout=None)
            steal_type_select.callback = steal_dropdown
            view.add_item(steal_type_select)
            await ctx.send(f'**Select steal type**', view=view)

    @commands.command(brief='Intentionally walk a batter',
                      description='Intentionally walk a batter',
                      aliases=['hbp'])
    async def ibb(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        current_pitcher, pitch_submitted, swing_requested, swing_submitted = db.fetch_one('SELECT current_pitcher, pitch_submitted, swing_requested, swing_submitted FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
        player_id = robo_ump.get_player_from_discord(ctx.author.id)
        if robo_ump.player_is_allowed(ctx.author.id, team) or (ctx.guild is None and player_id == current_pitcher):
            event = robo_ump.set_event(sheet_id, 'IBB')
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
            await ctx.send(f'Event set to {event}')
            robo_ump.log_msg(f'{ctx.author.name} issued an IBB for {league} {season}.{session}.{game_id}')

    @commands.command(brief='Set the infield in for the current at bat',
                      description='Set the infield in for the current at bat. Re-posts the at bat ping if one has already been posted.',
                      aliases=['ifin', 'infieldin', 'if_in'])
    async def infield_in(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        current_pitcher, pitch_submitted, swing_requested, swing_submitted = db.fetch_one('SELECT current_pitcher, pitch_submitted, swing_requested, swing_submitted FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
        player_id = robo_ump.get_player_from_discord(ctx.author.id)
        if robo_ump.player_is_allowed(ctx.author.id, team) or (ctx.guild is None and player_id == current_pitcher):
            if not swing_submitted:
                robo_ump.log_msg(f'{ctx.author.name} set Infield In for {league} {season}.{session}.{game_id}')
                event = robo_ump.set_event(sheet_id, 'Infield In')
                await ctx.send(f'Event set to {event}')
                if pitch_submitted and swing_requested:
                    await robo_ump.post_at_bat(self.bot, league, season, session, game_id)
            else:
                await ctx.send("Swing already submitted, can't call infield in now.")

    @commands.command(brief='Reset infield in back to normal',
                      description='Set the infield out for the current at bat. Re-posts the at bat ping if one has already been posted.',
                      aliases=['ifout', 'infieldout', 'if_out'])
    async def infield_out(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        current_pitcher, pitch_submitted, swing_requested, swing_submitted = db.fetch_one('SELECT current_pitcher, pitch_submitted, swing_requested, swing_submitted FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
        player_id = robo_ump.get_player_from_discord(ctx.author.id)
        if robo_ump.player_is_allowed(ctx.author.id, team) or (ctx.guild is None and player_id == current_pitcher):
            if not swing_submitted:
                robo_ump.log_msg(f'{ctx.author.name} set Infield Out for {league} {season}.{session}.{game_id}')
                event = robo_ump.set_event(sheet_id, 'Swing')
                await ctx.send(f'Event set to {event}')
                if pitch_submitted and swing_requested:
                    await robo_ump.post_at_bat(self.bot, league, season, session, game_id)
            else:
                await ctx.send("Swing already submitted, can't change infield position now.")

    @commands.command(brief='Pause the game from advancing',
                      description='Allows GMs to pause the game from automatically resulting, prompting for a pitch, or posting an AB on reddit.',
                      aliases=['pause'])
    async def pause_game(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team) or discord.utils.get(ctx.guild.roles, id=ump_warden_role) in ctx.author.roles:
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            robo_ump.log_msg(f'{ctx.author.name} paused game {league} {season}.{session}.{game_id}')
            robo_ump.set_state(league, season, session, game_id, 'PAUSED')
            await ctx.message.add_reaction('👍')

    @commands.command(brief='Request umps issue an Auto BB',
                      description='Sends a request to #umpires with the current game state to evaluate if an Auto BB should be applied, or to use a conditional sub, if applicable.',
                      aliases=['auto_bb', 'autobb', 'use_conditional_pitch'])
    async def request_auto_bb(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team) or discord.utils.get(ctx.guild.roles, id=umpire_role) in ctx.author.roles:
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            game = robo_ump.fetch_game_team(team, season, session)
            thread_url, sheet_id, state = db.fetch_one('SELECT threadURL, sheetID, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
            if state.upper() not in ['WAITING FOR PITCH']:
                await ctx.send(f'Game is currently {state.lower()}. Please wait.')
                return
            sql = '''SELECT current_pitcher, pitch_requested, pitch_submitted, pitch_src, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, pitch_requested, pitch_submitted, pitch_src, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes = db.fetch_one(sql, game)
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            pitcher_name = robo_ump.get_player_name(current_pitcher)

            if pitch_src:
                pitch_submitted = f'<t:{pitch_submitted}:T>'
            else:
                pitch_submitted = '-'

            if conditional_pitch_src:
                conditional_pitcher_name, conditional_pitcher_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (conditional_pitcher,))
                conditional_pitcher_discord = self.bot.get_user(int(conditional_pitcher_discord))
                conditional_pitcher_dm_channel = await conditional_pitcher_discord.create_dm()
                conditional_pitch_src = await conditional_pitcher_dm_channel.fetch_message(int(conditional_pitch_src))
                conditional_pitch_requested = f'<t:{conditional_pitch_requested}:T>'
                conditional_pitch_submitted = f'<t:{robo_ump.convert_to_unix_time(conditional_pitch_src.created_at)}:T>'
            else:
                conditional_pitcher = '-'
                conditional_pitcher_name = '-'
                conditional_pitch_requested = '-'
                conditional_pitch_submitted = '-'

            embed = discord.Embed(title='Auto BB Request',
                                  description=f'{ctx.author.mention} has requested an auto BB. Please investigate.',
                                  color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='Pitcher', value=pitcher_name, inline=False)
            embed.add_field(name='Pitcher ID', value=current_pitcher)
            embed.add_field(name='Pitch Requested', value=f'<t:{pitch_requested}:T>')
            embed.add_field(name='Pitch Submitted', value=pitch_submitted)
            embed.add_field(name='Conditional Pitcher', value=conditional_pitcher_name, inline=False)
            embed.add_field(name='Conditional Pitcher ID', value=conditional_pitcher)
            embed.add_field(name='Conditional Pitch Requested', value=conditional_pitch_requested)
            embed.add_field(name='Conditional Pitch Submitted', value=conditional_pitch_submitted)
            embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})')
            embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
            await ctx.send(embed=embed, view=standard_buttons(self.ump_hq, embed, self.bot, league, season, session, game_id))

    @commands.command(brief='Request umps issue an Auto K',
                      description='Sends a request to #umpires with the current game state to evaluate if an Auto K should be applied, or to use a conditional sub, if applicable.',
                      aliases=['auto_k', 'autok', 'use_conditional_swing'])
    async def request_auto_k(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team) or discord.utils.get(ctx.guild.roles, id=umpire_role) in ctx.author.roles:
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            game = robo_ump.fetch_game_team(team, season, session)
            thread_url, sheet_id, state = db.fetch_one('SELECT threadURL, sheetID, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
            if state.upper() not in ['WAITING FOR SWING']:
                await ctx.send(f'Game is currently {state.lower()}. Please wait.')
                return
            sql = '''SELECT swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes = db.fetch_one(sql, game)
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            if conditional_swing_src:
                conditional_batter_name, conditional_batter_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (conditional_batter,))
                conditional_batter_discord = self.bot.get_user(int(conditional_batter_discord))
                conditional_batter_dm_channel = await conditional_batter_discord.create_dm()
                conditional_swing_src = await conditional_batter_dm_channel.fetch_message(int(conditional_swing_src))
                conditional_swing_requested = f'<t:{conditional_swing_requested}:T>'
                conditional_swing_submitted = f'<t:{robo_ump.convert_to_unix_time(conditional_swing_src.created_at)}:T>'
            else:
                conditional_batter = '-'
                conditional_batter_name = '-'
                conditional_swing_notes = '-'
                conditional_swing_requested = '-'
                conditional_swing_submitted = '-'

            embed = discord.Embed(title='Auto K Request', description=f'{ctx.author.mention} has requested an auto K. Please investigate.', color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='Conditional Batter', value=conditional_batter_name, inline=True)
            embed.add_field(name='Conditional Batter ID', value=conditional_batter, inline=True)
            embed.add_field(name='Condition', value=conditional_swing_notes, inline=True)
            embed.add_field(name='Conditional Time Requested', value=conditional_swing_requested, inline=True)
            embed.add_field(name='ConditionalTime Submitted', value=conditional_swing_submitted, inline=True)
            embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
            embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})', inline=True)
            await ctx.send(embed=embed, view=standard_buttons(self.ump_hq, embed, self.bot, league, season, session, game_id))

    @commands.command(brief='Request a position change',
                      description='Sends a request to #umpires to update the Subs tab on the game sheet with the specified change. Multiple requests can be submitted using one command. There is no ability to undo, simply cancel and start over upon making a mistake.',
                      aliases=['position_change', 'pos_change', 'poschange', 'positionchange'])
    async def request_position_change(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            game = robo_ump.fetch_game_team(team, season, session)
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            thread_url, sheet_id, home_team, away_team, state = db.fetch_one('SELECT threadURL, sheetID, homeTeam, awayTeam, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
            if state.upper() in ['WAITING FOR UMP CONFIRMATION', 'WAITING FOR PITCHER CONFIRMATION']:
                await ctx.send(f'Game is currently {state.lower()}. Please wait until the current request is resolved before making any further requests.')
                return
            if team.upper() == home_team:
                sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['home_sub_list'])
            elif team.upper() == away_team:
                sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['away_sub_list'])
            else:
                await ctx.message.add_reaction('⁉')
                return
            sub_list_dropdown = []
            positions_select = []
            for sub in sub_list:
                sub_list_dropdown.append(discord.SelectOption(label=sub[0]))
            for pos in assets.valid_positions:
                positions_select.append(discord.SelectOption(label=pos))
            player_select = Select(placeholder='Player', options=sub_list_dropdown)
            old_pos_select = Select(placeholder='Old Position', options=positions_select)
            new_pos_select = Select(placeholder='New Position', options=positions_select)
            confirm = Button(label="Submit Request", style=discord.ButtonStyle.green)
            cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

            async def player_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='Player', value=player_select.values[0])
                await prompt.edit(embed=embed)

            async def old_position_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='Old Position', value=old_pos_select.values[0])
                await prompt.edit(embed=embed)

            async def new_position_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='New Position', value=new_pos_select.values[0])
                await prompt.edit(embed=embed)

            async def send_request(interaction):
                await interaction.response.defer()
                await self.ump_hq.send(embed=embed, view=robo_ump.umpdate_buttons(self.bot, sheet_id, embed, league, season, session, game_id, team))
                robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
                await prompt.edit(content=None, view=None, embed=embed)
                await interaction.followup.send('Request sent.')

            async def cancel_request(interaction: discord.Interaction):
                await interaction.response.defer()
                await prompt.edit(content='Request cancelled.', view=None, embed=None)
                return

            player_select.callback = player_callback
            old_pos_select.callback = old_position_callback
            new_pos_select.callback = new_position_callback
            confirm.callback = send_request
            cancel.callback = cancel_request

            view = View(timeout=None)
            view.add_item(player_select)
            view.add_item(old_pos_select)
            view.add_item(new_pos_select)
            view.add_item(confirm)
            view.add_item(cancel)

            embed = discord.Embed(title='Position Change Request', description=f'{ctx.author.mention} has requested the following position change.\n\nPlease update the **Subs** tab on the Ump Helper sheet.', color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='State', value=state, inline=False)
            prompt = await ctx.send(content='Use the drop down menus to select the relevant player, their current position, and their new position. You can submit multiple position changes in one request. If you mess up, hit cancel and start over. When you hit submit, a request will be sent to #umpires in main for the sub to be processed.', view=view, embed=embed)
            return None

    @commands.command(brief='Request a player substitution',
                      description='Sends a request to #umpires to update the Subs tab on the game sheet with the specified change. Multiple requests can be submitted using one command. There is no ability to undo, simply cancel and start over upon making a mistake.',
                      aliases=['requestsub', 'sub'])
    async def request_sub(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            if not season and not session:
                season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            game = robo_ump.fetch_game_team(team, season, session)
            logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
            thread_url, sheet_id, home_team, away_team, state = db.fetch_one('SELECT threadURL, sheetID, homeTeam, awayTeam, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
            if state.upper() in ['WAITING FOR UMP CONFIRMATION', 'WAITING FOR PITCHER CONFIRMATION']:
                await ctx.send(f'Game is currently {state.lower()}. Please wait until the current request is resolved before making any further requests.')
                return
            if team.upper() == home_team:
                sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['home_sub_list'])
            elif team.upper() == away_team:
                sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['away_sub_list'])
            else:
                await ctx.message.add_reaction('⁉')
                return
            sub_list_dropdown = []
            positions_select = []
            for sub in sub_list:
                sub_list_dropdown.append(discord.SelectOption(label=sub[0]))
            for pos in assets.valid_positions:
                positions_select.append(discord.SelectOption(label=pos))
            player_out_select = Select(placeholder='Player Out', options=sub_list_dropdown)
            player_in_select = Select(placeholder='Player In', options=sub_list_dropdown)
            positions_select = Select(placeholder='Position', options=positions_select)
            confirm = Button(label="Submit Request", style=discord.ButtonStyle.green)
            cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

            async def player_out_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='Player Out', value=player_out_select.values[0])
                await prompt.edit(embed=embed)

            async def player_in_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='Player In', value=player_in_select.values[0])
                await prompt.edit(embed=embed)

            async def position_callback(interaction):
                await interaction.response.defer()
                embed.add_field(name='Position', value=positions_select.values[0])
                await prompt.edit(embed=embed)

            async def send_request(interaction):
                await interaction.response.defer()
                current_batter, current_pitcher = db.fetch_one('SELECT current_batter, current_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
                ask_pitcher = False
                new_pitcher = False
                for field in embed.fields:
                    if field.name == 'Player Out':
                        player_id = robo_ump.get_player_id(field.value)
                        if current_batter == player_id:
                            ask_pitcher = True
                        if current_pitcher == player_id:
                            new_pitcher = True
                if ask_pitcher:
                    embed.add_field(name='Requires Pitcher Confirmation', value=True)
                if new_pitcher:
                    embed.add_field(name='Clear Current Pitch', value=True)
                await self.ump_hq.send(embed=embed, view=robo_ump.umpdate_buttons(self.bot, sheet_id, embed, league, season, session, game_id, team))
                robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
                await prompt.edit(content='Request sent.', view=None, embed=embed)

            async def cancel_request(interaction):
                await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
                return

            player_out_select.callback = player_out_callback
            player_in_select.callback = player_in_callback
            positions_select.callback = position_callback
            confirm.callback = send_request
            cancel.callback = cancel_request

            view = View(timeout=None)
            view.add_item(player_out_select)
            view.add_item(player_in_select)
            view.add_item(positions_select)
            view.add_item(confirm)
            view.add_item(cancel)

            embed = discord.Embed(title='Substitution Request', description=f'{ctx.author.mention} has requested the following substitution.\n\nPlease update the **Subs** tab on the Ump Helper sheet.', color=discord.Color(value=int(color, 16)))
            embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
            embed.add_field(name='State', value=state, inline=False)
            prompt = await ctx.send(content='Use the drop down menus to select the player you want subbed out, the player you want subbed in, and their new position. You can submit multiple substitutions in one request. If you mess up, hit cancel and start over. When you hit submit, a request will be sent to #umpires in main for the sub to be processed.', view=view, embed=embed)

    @commands.command(brief='Reset the current at-bat',
                      description='Resets the current at bat from scratch. The pitcher will be prompted for a new pitch, the batters previous swing will be ignored, and any results are invalid.',
                      aliases=['reset'])
    @commands.has_role(umpire_role)
    async def reset_ab(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        before_swing = sheets.read_sheet(sheet_id, assets.calc_cell2['before_swing'])[0]
        inning, outs, obc, home_score, away_score = before_swing
        db.update_database('UPDATE pitchData SET current_batter=%s, current_pitcher=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (None, None, league, season, session, game_id))
        db.update_database('UPDATE gameData SET inning=%s, outs=%s, obc=%s, homeScore=%s, awayScore=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (inning, outs, obc, home_score, away_score, league, season, session, game_id))
        robo_ump.log_msg(f'{ctx.author.name} reset the current at bat for {league.upper()} {season}.{session}.{game_id}')
        robo_ump.set_state(league, season, session, game_id, 'WAITING FOR PITCH')
        await ctx.send('The at bat has been reset.')
        return

    @commands.command(brief='Reset all conditional subs for the game',
                      description='Resets all conditional subs for a game in case they get stuck for whatever reason',)
    @commands.has_role(umpire_role)
    async def reset_conditionals(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        db.update_database('UPDATE pitchData SET conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s, conditional_pitch_notes = %s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s, conditional_swing_notes = %s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (None, None, None, None, None, None, None, None, league, season, session, game_id))
        robo_ump.log_msg(f'{ctx.author.name} reset all conditional subs for {league.upper()} {season}.{session}.{game_id}')
        await ctx.send(f'All conditional subs for {league.upper()} {season}.{session}.{game_id} have been reset.')
        return

    @commands.command(brief='Roll back the last play',
                      description='Removes the previous play from the game log and the PALogs table in the database, and sets the game state back to the start of the previous at-bat.')
    @commands.has_role(umpire_role)
    async def rollback(self, ctx, team: str, season: int = None, session: int = None):
        if not season and not session:
            season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        rows = sheets.read_sheet(sheet_id, assets.calc_cell2['game_log'])
        last_play = rows[-1]

        batter_name = last_play[0]
        swing = last_play[1]
        pitcher_name = last_play[2]
        pitch = last_play[3]
        play_type = last_play[4]
        diff = last_play[5]
        result_type = last_play[6]

        at_bat = f'{batter_name} batting against {pitcher_name}\n\n'
        at_bat += f'Play: {play_type}\nSwing: {swing}\nPitch: {pitch}\nDiff: {diff} -> {result_type}'

        confirm = Button(label="Rollback Play", style=discord.ButtonStyle.red)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.grey)

        async def send_request(interaction):
            await interaction.response.defer()
            play_number = last_play[57]
            pa_id = robo_ump.get_pa_id(league, season, session, game_id, play_number)

            # Clear entry from sheet
            sheets.update_sheet(sheet_id, f'NewGL!G{len(rows)}', '', lazy=True)
            sheets.update_sheet(sheet_id, f'NewGL!H{len(rows)}', '', lazy=True)
            sheets.update_sheet(sheet_id, f'NewGL!I{len(rows)}', '', lazy=True)
            sheets.update_sheet(sheet_id, f'NewGL!J{len(rows)}', '', lazy=True)
            sheets.update_sheet(sheet_id, f'NewGL!K{len(rows)}', '', lazy=True)

            # Remove row from database
            robo_ump.remove_from_pa_log(pa_id)

            # Clear current pitch/swing data
            sql = '''UPDATE pitchData SET current_pitcher=%s, current_batter=%s, pitch_requested=%s, pitch_submitted=%s, pitch_src=%s, steal_src=%s, swing_requested=%s, swing_submitted=%s, swing_src=%s, conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s, conditional_pitch_notes=%s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            db.update_database(sql, (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, league, season, session, game_id))

            # Update gameData with new state
            before_swing, = sheets.read_sheet(sheet_id, assets.calc_cell2['before_swing'])
            inning, outs, obc, home_score, away_score = before_swing
            sql = '''UPDATE gameData SET awayScore=%s, homeScore=%s, inning=%s, outs=%s, obc=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
            db.update_database(sql, (away_score, home_score, inning, outs, obc, league, season, session, game_id))

            robo_ump.log_msg(f'{ctx.author} rolled back play {pa_id} for {league.upper()} {season}.{session}.{game_id}')
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR PITCH')
            await message.edit(content=f'**Play successfully rolled back.**\n```{at_bat}```', view=None)
            return

        async def cancel_request(interaction):
            await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
            return

        confirm.callback = send_request
        cancel.callback = cancel_request
        view = View(timeout=None)
        view.add_item(confirm)
        view.add_item(cancel)
        message = await ctx.send(f'**Clear last play?**\n```{at_bat}```', view=view)

    @commands.command(brief='Set lineups to start the game',
                      description='GMs can input their lineup directly to the ump helper sheet. When both lineups have been submitted, the game automatically prompts the pitcher for their first pitch. ',
                      aliases=['set_lineups', 'setlineups', 'setlineup', 'lineup', 'lineups'])
    async def set_lineup(self, ctx, team: str, season: int = None, session: int = None):
        if robo_ump.player_is_allowed(ctx.author.id, team):
            season, session = robo_ump.get_current_session(team)
            league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
            sql = 'SELECT sheetID, threadURL, awayTeam, homeTeam FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'
            sheet_id, thread_url, away_team, home_team = db.fetch_one(sql, (league, season, session, game_id))

            done = Button(label="Done", style=discord.ButtonStyle.green)
            cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

            async def done_lineup(interaction):
                await interaction.response.defer()
                if robo_ump.lineup_check(sheet_id):
                    matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
                    # Write lineup to lineups table
                    await robo_ump.starting_lineup(league, season, session, game_id)
                    if matchup_info:
                        matchup_info = matchup_info[0]
                        await interaction.message.edit(view=None)
                    else:
                        return None
                    starting_pitchers = sheets.read_sheet(sheet_id, assets.calc_cell2['starting_pitchers'])[0]
                    away_sp = robo_ump.get_player_id(starting_pitchers[0])
                    home_sp = robo_ump.get_player_id(starting_pitchers[3])
                    db.update_database('UPDATE pitchData SET home_pitcher=%s, away_pitcher=%s, current_batter=%s, current_pitcher=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (home_sp, away_sp, matchup_info[0], matchup_info[3], league, season, session, game_id))
                    await reddit.edit_thread(thread_url, robo_ump.get_box_score(sheet_id))
                    away_role_id, = db.fetch_one('SELECT role_id FROM teamData WHERE abb=%s', (away_team,))
                    home_role_id, = db.fetch_one('SELECT role_id FROM teamData WHERE abb=%s', (home_team,))
                    hype_ping = f'<@&{away_role_id}> <@&{home_role_id}> your game thread has been created! {thread_url}'
                    channel = int(robo_ump.read_config('league.ini', league.upper(), 'game_discussion'))
                    channel = self.bot.get_channel(channel)
                    await channel.send(hype_ping)
                    robo_ump.set_state(league, season, session, game_id, 'WAITING FOR PITCH')
                else:
                    await ctx.send('Still waiting for lineups.')
                    await interaction.message.edit(view=None)
                return

            async def cancel_request(interaction):
                await interaction.response.edit_message(content='Request cancelled.', view=None)
                return

            cancel.callback = cancel_request
            done.callback = done_lineup
            view = View(timeout=None)
            view.add_item(done)
            view.add_item(cancel)

            await ctx.send(content=f'Here\'s your game sheet, please update the **Starting Lineups** tab.\nhttps://docs.google.com/spreadsheets/d/{sheet_id}', view=view)

    @commands.command(brief='Manually set pitch message ID',
                      description='Manual override for pitch message ID',
                      aliases=['setpitch'])
    @commands.has_role(ump_helper_role)
    async def set_pitch(self, ctx, team: str, url: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        url = url.split('/')
        message_id = url[-1]
        sql = '''UPDATE pitchData SET pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (message_id, league, season, session, game_id))
        robo_ump.log_msg(f'{league.upper()} {season}.{session}.{game_id} {ctx.author.name} manually set pitch_src to {message_id}')
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Manually set swing message ID',
                      description='Manual override for swing message ID',
                      aliases=['setswing'])
    @commands.has_role(ump_helper_role)
    async def set_swing(self, ctx, team: str, url: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        url = url.split('/')
        message_id = url[-1]
        sql = '''UPDATE pitchData SET swing_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (message_id, league, season, session, game_id))
        robo_ump.log_msg(f'{league.upper()} {season}.{session}.{game_id} {ctx.author.name} manually set swing_src to {message_id}')
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Override game state',
                      description='Manual override to update the state of a game.',
                      aliases=['setstate'])
    @commands.has_role(umpire_role)
    async def set_state(self, ctx, team: str, *, state: str):
        if state.upper() not in assets.states:
            await ctx.send(f'Invalid state. Valid states are: `{assets.states}`')
            return
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        robo_ump.set_state(league, season, session, game_id, state.upper())
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Override game state',
                      description='Manual override to update the state of a game.',
                      aliases=['setstate2'])
    @commands.has_role(umpire_role)
    async def set_state2(self, ctx, team: str, season: int, session: int, state: str):
        if state.upper() not in assets.states:
            await ctx.send(f'Invalid state. Valid states are: `{assets.states}`')
            return
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        robo_ump.set_state(league, season, session, game_id, state.upper())
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Setup all games for the current session',
                      description='Create games in the database and post the game thread on reddit',
                      aliases=['setup', 'setupgames'])
    @commands.has_role(ump_warden_role)
    async def setup_games(self, ctx, session: int):
        await ctx.send(f'Setting up games for session {session}...')
        await robo_ump.create_ump_sheets(self.bot, session)
        await ctx.send('Done.')

    @commands.command(brief='Get ump helper sheet',
                      description='Gets a link to the ump helper sheet')
    @commands.has_role(umpire_role)
    async def sheet(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sql = 'SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'
        sheet_id = db.fetch_one(sql, (league, season, session, game_id))
        if sheet_id:
            await ctx.send(f'https://docs.google.com/spreadsheets/d/{sheet_id[0]}')

    @commands.command(brief='Submit a conditional pitch if a sub is still pending',
                      description='If the bot is restarted while a pending conditional sub was awaiting a reply, it will prompt the pitcher to submit their pitch using this command.',
                      aliases=['submit_cond_pitch', 'submitconditionalpitch'])
    async def submit_conditional_pitch(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_conditional_pitch(ctx, self.bot)
        league, season, session, game_id = game
        dm_channel = await ctx.author.create_dm()
        robo_ump.log_msg(f'{league} {season}.{season}.{game_id} Player ID:{robo_ump.get_player_from_discord(ctx.author.id)}:DiscordID:{ctx.author.id}:ChannelID:{ctx.channel.id}:MessageID:{ctx.message.id}:DM Channel:{ctx.author.dm_channel.id}:DM Channel:{dm_channel.id}:SCP')
        data = (ctx.message.id,) + game
        db.update_database('''UPDATE pitchData SET conditional_pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='Submit a conditional swing if a sub is still pending',
                      description='If the bot is restarted while a pending conditional sub was awaiting a reply, it will prompt the batter to submit their swing using this command.',
                      aliases=['submit_cond_swing', 'submitconditionalswing'])
    async def submit_conditional_swing(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_conditional_swing(ctx, self.bot)
        league, season, session, game_id = game
        dm_channel = await ctx.author.create_dm()
        robo_ump.log_msg(f'{league} {season}.{season}.{game_id} Player ID:{robo_ump.get_player_from_discord(ctx.author.id)}:DiscordID:{ctx.author.id}:ChannelID:{ctx.channel.id}:MessageID:{ctx.message.id}:DM Channel:{ctx.author.dm_channel.id}:DM Channel:{dm_channel.id}:SCS')
        data = (ctx.message.id, robo_ump.convert_to_unix_time(ctx.message.created_at)) + game
        db.update_database('''UPDATE pitchData SET conditional_swing_src=%s, conditional_swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        await ctx.message.add_reaction('👍')


async def setup(bot):
    await bot.add_cog(Game(bot))


def standard_buttons(channel, embed, bot, league, season, session, game_id):
    confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
    cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

    async def send_request(interaction):
        await interaction.response.defer()
        robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        if 'Auto' in embed.title:
            await channel.send(embed=embed, view=robo_ump.auto_buttons(bot, embed, league, season, session, game_id))
        else:
            await channel.send(embed=embed)
        await interaction.message.edit(content='Request sent.', view=None, embed=None)

    async def cancel_request(interaction):
        await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
        return

    confirm.callback = send_request
    cancel.callback = cancel_request
    view = View(timeout=None)
    view.add_item(confirm)
    view.add_item(cancel)
    return view
