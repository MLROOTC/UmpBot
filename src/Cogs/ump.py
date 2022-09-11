import configparser
import discord
import datetime
import src.reddit_interface as reddit
from discord.ext import commands
import src.db_controller as db
import src.sheets_reader as sheets
import src.assets as assets
from dhooks import Webhook

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')
ump_role = int(config_ini['Discord']['ump_role'])
league_config = 'league.ini'
bot_config = 'config.ini'
loading_emote = '<a:baseball:872894282032365618>'


class Ump(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ab_ping_channel = int(config_ini['Channels']['ab_bat_pings_channel'])
        self.fcb_ab_ping_channel = int(config_ini['Channels']['fcb_ab_bat_pings_channel'])
        self.subreddit_name = config_ini['Reddit']['subreddit_name']
        self.master_ump_sheet = config_ini['Database']['master_ump_sheet']
        self.main_guild_id = config_ini['Discord']['main_guild_id']
        self.timeout = float(config_ini['Discord']['timeout']) * 60
        self.bot_admin_channel = int(config_ini['Discord']['bot_admin_channel'])
        self.ump_admin_role = int(config_ini['Discord']['ump_admin_role'])

    @commands.command(brief='Updates the boxscore in the reddit thread.',
                      description='Refreshes the box score in the post body of the reddit thread. Note that this '
                                  'already happens automatically after resulting an at bat.')
    @commands.has_role(ump_role)
    async def boxscore(self, ctx):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            thread = config[8]
            data = sheets.read_sheet(sheet_id, assets.calc_cell['boxscore'])
            boxscore_raw = raw_text(data)
            boxscore_raw += '\n---\nLast Updated at %s' % datetime.datetime.now()
            updated = await reddit.edit_thread(thread, boxscore_raw)
            if updated:
                await ctx.send('Box score updated.')
            else:
                await ctx.send('I was not able to update the box score for you.')

    @commands.command(brief='Delete a comment posted by the bot',
                      description='Deletes a reddit comment that was posted by the bot. Accepts a URL to a comment posted on reddit as an argument.')
    @commands.has_role(ump_role)
    async def delete_comment(self, ctx, comment_url):
        comment = await reddit.get_comment(comment_url)
        delete_prompt = await ctx.send('Delete the following comment?\n```%s```Tap the :baseball: to delete or :thumbsdown: to cancel.' % comment.body)
        await delete_prompt.add_reaction('\N{baseball}')
        await delete_prompt.add_reaction('👎')

        def check(result_reaction, ump_user):
            return result_reaction.message.id == delete_prompt.id and ump_user == ctx.message.author and str(
                result_reaction.emoji) in ['👎', '\N{baseball}']

        reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
        if reaction.emoji == '\N{baseball}':
            comment_deleted = await reddit.delete_comment('https://www.reddit.com%s' % comment.permalink)
            if comment_deleted:
                await delete_prompt.add_reaction('🆗')
            else:
                await delete_prompt.add_reaction('❗')
        elif reaction.emoji == '👎':
            await delete_prompt.add_reaction('🆗')

    @commands.command(brief='Delete a game thread posted by the bot',
                      description='Deletes a reddit thread that was posted by the bot. Accepts a URL to a comment posted on reddit as an argument, and is sent for approval before deleting.')
    @commands.has_role(ump_role)
    async def delete_thread(self, ctx, thread_url):
        thread = await reddit.get_thread_url(thread_url)
        delete_prompt = await ctx.send('Delete the following thread?\n```%s```Tap the :baseball: to delete or :thumbsdown: to cancel.' % thread.title)
        await delete_prompt.add_reaction('\N{baseball}')
        await delete_prompt.add_reaction('❌')

        def check(result_reaction, ump_user):
            return result_reaction.message.id == delete_prompt.id and ump_user == ctx.message.author and str(
                result_reaction.emoji) in ['❌', '\N{baseball}']

        reaction, user = await self.bot.wait_for('reaction_add', timeout=None, check=check)
        if reaction.emoji == '\N{baseball}':
            channel = self.bot.get_channel(self.bot_admin_channel)
            approval_msg = await channel.send(content='<@%s> wants to delete the following game thread:\n%s' % (ctx.author.id, thread_url))
            await approval_msg.add_reaction('✅')
            await approval_msg.add_reaction('❌')

            admin_role = discord.utils.get(ctx.guild.roles, id=self.ump_admin_role)

            def approval(approval_reaction, admin_user):
                return approval_reaction.message.id == approval_msg.id and admin_role in admin_user.roles and str(approval_reaction.emoji) in ['✅', '❌']

            admin_react, admin_react_user = await self.bot.wait_for('reaction_add', timeout=None, check=approval)
            if admin_react.emoji == '✅':
                thread_deleted = await reddit.delete_thread(thread_url)
                if thread_deleted:
                    await delete_prompt.add_reaction('🆗')
                else:
                    await delete_prompt.add_reaction('❗')
            elif admin_react.emoji == '❌':
                await delete_prompt.add_reaction('👎')
        elif reaction.emoji == '❌':
            await delete_prompt.add_reaction('🆗')

    @commands.command(brief='Set the event type for the current at bat (swing, steal, etc.)',
                      description='Sets the event type in the calculator for the current at bat. Setting the event type'
                                  ' to Auto K, Auto BB, or IBB will also reset the swing and pitch in the calculator. '
                                  '\n\n**Please note that the arguments are case sensitive.**\n\nValid Arguments:\n\n\t'
                                  '[Swing, Auto K, Auto BB, Bunt, Steal 2B, Steal 3B, Steal Home, Infield In, IBB]')
    @commands.has_role(ump_role)
    async def event(self, ctx, *, event_type):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            valid_events = ['swing', 'auto k', 'auto bb', 'bunt', 'steal 2b', 'steal 3b', 'steal home', 'infield in',
                            'ibb']
            if event_type.lower() not in valid_events:
                await ctx.send('%s is not a valid event type. Please use: %s' % (event_type, valid_events))
            else:
                if event_type.lower() in ['auto k', 'auto bb', 'ibb']:
                    await reset(ctx, sheet_id)
                check_event = sheets.update_sheet(sheet_id, assets.calc_cell['event'], event_type)
                if check_event:
                    await ctx.send('Event set to %s.' % event_type)
                else:
                    await ctx.send('Something went wrong. Please reset or check the sheet manually.')

    @commands.command(brief='Sets game complete to true',
                      description='Sets the game state to completed. Note, does not set awards, that must be done '
                                  'manually through the sheet.')
    @commands.has_role(ump_role)
    async def finalize(self, ctx):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            thread = config[8]
            check_complete = sheets.update_sheet(sheet_id, assets.calc_cell['game_complete'], 'TRUE')
            if not check_complete:
                await ctx.send('Something went wrong. Please check the sheet.')
                return
            finalize_msg = await ctx.send('Please set awards on the calculator tab of the ump helper sheet\nhttps://docs.google.com/spreadsheets/d/%s/edit#gid=1602349494\nReact to the message with \N{baseball} when complete or ❌ to cancel.' % sheet_id)
            await finalize_msg.add_reaction('\N{baseball}')
            await finalize_msg.add_reaction('❌')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == finalize_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['\N{baseball}', '❌']

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                awards_list = sheets.read_sheet(sheet_id, assets.calc_cell['awards'])[0]
                if len(awards_list) != 8:
                    await ctx.send("Awards not set properly. Please retry.")
                    return
                winning_pitcher = awards_list[1]
                losing_pitcher = awards_list[3]
                save = awards_list[5]
                player_of_game = awards_list[7]
                awards = '> **Winning Pitcher:** %s\n> **Losing Pitcher:** %s\n> **Save:** %s\n> **PotG:** %s' % (winning_pitcher, losing_pitcher, save, player_of_game)
                awards_msg = await ctx.send('%s \nIf the above looks good, react to this message with 👍 to update the game thread and close the game out.' % awards)
                await awards_msg.add_reaction('👍')
                await awards_msg.add_reaction('❌')

                def check(awards_react, ump_user):
                    return awards_react.message.id == awards_msg.id and ump_user == ctx.message.author and str(
                        awards_react.emoji) in ['👍', '❌']

                awards_reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
                if awards_reaction.emoji == '👍':
                    await awards_msg.edit(content='Closing out game, please wait...')
                    sql = '''SELECT league, season, session, gameID, awayTeam, homeTeam FROM gameData WHERE sheetID=%s'''
                    game_data = db.fetch_data(sql, (sheet_id,))
                    if game_data:
                        league, season, session, gameID, away_team, home_team = game_data[0]
                        if league != 'SCRIM':
                            game_log = sheets.read_sheet(sheet_id, assets.calc_cell['game_log'])
                            for i in range(len(game_log)):
                                pa = game_log[i]
                                if pa[0] != 'Before Swing' and pa[0] != 'IP Outs':
                                    if len(pa) > 6:
                                        if pa[6] != '':
                                            inning = pa[1]
                                            playNumber = i - 1
                                            outs = int(pa[2])
                                            obc = int(pa[3])
                                            awayScore = int(pa[5])
                                            homeScore = int(pa[4])
                                            pitcherName = pa[8]
                                            hitterName = pa[6]
                                            pitch = pa[9]
                                            swing = pa[7]
                                            diff = pa[11]
                                            exactResult = pa[88]
                                            resultAtNeutral = pa[89]
                                            resultAllNeutral = pa[90]
                                            rbi = int(pa[13])
                                            run = int(pa[14])
                                            pr3B = None
                                            pr2B = None
                                            pr1B = None
                                            prAB = None
                                            if len(pa) >= 98:
                                                pr3B = pa[97]
                                            if len(pa) >= 99:
                                                pr2B = pa[98]
                                            if len(pa) >= 100:
                                                pr1B = pa[99]
                                            if len(pa) >= 101:
                                                prAB = pa[100]
                                            inning_after = pa[16]
                                            obc_after = int(pa[18])
                                            outs_after = int(pa[17])
                                            away_score_after = int(pa[20])
                                            home_score_after = int(pa[19])
                                            pa_id = get_pa_id(league, season, session, gameID, playNumber)
                                            sql = '''SELECT * FROM PALogs WHERE paID=%s'''
                                            pa_in_db = db.fetch_data(sql, (pa_id,))
                                            pa_in_sheet = format_pa_log(league, season, session, gameID, inning, playNumber, outs, obc, awayScore, homeScore, away_team, home_team, pitcherName, hitterName, pitch, swing, diff, exactResult, exactResult, resultAtNeutral, resultAllNeutral, rbi, run, pr3B, pr2B, pr1B, prAB, inning_after, obc_after, outs_after, away_score_after, home_score_after)
                                            if not pa_in_db:
                                                sql = '''INSERT INTO PALogs VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                                                db.update_database(sql, pa_in_sheet)
                                            else:
                                                pa_in_db = pa_in_db[0]
                                                if pa_in_db != pa_in_sheet:
                                                    sql = '''UPDATE PALogs SET paID=%s, league=%s, season=%s, session=%s, gameID=%s, inning=%s, inningID=%s, playNumber=%s, outs=%s, obc=%s, awayScore=%s, homeScore=%s, pitcherTeam=%s, pitcherName=%s, pitcherID=%s, hitterTeam=%s, hitterName=%s, hitterID=%s, pitch=%s, swing=%s, diff=%s, exactResult=%s, oldResult=%s, resultAtNeutral=%s, resultAllNeutral=%s, rbi=%s, run=%s, batterWPA=%s, pitcherWPA=%s, pr3B=%s, pr2B=%s, pr1B=%s, prAB=%s WHERE paID=%s'''
                                                    db.update_database(sql, (pa_in_sheet + (pa_id,)))
                    starting_pitchers = sheets.read_sheet(sheet_id, assets.calc_cell['starting_pitchers'])
                    sql = '''SELECT playerID from playerData WHERE playerName LIKE %s'''
                    winning_pitcher_id = db.fetch_data(sql, ('%' + winning_pitcher + '%',))
                    losing_pitcher_id = db.fetch_data(sql, ('%' + losing_pitcher + '%',))
                    if save:
                        save_id = db.fetch_data(sql, ('%' + save + '%',))
                    else:
                        save_id = None
                    player_of_game_id = db.fetch_data(sql, ('%' + player_of_game + '%',))
                    if winning_pitcher_id:
                        winning_pitcher_id = winning_pitcher_id[0][0]
                    if losing_pitcher_id:
                        losing_pitcher_id = losing_pitcher_id[0][0]
                    if save_id:
                        save_id = save_id[0][0]
                    if player_of_game_id:
                        player_of_game_id = player_of_game_id[0][0]
                    if starting_pitchers:
                        away_pitcher_name = starting_pitchers[0][0]
                        home_pitcher_name = starting_pitchers[0][3]
                        away_starting_pitcher = db.fetch_data(sql, ('%' + away_pitcher_name + '%',))[0][0]
                        home_starting_pitcher = db.fetch_data(sql, ('%' + home_pitcher_name + '%',))[0][0]
                    else:
                        away_starting_pitcher = None
                        home_starting_pitcher = None

                    sql = '''UPDATE gameData SET complete=%s, winningPitcher=%s, losingPitcher=%s, save=%s, potg=%s WHERE sheetID=%s'''
                    update_game_log = (1, winning_pitcher_id, losing_pitcher_id, save_id, player_of_game_id, sheet_id)
                    db.update_database(sql, update_game_log)

                    sql = '''SELECT session, homeTeam, awayTeam FROM gameData WHERE sheetID=%s'''
                    session, home_team, away_team = db.fetch_data(sql, (sheet_id,))[0]
                    game_awards = (session, home_team, away_team, player_of_game_id, winning_pitcher_id, losing_pitcher_id, save_id, home_starting_pitcher, away_starting_pitcher)
                    sheets.append_sheet(read_config(bot_config, 'URLs', 'backend_sheet_id'),assets.calc_cell['game_awards_input'], game_awards)

                    away_team = sheets.read_sheet(sheet_id, assets.calc_cell['away_team'])
                    away_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = %s''', (away_team[0][0],))
                    away_score = sheets.read_sheet(sheet_id, assets.calc_cell['away_score'])

                    home_team = sheets.read_sheet(sheet_id, assets.calc_cell['home_team'])
                    home_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = %s''', (home_team[0][0],))
                    home_score = sheets.read_sheet(sheet_id, assets.calc_cell['home_score'])

                    if len(home_team) > 0 and len(home_score) > 0 and len(away_team) > 0 and len(away_score) > 0:
                        home_team = home_team[0][0]
                        home_score = int(home_score[0][0])
                        away_team = away_team[0][0]
                        away_score = int(away_score[0][0])
                        if home_score > away_score:
                            end_game_command = '-endgame %s %s %s' % (home_team, away_team, thread)
                        elif away_score > home_score:
                            end_game_command = '-endgame %s %s %s' % (away_team, home_team, thread)
                        else:
                            end_game_command = None
                    else:
                        end_game_command = None

                    sheets.update_sheet(sheet_id, assets.calc_cell['game_end'], str(datetime.datetime.now()), True)
                    current_situation = sheets.update_sheet(sheet_id, assets.calc_cell['current_situation'], 'FALSE')
                    next_up = sheets.update_sheet(sheet_id, assets.calc_cell['next_up'], 'FALSE')
                    due_up = sheets.update_sheet(sheet_id, assets.calc_cell['due_up'], 'FALSE')
                    if current_situation and next_up and due_up:
                        data = sheets.read_sheet(sheet_id, assets.calc_cell['boxscore'])
                        boxscore_raw = raw_text(data)
                        boxscore_raw += '\n---\nLast Updated at %s' % datetime.datetime.now()
                        updated = await reddit.edit_thread(thread, boxscore_raw)
                        if updated:
                            await ctx.send('Box score updated.')
                        else:
                            await ctx.send('I was not able to update the box score for you, please try again.')
                        sql = '''UPDATE umpData SET sheetID=%s WHERE sheetID = %s'''
                        db.update_database(sql, ('update', sheet_id))
                        sql = '''UPDATE umpData SET gameThread=%s WHERE gameThread = %s'''
                        db.update_database(sql, (None, thread))
                        sql = '''SELECT * FROM umpData WHERE discordID=%s'''
                        ump_data = db.fetch_data(sql, (ctx.author.id,))[0]
                        if ump_data[2] == 'update':
                            await ctx.send('Sheet ID reset.')
                        else:
                            await ctx.send('Failed to reset sheet ID.')
                        if ump_data[8] is None:
                            await ctx.send('Game thread URL reset.')
                        else:
                            await ctx.send('Failed to reset game thread URL.')
                        await ctx.send('Thanks for umping! Don\'t forget to do do -endgame in main!')
                        if end_game_command:
                            await ctx.send(end_game_command)
                        await ctx.send(awards)
                        return
                    else:
                        await ctx.send('Something went wrong finalizing the sheet, please try again.')
                        return
                elif awards_reaction.emoji == '❌':
                    return
            elif reaction.emoji == '❌':
                return

    @commands.command(brief='Posts the at bat ping on reddit and discord',
                      description='Posts the at bat ping on reddit and sends an alert to the at bat pings channel in '
                                  'main. Accepts flavor text for the at bat writeup as an optional parameter.')
    @commands.has_role(ump_role)
    async def ping(self, ctx, *, custom_text=None):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            thread = config[8]
            data = sheets.read_sheet(sheet_id, assets.calc_cell['reddit_ping'])
            ab_ping = raw_text(data)
            if custom_text:
                ab_ping += '\n%s' % custom_text
            ab_msg = await ctx.send('```%s```' % ab_ping)
            await ab_msg.add_reaction('\N{baseball}')
            await ab_msg.add_reaction('👎')
            await ab_msg.add_reaction('❌')
            await ctx.send('Tap the :baseball: if youd like me to post the AB for you, :thumbsdown: if you want to '
                           'post it yourself, or ❌ to cancel and redo the ping.')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == ab_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['👎', '\N{baseball}', '❌']

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                reddit_comment = await reddit.post_comment(thread, ab_ping)
                if reddit_comment:
                    await ab_msg.add_reaction('✅')
                else:
                    await ctx.send('Something went wrong.')
            elif reaction.emoji == '👎':
                await ab_msg.add_reaction('🆗')
            elif reaction.emoji == '❌':
                return

            batter_name = sheets.read_sheet(sheet_id, assets.calc_cell['batter_name'])
            league = db.fetch_data('SELECT league FROM gameData WHERE sheetID = %s', (sheet_id,))
            if league:
                league = league[0][0]
            main = self.bot.get_guild(int(self.main_guild_id))
            discord_ping = None
            if batter_name:
                batter_discord = db.fetch_data('''SELECT discordID, discordName FROM playerData WHERE playerName = %s''',
                                               (batter_name[0][0],))
                if not batter_discord:
                    data = sheets.read_sheet(sheet_id, assets.calc_cell['discord_ping'])
                    if 'NO PING NECESSARY' in data[1][0].upper():
                        await ctx.send('Discord not on file, no ping necessary.')
                        return
                    discord_name = sheets.read_sheet(sheet_id, assets.calc_cell['discord_name'])[0][0]
                    discord_name = discord_name[1:discord_name.index('#') + 5]
                    if league != 'FCB':
                        discord_user = main.get_member_named(discord_name)
                        if discord_user:
                            discord_ping = '%s' % discord_user.mention
                elif batter_discord[0][0]:
                    discord_ping = '<@%s>' % batter_discord[0][0]
                elif batter_discord[0][1]:
                    discord_user = main.get_member_named(batter_discord[0][1])
                    if discord_user:
                        discord_ping = '%s' % discord_user.mention
                    else:
                        discord_name = sheets.read_sheet(sheet_id, assets.calc_cell['discord_name'])[0][0]
                        if 'NO PING NECESSARY' in discord_name[1][0].upper():
                            await ctx.send('Discord not on file, no ping necessary.')
                            return
                        discord_name = discord_name[1:discord_name.index('#') + 5]
                        discord_user = main.get_member_named(discord_name)
                        if discord_user:
                            discord_ping = '%s' % discord_user.mention
                else:
                    await ctx.send('Discord not found. Please let GMs know the AB is posted.')
                    return
            ab_ping = raw_text(sheets.read_sheet(sheet_id, assets.calc_cell['discord_ping']))
            if discord_ping:
                league = db.fetch_data('SELECT league FROM gameData WHERE sheetID=%s', (sheet_id,))
                ab_ping += '%s is up to bat!' % discord_ping
                ab_ping += ' No need to ping your umps when you swing, we have bots for that.\n%s' % config[8]
                if league[0][0] == 'FCB':
                    await at_bat_ping(self.bot, ab_ping, self.fcb_ab_ping_channel)
                else:
                    await at_bat_ping(self.bot, ab_ping, self.ab_ping_channel)
                await ctx.send('Discord ping sent in main.')
            elif not discord_name:
                await ctx.send('Discord not on file, no ping necessary.')
            else:
                ab_ping += '@%s is up to bat!' % discord_name
                ab_ping += ' No need to ping your umps when you swing, we have bots for that.\n%s' % config[8]
                await ctx.send(
                    'Warning: a discord username is on file, but I couldn\'t find them in main. Their username may be out of date, or they may have left the server. Please post the AB ping manually and alert their GM.')
                await ctx.send(ab_ping)

    @commands.command(brief='Set pitch for current at bat',
                      description='Adds the pitch into the calculator. Does not process any results. Note, the sheet is'
                                  ' public. Do not use this command before the batter has swung.')
    @commands.has_role(ump_role)
    async def pitch(self, ctx, pitch):
        if not 0 < int(pitch) <= 1000:
            await ctx.send('Pitch must be between 1 and 1000')
            return
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            check_pitch = sheets.update_sheet(sheet_id, assets.calc_cell['pitch'], int(pitch))
            if check_pitch:
                await ctx.message.add_reaction('✅')
            else:
                await ctx.send('Something went wrong. Could not set pitch to %s' % pitch)

    @commands.command(brief='Post the reddit thread.',
                      description='Checks the lineup sheet to make sure both lineups are set, and then creates the game'
                                  ' thread on reddit.')
    @commands.has_role(ump_role)
    async def post_thread(self, ctx, *, custom_text=None):
        await ctx.message.add_reaction(loading_emote)
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            lineup_check = sheets.read_sheet(sheet_id, assets.calc_cell['lineup_check'])
            if lineup_check:
                lineup_check = lineup_check[0]
                if lineup_check[0] == 'That\'s a good lineup!' and lineup_check[3] == 'That\'s a good lineup!':
                    game_data = sheets.read_sheet(sheet_id, assets.calc_cell['game_data'])[0]
                    box_score = sheets.read_sheet(sheet_id, assets.calc_cell['boxscore'])
                    away_team = game_data[0]
                    home_team = game_data[3]
                    away_team = away_team.title()
                    home_team = home_team.title()
                    away_team = away_team.replace('\'S', '\'s')
                    home_team = home_team.replace('\'S', '\'s')
                    sql = '''SELECT league FROM gameData WHERE sheetID=%s'''
                    game_db = db.fetch_data(sql, (sheet_id,))
                    milr = game_data[5]
                    thread_title = ''
                    if game_db[0][0] == 'SCRIM':
                        thread_title += '[SCRIM'
                        league = 'SCRIM'
                    elif milr == 'TRUE':
                        thread_title += '[MiLR'
                        league = 'MILR'
                    elif milr == 'FALSE':
                        thread_title += '[MLR'
                        league = 'MLR'
                    else:
                        thread_title += '[FCB'
                        league = 'FCB'
                    season = read_config(league_config, league, 'season')
                    session = read_config(league_config, league, 'session')
                    thread_title += ' %s.%s Game Thread] %s at %s' % (season, session, away_team.title(), home_team.title())
                    if custom_text:
                        thread_title += ' - %s' % custom_text
                    sheets.rename_sheet(sheet_id, '%s %s.%s - %s @ %s' % (league, season, session, away_team, home_team))
                    body = raw_text(box_score)
                    thread = await reddit.post_thread(self.subreddit_name, thread_title, body)
                    await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
                    await ctx.message.add_reaction('✅')
                    await ctx.send(thread.url)
                    sql = '''UPDATE umpData SET gameThread=%s WHERE sheetID = %s'''
                    db.update_database(sql, (thread.url, sheet_id))
                    start_game_command = '-startgame'
                    if game_data[1]:
                        away_team = game_data[1]
                    else:
                        away_team = sheets.read_sheet(sheet_id, assets.calc_cell['away_team'])
                        away_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = %s''', (away_team[0][0],))[0][0]
                    if len(away_team) > 0:
                        start_game_command += ' %s' % away_team[0]

                    if game_data[4]:
                        home_team = game_data[4]
                    else:
                        home_team = sheets.read_sheet(sheet_id, assets.calc_cell['home_team'])
                        home_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = %s''', (home_team[0][0],))[0][0]
                    if len(home_team) > 0:
                        start_game_command += ' %s' % home_team[0]
                    start_game_command += ' %s' % thread.url
                    sql = '''UPDATE gameData SET threadURL=%s, awayTeam=%s, homeTeam=%s WHERE sheetID=%s'''
                    update_game_log = (thread.url, away_team, home_team, sheet_id)
                    db.update_database(sql, update_game_log)
                    if league != 'SCRIM':
                        sql = '''SELECT league, season, session, awayTeam, homeTeam, gameID, sheetID, threadURL, umpires FROM gameData WHERE sheetID=%s'''
                        if league != 'FCB':
                            sheet_export = db.fetch_data(sql, (sheet_id,))
                            if sheet_export:
                                sheets.append_sheet(read_config(bot_config, 'URLs', 'backend_sheet_id'), assets.calc_cell['game_data_import'], sheet_export[0])
                        await ctx.send('Game thread set. Play ball!')
                        if league != 'FCB':
                            await ctx.send(start_game_command)
                else:
                    await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
                    await ctx.message.add_reaction('⚠')
                    await ctx.send('Something went wrong. Please contact Dottie for help.')
            else:
                await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
                await ctx.message.add_reaction('⚠')
                await ctx.send('There appears to be an issue with your lineup. Please fix it before posting the game '
                               'thread.')

    @commands.command(brief='Resets the swing, pitch, and event type in the calculator',
                      description='Resets the pitch, swing, and event fields on the calculator tab in the sheet. Does '
                                  'not rollback anything that has previously been commited to the game log (use '
                                  '.rollback for that).')
    @commands.has_role(ump_role)
    async def reset(self, ctx):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            await reset(ctx, config[2])

    @commands.command(brief='Gets the result for the current at bat',
                      description='Accepts a pitch and swing as an optional argument.\n\nAcceptable inputs include:\n'
                                  '- .result pitch ### swing ###\n'
                                  '- .result swing ### pitch ###\n'
                                  '- .result p ### s ###\n'
                                  '- .result s ### p ###\n'
                                  '- .result\n'
                                  '\nPitch and swing can also be added using the .pitch and .swing commands, and then '
                                  'the .result command can be used without argumtns. If there is no pitch and swing '
                                  'configured for the required event types the command will fail. Once a result is '
                                  'calculated, the bot will display the bot and propmt for confirmation. When the '
                                  'result is confirmed, the game thread will be updated automatically with the box '
                                  'score and a webhook will be fired off if there is a URL configured for that team.',
                      aliases=['r'])
    @commands.has_role(ump_role)
    async def result(self, ctx, arg1=None, arg1_number=None, arg2=None, arg2_number=None):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            thread = config[8]
            if arg1 and not arg2:
                await ctx.send('Missing arguments')
                return
            if arg1 and arg2:
                if arg1.lower() == 'swing' or arg1.lower() == 's':
                    swing_number = arg1_number
                elif arg1.lower() == 'pitch' or arg1.lower() == 'p':
                    pitch_number = arg1_number
                else:
                    await ctx.send('Unrecognized command format. Please use .result swing ### pitch ###')
                if arg2.lower() == 'swing' or arg2.lower() == 's':
                    swing_number = arg2_number
                elif arg2.lower() == 'pitch' or arg2.lower() == 'p':
                    pitch_number = arg2_number
                else:
                    await ctx.send('Unrecognized command format. Please use .result swing ### pitch ###')
                    return
                if not 0 < int(pitch_number) <= 1000:
                    await ctx.send('Pitch must be between 1 and 1000')
                    return
                if not 0 < int(swing_number) <= 1000:
                    await ctx.send('Swing must be between 1 and 1000')
                    return
                if swing_number:
                    swing_check = sheets.update_sheet(sheet_id, assets.calc_cell['swing'], swing_number)
                    if swing_check:
                        await ctx.message.add_reaction('🦇')
                if pitch_number:
                    pitch_check = sheets.update_sheet(sheet_id, assets.calc_cell['pitch'], pitch_number)
                    if pitch_check:
                        await ctx.message.add_reaction('⚾')
            at_bat = sheets.read_sheet(sheet_id, assets.calc_cell['at_bat'])[0]
            numbers_required = ['Swing', 'Steal', 'Infield In', 'Bunt']
            if any(x in at_bat[4] for x in numbers_required) and (at_bat[1] == ' ' or at_bat[3] == ' '):
                await ctx.send('Can\'t process result, missing data: %s' % at_bat)
                return
            await ctx.send('Resulting at bat, please wait...')

            away_team_name = sheets.read_sheet(sheet_id, assets.calc_cell['away_team'])[0][0]
            home_team_name = sheets.read_sheet(sheet_id, assets.calc_cell['home_team'])[0][0]
            game_data = db.fetch_data('''SELECT league, awayTeam, homeTeam FROM gameData WHERE sheetID=%s''', (sheet_id,))
            away_team = db.fetch_data('''SELECT * FROM teamData WHERE name = %s''', (away_team_name,))
            if len(away_team) > 0:
                away_team = away_team[0]
            else:
                away_team = None
            home_team = db.fetch_data('''SELECT * FROM teamData WHERE name = %s''', (home_team_name,))
            if len(home_team) > 0:
                home_team = home_team[0]
            else:
                home_team = None

            gamestate_before = sheets.read_sheet(sheet_id, assets.calc_cell['game_state'])[0]
            result_raw = raw_text(sheets.read_sheet(sheet_id, assets.calc_cell['result']))
            pitcher = at_bat[2]
            batter = at_bat[0]
            before_score = gamestate_before[0]
            before_inning = gamestate_before[1]
            before_outs = gamestate_before[2]
            before_obc_string = gamestate_before[4]

            check_text = '%s batting against %s \n%s - %s | %s\n\n%s' % (batter, pitcher, before_inning, before_outs, before_obc_string, result_raw)

            result_msg = await ctx.send('```%s```' % check_text)
            await result_msg.add_reaction('\N{baseball}')
            await result_msg.add_reaction('👎')
            prompt_msg = await ctx.send('Tap the :baseball: to confirm the above result or :thumbsdown: to reset the'
                                        ' calculator.')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == result_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['👎', '\N{baseball}']

            calc_be = sheets.read_sheet(sheet_id, assets.calc_cell['calc_be'])
            before_home_score = calc_be[0][4]
            before_away_score = calc_be[0][5]
            after_home_score = calc_be[0][19]
            after_away_score = calc_be[0][20]
            before_score = int(before_home_score) + int(before_away_score)
            after_score = int(after_home_score) + int(after_away_score)

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                await prompt_msg.edit(content='Resulting at bat, please wait sheets API can be slow...')
                if game_data[0][0] != 'SCRIM':
                    log_result(sheet_id, away_team[1], home_team[1])

                if await commit_at_bat(ctx, sheet_id):
                    await ctx.send('Result submitted.')
                else:
                    await ctx.send('Something went wrong, please check the sheet.')
                    return
            elif reaction.emoji == '👎':
                await ctx.send('Resetting calculator, please wait...')
                await reset(ctx, sheet_id)
                return

            gamestate_after = sheets.read_sheet(sheet_id, assets.calc_cell['game_state'])[0]
            after_score_string = gamestate_after[0]
            after_inning = gamestate_after[1]
            after_outs = gamestate_after[2]
            after_obc_count = gamestate_after[3]
            after_obc_string = gamestate_after[4]

            check_text += '\n\n%s - %s | %s' % (after_inning, after_outs, after_obc_string)

            if home_team and away_team:
                title = "%s @ %s" % (away_team[1], home_team[1])
            else:
                title = "%s @ %s" % (away_team_name, home_team_name)
            text = "%s batting against %s\n%s with %s\n\n" % (batter, pitcher, before_inning, before_outs)
            text += "%s\n" % result_raw
            text += "%s, %s with %s\n\n" % (after_obc_string, after_inning, after_outs)
            text += "%s" % after_score_string

            await result_msg.edit(content='```%s```' % text)

            if 'B' in before_inning:
                result_team = home_team
            else:
                result_team = away_team

            embed = result_embed(text, result_team)
            embed.set_thumbnail(url=assets.obc_img[after_obc_count])
            if result_team:
                icon_url = result_team[3]
            else:
                icon_url = 'https://cdn.discordapp.com/emojis/809864952662982716.png?v=1'
            embed.set_author(name=title, url=thread, icon_url=icon_url)
            embed.add_field(name='View on Reddit', value='[Link](%s)' % thread)

            if away_team:
                if away_team[4]:
                    hook = Webhook(away_team[4])
                    hook.send(embed=embed)
            if home_team:
                if home_team[4]:
                    hook = Webhook(home_team[4])
                    hook.send(embed=embed)

            if before_score != after_score:
                await ctx.send("Run scores! Don't forget to ping!")
                if result_team:
                    await ctx.send('-hype %s %s' % (result_team[1], thread))

            data = sheets.read_sheet(sheet_id, assets.calc_cell['boxscore'])
            boxscore_raw = raw_text(data)
            boxscore_raw += '\n---\nLast Updated at %s' % datetime.datetime.now()
            updated = await reddit.edit_thread(thread, boxscore_raw)
            if updated:
                await ctx.send('Box score updated.')
            else:
                await ctx.send('Unable to edit the reddit thread.')
            next_batter = sheets.read_sheet(sheet_id, assets.calc_cell['batter_name'])
            await ctx.send('Up next: %s' % next_batter[0][0])

    @commands.command(brief='Rolls back the last entry into the game log.',
                      description='Rolls back the last entry into the game log.')
    @commands.has_role(ump_role)
    async def rollback(self, ctx):
        await ctx.message.add_reaction(loading_emote)
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            rows = sheets.read_sheet(sheet_id, assets.calc_cell['game_log'])
            index = len(rows) - 1
            if len(rows[-1]) <= 11 and len(rows[-1]) != 6:
                index = len(rows)
            game_log = sheets.read_sheet(sheet_id, 'Game Log!G%s:M%s' % (index, index))[0]
            result_txt = '%s batting against %s' % (game_log[0], game_log[2])
            result_txt += '\n\nPlay: %s\nSwing: %s\nPitch: %s' % (game_log[4], game_log[1], game_log[3],)
            if len(game_log) >= 6:
                result_txt += '\nDiff: %s' % game_log[5]
            if len(game_log) >= 7:
                result_txt += ' > %s' % game_log[6]
            await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
            rollback_msg = await ctx.send('Clear last result?```%s```React to this message with ⚾ to confirm or 👎 to '
                                          'cancel.' % result_txt)
            await rollback_msg.add_reaction('\N{baseball}')
            await rollback_msg.add_reaction('👎')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == rollback_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['👎', '\N{baseball}']

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                play_number = sheets.read_sheet(sheet_id, assets.calc_cell['play_number'])
                if play_number:
                    play_number = play_number[0][0]
                    play_number = int(play_number) - 1
                sql = '''SELECT league, season, session, gameID FROM gameData WHERE sheetID=%s'''
                game_data = db.fetch_data(sql, (sheet_id,))
                if game_data:
                    if game_data[0][0] != 'SCRIM':
                        game_data = game_data[0]
                        pa_id = get_pa_id(game_data[0], game_data[1], game_data[2], game_data[3], play_number)
                        sql = '''DELETE FROM PALogs WHERE paID=%s'''
                        db.update_database(sql, (pa_id,))
                        await ctx.send('Play removed from database, removing from ump helper sheet...')
                sheets.update_sheet(sheet_id, 'Game Log!G%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!H%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!I%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!J%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!K%s' % index, '', lazy=True)
                check_game_log = sheets.read_sheet(sheet_id, assets.calc_cell['game_log'])
            elif reaction.emoji == '👎':
                await rollback_msg.add_reaction('❌')

    @commands.command(brief='Set game thread URL for current game',
                      description='Adds the given game thread URL to the umpire table in the database.')
    @commands.has_role(ump_role)
    async def set_game_thread(self, ctx, reddit_url):
        if is_ump(ctx.author.id):
            standardize_url = await reddit.get_thread_url(reddit_url)
            sql = '''UPDATE umpData SET gameThread=%s WHERE discordID = %s'''
            db.update_database(sql, (standardize_url.url, ctx.author.id))
            url = db.fetch_data('''SELECT gameThread FROM umpData WHERE discordID = %s''', (ctx.author.id, ))
            if url:
                await ctx.send('Set game thread to %s' % url[0])

    @commands.command(brief='Set google sheets ID for game',
                      description='Adds the given google sheet ID to the umpire table in the database.')
    @commands.has_role(ump_role)
    async def set_sheet_id(self, ctx, sheet_id):
        if is_ump(ctx.author.id):
            if 'docs.google.com/spreadsheets/' in sheet_id:
                sheet_id = sheets.get_sheet_id(sheet_id)
            sql = '''UPDATE umpData SET sheetID=%s WHERE discordID = %s'''
            db.update_database(sql, (sheet_id, ctx.author.id))
            await ctx.send('Set google sheet to https://docs.google.com/spreadsheets/d/%s' % sheet_id)
            discord_username = str(ctx.author)
            for i in range(3):
                sheet_cell = 'Calculator!F%s' % (i + 23)
                umphandle = sheets.read_sheet(sheet_id, sheet_cell)
                if not umphandle:
                    sheets.update_sheet(sheet_id, sheet_cell, discord_username)
                    check_ump_handle = sheets.read_sheet(sheet_id, sheet_cell)[0]
                    if not check_ump_handle[0] == discord_username:
                        await ctx.send('Something went wrong adding your discord username to the sheet.\n'
                                       'https://docs.google.com/spreadsheets/d/%s' % sheet_id)
                    break

    @commands.command(brief='Game setup',
                      description='Creates a copy of the most recent version of the ump helper sheet and logs the game in the database. Also sets the sheet ID for all umps that are tagged.')
    @commands.has_role(ump_role)
    async def setup(self, ctx, league, ump2: discord.Member = None, ump3: discord.Member = None, ump4: discord.Member = None, ump5: discord.Member = None, ump6: discord.Member = None):
        await ctx.message.add_reaction(loading_emote)
        league = league.upper()
        season = read_config(league_config, league.upper(), 'Season')
        session = read_config(league_config, league.upper(), 'Session')
        title = '%s.%s - Ump Helper - %s' % (season, session, ctx.author.display_name)
        ump_list = [ctx.author.id]
        if ump2 and ump2.id != ctx.author.id:
            title += ' %s' % ump2.display_name
            ump_list.append(ump2.id)
        if ump3 and ump3.id != ctx.author.id:
            title += ' %s' % ump3.display_name
            ump_list.append(ump3.id)
        if ump4 and ump4.id != ctx.author.id:
            title += ' %s' % ump4.display_name
            ump_list.append(ump4.id)
        if ump5 and ump5.id != ctx.author.id:
            title += ' %s' % ump5.display_name
            ump_list.append(ump5.id)
        if ump6 and ump6.id != ctx.author.id:
            title += ' %s' % ump6.display_name
            ump_list.append(ump6.id)
        sheet_id = sheets.copy_ump_sheet(read_config(league_config, league.upper(), 'sheet'), title)
        for ump in ump_list:
            sql = '''UPDATE umpData SET sheetID= %s WHERE discordID = %s'''
            db.update_database(sql, (sheet_id, ump))
            sql = '''SELECT playerID from umpData WHERE sheetID=%s'''
        ump_list_player_ids = ''
        player_ids = db.fetch_data(sql, (sheet_id,))
        for player_id in player_ids:
            ump_list_player_ids += '%s ' % player_id[0]
        game_id = int(read_config(league_config, league.upper(), 'gameid'))
        write_config(league_config, league.upper(), 'gameid', str(game_id + 1))
        await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
        await ctx.message.add_reaction('✅')
        game_log = (league, season, session, game_id, sheet_id, ump_list_player_ids)
        sql = '''INSERT INTO gameData (league, season, session, gameID, sheetID, umpires) VALUES (%s, %s, %s, %s, %s, %s)'''
        db.update_database(sql, game_log)
        await ctx.send('I have created a copy of the ump helper sheet for you. Open the **Starting Lineups** page, select the two teams from the drop down lists, and input the starting lineups.\nhttps://docs.google.com/spreadsheets/d/%s\n\nWhen you\'re done use .post_thread to complete game setup.' % sheet_id)

    @commands.command(brief='Returns ump helper sheet for game',
                      description='Returns a link to the google sheet calculator in the database.')
    @commands.has_role(ump_role)
    async def sheet(self, ctx):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            await ctx.send('https://docs.google.com/spreadsheets/d/%s' % sheet_id)

    @commands.command(brief='Set pitch for current at bat',
                      desciption='Adds the swing into the calculator. Does not process any results.')
    @commands.has_role(ump_role)
    async def swing(self, ctx, swing):
        if not 0 < int(swing) <= 1000:
            await ctx.send('Swing must be between 1 and 1000')
            return
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            sheets.update_sheet(sheet_id, assets.calc_cell['swing'], int(swing))
            check_swing = sheets.read_sheet(sheet_id, assets.calc_cell['swing'])
            if check_swing[0][0] == swing:
                await ctx.message.add_reaction('✅')
            else:
                await ctx.send('Something went wrong. Could not set swing to %s' % swing)

    @commands.command(brief='Returns reddit thread for game',
                      description='Returns a link to the game thread stored in the database.')
    @commands.has_role(ump_role)
    async def thread(self, ctx):
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[8]
            await ctx.send('%s' % sheet_id)

    @commands.command(brief='Displays game info about an umpire',
                      description='Returns the discord username, sheet ID, and game thread that is configured in the database.')
    @commands.has_role(ump_role)
    async def ump(self, ctx, member: discord.Member = None):
        if member:
            ump_admin = discord.utils.get(ctx.guild.roles, id=int(config_ini['Discord']['ump_admin_role']))
            if ump_admin in ctx.author.roles:
                config = await get_ump_data(ctx, member.id)
            else:
                await ctx.send('You can\'t do that')
                return
        else:
            config = await get_ump_data(ctx, ctx.author.id)
        if config:
            embed = discord.Embed(title=config[0])
            embed.add_field(name='Discord', value='<@%s>' % config[1], inline=True)
            if config[2] != 'update':
                embed.add_field(name='Ump Helper', value='[Link](https://docs.google.com/spreadsheets/d/%s)' % config[2], inline=False)
            if config[8]:
                embed.add_field(name='Game Thread', value='[Link](%s)' % config[8], inline=False)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ump(bot))


# Helper Functions

async def at_bat_ping(bot, msg, channel_id):
    ab_ping_channel = bot.get_channel(channel_id)
    await ab_ping_channel.send(msg)


async def get_ump_data(ctx, discord_id):
    sql = '''SELECT * FROM umpData WHERE discordID=%s'''
    ump_data = db.fetch_data(sql, (discord_id,))
    if len(ump_data) == 1:
        if ump_data[0][2] == 'update':
            await ctx.send('Warning: SheetID not set. Please update before continuing.')
            return ump_data[0]
        elif ump_data[0][8] == '':
            await ctx.send('Warning: reddit thread missing. Please update before continuing. (Ignore this warning if '
                           'you are doing .post_thread)')
            return ump_data[0]
        else:
            return ump_data[0]
    elif len(ump_data) > 1:
        await ctx.send('Something went wrong, please contact an admin for assistance.')
    else:
        await ctx.send('Umpire profile not configured, please contact an admin for assistance.')


async def commit_at_bat(ctx, sheet_id):
    rows = sheets.read_sheet(sheet_id, 'Game Log')
    game_update = sheets.read_sheet(sheet_id, assets.calc_cell['at_bat'])[0]
    sheets.update_sheet(sheet_id, 'Game Log!G%s' % len(rows), game_update[0])
    sheets.update_sheet(sheet_id, 'Game Log!H%s' % len(rows), game_update[1])
    sheets.update_sheet(sheet_id, 'Game Log!I%s' % len(rows), game_update[2])
    sheets.update_sheet(sheet_id, 'Game Log!J%s' % len(rows), game_update[3])
    sheets.update_sheet(sheet_id, 'Game Log!K%s' % len(rows), game_update[4])
    await reset(ctx, sheet_id)
    check_game_log = sheets.read_sheet(sheet_id, 'Game Log!G%s:K%s' % (len(rows), len(rows)))[0]
    if check_game_log == game_update:
        return True
    else:
        return False


def is_ump(discord_id):
    sql = '''SELECT * FROM umpData WHERE discordID=%s'''
    data = db.fetch_data(sql, (discord_id,))
    if len(data) == 1:
        return True
    else:
        return False


def format_text(rows):
    string = '```'
    for row in rows:
        if len(row) > 0:
            string += row[0]
        string += "\n"
    string += '```'
    return string


def get_pa_id(league, season, session, game_id, play_number):
    if league.lower() == 'mlr':
        pa_id = '1'
    elif league.lower() == 'milr':
        pa_id = '2'
    elif league.lower() == 'gib':
        pa_id = '3'
    elif league.lower() == 'fcb':
        pa_id = '4'
    else:
        pa_id = '9'

    pa_id += '%s%s%s%s' % (str(season).zfill(2), str(session).zfill(2), str(game_id).zfill(3), str(play_number).zfill(3))

    return int(pa_id)


def log_result(sheet_id, away_team, home_team):
    # Fetch data from sheet
    calc_be = sheets.read_sheet(sheet_id, assets.calc_cell['calc_be'])
    play_number = sheets.read_sheet(sheet_id, assets.calc_cell['play_number'])
    league = sheets.read_sheet(sheet_id, assets.calc_cell['league'])

    if play_number:
        play_number = play_number[0][0]
        play_number = int(play_number)
    league = db.fetch_data('SELECT LEAGUE FROM gameData WHERE sheetID=%s', (sheet_id,))
    if league:
        league = league[0][0].lower()

    # Get game ID from database
    sql = '''SELECT gameID, season, session from gameData where sheetID = %s'''
    gameID = db.fetch_data(sql, (sheet_id,))
    if gameID:
        season = gameID[0][1]
        session = gameID[0][2]
        gameID = gameID[0][0]

    if calc_be:
        # Parse easy stuff right from the sheet
        calc_be = calc_be[0]
        inning = calc_be[1]
        outs = int(calc_be[2])
        obc = int(calc_be[3])
        awayScore = int(calc_be[5])
        homeScore = int(calc_be[4])
        pitcherName = calc_be[8]
        hitterName = calc_be[6]
        pitch = calc_be[9]
        swing = calc_be[7]
        diff = calc_be[11]
        exactResult = calc_be[78]
        oldResult = calc_be[77]
        resultAtNeutral = calc_be[79]
        resultAllNeutral = calc_be[80]
        run = calc_be[14]
        if not run:
            run = None
        pr3B = None
        pr2B = None
        pr1B = None
        prAB = None
        if len(calc_be) > 87:
            if calc_be[87]:
                pr3B = calc_be[87]
        if len(calc_be) > 88:
            if calc_be[88]:
                pr2B = calc_be[88]
        if len(calc_be) > 89:
            if calc_be[89]:
                pr1B = calc_be[89]
        if len(calc_be) > 90:
            if calc_be[90]:
                prAB = calc_be[90]

        # Sheet isn't calculating RBIs currently
        rbi = 0
        if diff and 'steal' not in calc_be[10].lower() and 'DP' not in calc_be[12].upper():
            rbi = (int(calc_be[20]) + int(calc_be[19])) - (int(calc_be[5]) + int(calc_be[4]))

        # Update Game Log with current game state
        away_score_after = int(calc_be[20])
        home_score_after = int(calc_be[19])
        inning_after = calc_be[16]
        outs_after = int(calc_be[17])
        obc_after = int(calc_be[18])
        sql = '''UPDATE gameData SET awayScore=%s, homeScore=%s, inning=%s, outs=%s, obc=%s WHERE sheetID=%s'''
        game_log = (away_score_after, home_score_after, inning_after, outs_after, obc_after, sheet_id)
        db.update_database(sql, game_log)

        pa_log = format_pa_log(league, season, session, gameID, inning, play_number, outs, obc, awayScore, homeScore,
                               away_team, home_team, pitcherName, hitterName, pitch, swing, diff, exactResult,
                               oldResult, resultAtNeutral, resultAllNeutral, rbi, run, pr3B, pr2B, pr1B, prAB,
                               inning_after, obc_after, outs_after, away_score_after, home_score_after)
        # pa_log = (paID, league, season, session, gameID, inning, inningID, play_number, outs, obc, awayScore, homeScore, pitcherTeam, pitcherName, pitcherID, hitterTeam, hitterName, hitterID, pitch, swing, diff, exactResult, oldResult, resultAtNeutral, resultAllNeutral, rbi, run, batterWPA, pitcherWPA, pr3B, pr2B, pr1B, prAB)
        sql = '''INSERT INTO PALogs VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        db.update_database(sql, pa_log)
    return


def calculate_win_prob(inning_before, outs_before, obc_before, away_score_before, home_score_before, inning_after,
                       outs_after, obc_after, away_score_after, home_score_after):
    if 'T' in inning_before:
        run_diff_before = away_score_before - home_score_before
        if 'T' in inning_after:
            run_diff_after = home_score_after - away_score_after
        else:
            run_diff_after = away_score_after - home_score_after
    else:
        run_diff_before = home_score_before - away_score_before
        if 'B' in inning_after:
            run_diff_after = away_score_after - home_score_after
        else:
            run_diff_after = home_score_after - away_score_after
    if run_diff_before == 0:
        column_name_before = 'tie'
    elif run_diff_before <= -10:
        column_name_before = 'd10'
    elif run_diff_before >= 10:
        column_name_before = 'u10'
    elif -10 < run_diff_before < 0:
        column_name_before = 'd%s' % str(run_diff_before)[1]
    elif 0 < run_diff_before < 10:
        column_name_before = 'u%s' % run_diff_before
    else:
        column_name_before = None

    if run_diff_after == 0:
        column_name_after = 'tie'
    elif run_diff_after <= -10:
        column_name_after = 'd10'
    elif run_diff_after >= 10:
        column_name_after = 'u10'
    elif -10 < run_diff_after < 0:
        column_name_after = 'd%s' % str(run_diff_after)[1]
    elif 0 < run_diff_after < 10:
        column_name_after = 'u%s' % run_diff_after
    else:
        column_name_after = None

    win_prob_before_key = '%s' % (inning_before[1])
    win_prob_after_key = '%s' % (inning_after[1])

    if 'T' in inning_before:
        win_prob_before_key += '1'
    else:
        win_prob_before_key += '2'
    if 'T' in inning_after:
        win_prob_after_key += '1'
    else:
        win_prob_after_key += '2'
    win_prob_before_key += '%s%s' % (obc_before, outs_before)
    win_prob_after_key += '%s%s' % (obc_after, outs_after)

    sql = '''SELECT %s from winProbability ''' % column_name_before
    sql += '''WHERE gameState=%s'''
    win_prob_before = db.fetch_data(sql, (int(win_prob_before_key),))[0][0]

    sql = '''SELECT %s from winProbability ''' % column_name_after
    sql += '''WHERE gameState=%s'''
    win_prob_after = db.fetch_data(sql, (int(win_prob_after_key),))[0][0]

    if win_prob_before_key[0:2] != win_prob_after_key[0:2]:
        if win_prob_after:
            win_prob_after = 100 - win_prob_after
        else:
            win_prob_after = 0

    batter_wpa = ''
    pitcher_wpa = ''

    if win_prob_before and win_prob_after:
        batter_wpa = win_prob_after - win_prob_before
        wpa = '%.2f' % batter_wpa
        batter_wpa = wpa + '%'
        if batter_wpa[0] == '-':
            pitcher_wpa = batter_wpa[1:]
        else:
            pitcher_wpa = '-' + batter_wpa
    return batter_wpa, pitcher_wpa


def format_pa_log(league, season, session, game_id, inning, play_number, outs, obc, away_score, home_score, away_team,
                  home_team, pitcher_name, hitter_name, pitch, swing, diff, exact_result, old_result, result_at_neutral,
                  result_all_neutral, rbi, run, pr3B, pr2B, pr1B, prAB, after_inning, after_obc, after_outs,
                  after_away_score, after_home_score):
    league = league.lower()
    if 'B' in inning:
        pitcher_team = away_team
        hitter_team = home_team
    else:
        pitcher_team = home_team
        hitter_team = away_team

    if not run:
        run = None

    paID = get_pa_id(league, season, session, game_id, play_number)

    sql = '''SELECT inningID FROM PALogs WHERE league=%s AND season=%s AND session=%s AND gameID=%s AND inning = %s'''
    inning_data = db.fetch_data(sql, (league, season, session, game_id, inning))
    if inning_data:
        inningID = inning_data[0][0]
    else:
        inningID = read_config(league_config, league.upper(), 'inningid')
        inningID = int(inningID)
        write_config(league_config, league.upper(), 'inningid', str(inningID + 1))

    # Fetch player IDs for pitcher and batter
    sql = '''SELECT playerID from playerData WHERE playerName LIKE %s'''
    hitter = db.fetch_data(sql, ('%' + hitter_name + '%',))
    pitcher = db.fetch_data(sql, ('%' + pitcher_name + '%',))

    hitter_id = None
    pitcher_id = None
    if hitter:
        hitter_id = hitter[0][0]
    if pitcher:
        pitcher_id = pitcher[0][0]

    if pitch == ' ':
        pitch = None
    else:
        pitch = int(pitch)
    if swing == ' ':
        swing = None
    else:
        swing = int(swing)
    if diff == ' ' or diff == 'x':
        diff = None
    else:
        diff = int(diff)

    if pr3B and pr3B != '#REF!':
        pr3B = db.fetch_data(sql, ('%' + pr3B + '%',))[0][0]
    else:
        pr3B = None
    if pr2B and pr2B != '#REF!':
        pr2B = db.fetch_data(sql, ('%' + pr2B + '%',))[0][0]
    else:
        pr2B = None
    if pr1B and pr1B != '#REF!':
        pr1B = db.fetch_data(sql, ('%' + pr1B + '%',))[0][0]
    else:
        pr1B = None
    if prAB and prAB != '#REF!':
        prAB = db.fetch_data(sql, ('%' + prAB + '%',))[0][0]
    else:
        prAB = None

    batter_wpa, pitcher_wpa = calculate_win_prob(inning, outs, obc, away_score, home_score, after_inning, after_outs, after_obc, after_away_score, after_home_score)

    return paID, league, season, session, game_id, inning, inningID, play_number, outs, obc, away_score, home_score, pitcher_team, pitcher_name, pitcher_id, hitter_team, hitter_name, hitter_id, pitch, swing, diff, exact_result, old_result, result_at_neutral, result_all_neutral, rbi, run, batter_wpa, pitcher_wpa, pr3B, pr2B, pr1B, prAB


def raw_text(rows):
    string = ''
    for row in rows:
        if len(row) > 0:
            string += row[0]
        string += "\n"
    return string


def read_config(filename, section, setting):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    return ini_file[section][setting]


async def reset(ctx, sheet_id):
    check_event = sheets.update_sheet(sheet_id, assets.calc_cell['event'], 'Swing')
    check_pitch = sheets.update_sheet(sheet_id, assets.calc_cell['pitch'], ' ')
    check_swing = sheets.update_sheet(sheet_id, assets.calc_cell['swing'], ' ')
    if check_swing and check_pitch and check_event:
        await ctx.send('Calculator reset successfully.')
    else:
        await ctx.send('Something went wrong, please try again or check the sheet.')


def result_embed(text, team):
    if team:
        embed_color = discord.Color(value=int(team[2], 16))
        embed = discord.Embed(description=text, color=embed_color)
    else:
        embed = discord.Embed(description=text)
    return embed


def write_config(filename, section, setting, value):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    ini_file.set(section, setting, value)
    with open(filename, 'w') as configfile:
        ini_file.write(configfile)
