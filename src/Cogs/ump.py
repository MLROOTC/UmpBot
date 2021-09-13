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


class Ump(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ab_ping_channel = int(config_ini['Channels']['ab_bat_pings_channel'])
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
            valid_events = ['Swing', 'Auto K', 'Auto BB', 'Bunt', 'Steal 2B', 'Steal 3B', 'Steal Home', 'Infield In',
                            'IBB']
            if event_type not in valid_events:
                await ctx.send('%s is not a valid event type. Please use: %s' % (event_type, valid_events))
            else:
                if event_type in ['Auto K', 'Auto BB', 'IBB']:
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

                    away_team = sheets.read_sheet(sheet_id, assets.calc_cell['away_team'])
                    away_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = ?''', (away_team[0][0],))
                    away_score = sheets.read_sheet(sheet_id, assets.calc_cell['away_score'])

                    home_team = sheets.read_sheet(sheet_id, assets.calc_cell['home_team'])
                    home_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = ?''', (home_team[0][0],))
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
                        sql = '''UPDATE umpData SET sheetID=? WHERE sheetID = ?'''
                        db.update_database(sql, ('update', sheet_id))
                        sql = '''UPDATE umpData SET gameThread=? WHERE gameThread = ?'''
                        db.update_database(sql, (None, thread))
                        sql = '''SELECT * FROM umpData WHERE discordID=?'''
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
            main = self.bot.get_guild(int(self.main_guild_id))
            discord_ping = None
            if batter_name:
                batter_discord = db.fetch_data('''SELECT discordID, discordName FROM playerData WHERE playerName = ?''',
                                               (batter_name[0][0],))
                if not batter_discord:
                    data = sheets.read_sheet(sheet_id, assets.calc_cell['discord_ping'])
                    if 'NO PING NECESSARY' in data[1][0].upper():
                        await ctx.send('Discord not on file, no ping necessary.')
                        return
                    discord_name = sheets.read_sheet(sheet_id, assets.calc_cell['discord_name'])[0][0]
                    discord_name = discord_name[1:discord_name.index('#') + 5]
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
                ab_ping += '%s is up to bat!' % discord_ping
                ab_ping += ' No need to ping your umps when you swing, we have bots for that.\n%s' % config[8]
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
        config = await get_ump_data(ctx, ctx.author.id)
        if config:
            sheet_id = config[2]
            lineup_check = sheets.read_sheet(sheet_id, assets.calc_cell['lineup_check'])[0]
            if lineup_check[0] == 'That\'s a good lineup!' and lineup_check[3] == 'That\'s a good lineup!':
                game_data = sheets.read_sheet(sheet_id, assets.calc_cell['game_data'])[0]
                box_score = sheets.read_sheet(sheet_id, assets.calc_cell['boxscore'])
                season_session = sheets.read_sheet(self.master_ump_sheet, assets.calc_cell['season_session'])[0][0]
                away_team = game_data[0]
                home_team = game_data[3]
                away_team = away_team.title()
                home_team = home_team.title()
                away_team = away_team.replace('\'S', '\'s')
                home_team = home_team.replace('\'S', '\'s')

                milr = game_data[5]
                thread_title = ''
                if milr == 'TRUE':
                    thread_title += '[MiLR'
                elif milr == 'FALSE':
                    thread_title += '[MLR'
                else:
                    thread_title += '[FCB'
                thread_title += ' %s.%s%s Game Thread] %s at %s' % (season_session[0], season_session[1],
                                                                    season_session[2], away_team.title(),
                                                                    home_team.title())
                if custom_text:
                    thread_title += ' - %s' % custom_text
                body = raw_text(box_score)
                thread = await reddit.post_thread(self.subreddit_name, thread_title, body)
                await ctx.send(thread.url)
                sql = '''UPDATE umpData SET gameThread=? WHERE discordID = ?'''
                db.update_database(sql, (thread.url, ctx.author.id))
                start_game_command = '-startgame'
                away_team = sheets.read_sheet(sheet_id, assets.calc_cell['away_team'])
                away_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = ?''', (away_team[0][0],))
                if len(away_team) > 0:
                    start_game_command += ' %s' % away_team[0]

                home_team = sheets.read_sheet(sheet_id, assets.calc_cell['home_team'])
                home_team = db.fetch_data('''SELECT abb FROM teamData WHERE name = ?''', (home_team[0][0],))
                if len(home_team) > 0:
                    start_game_command += ' %s' % home_team[0]
                start_game_command += ' %s' % thread.url
                await ctx.send('Game thread set. Play ball!')
                await ctx.send(start_game_command)
            else:
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

            away_team = db.fetch_data('''SELECT * FROM teamData WHERE name = ?''', (away_team_name,))
            if len(away_team) > 0:
                away_team = away_team[0]
            else:
                away_team = None
            home_team = db.fetch_data('''SELECT * FROM teamData WHERE name = ?''', (home_team_name,))
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

            check_text = '%s batting against %s \n%s - %s | %s\n\n%s' % (batter, pitcher, before_inning,
                                                                                before_outs, before_obc_string,
                                                                                result_raw)

            result_msg = await ctx.send('```%s```' % check_text)
            await result_msg.add_reaction('\N{baseball}')
            await result_msg.add_reaction('👎')
            prompt_msg = await ctx.send('Tap the :baseball: to confirm the above result or :thumbsdown: to reset the'
                                        ' calculator.')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == result_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['👎', '\N{baseball}']

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                await prompt_msg.edit(content='Resulting at bat, please wait sheets API can be slow...')
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
            after_score = gamestate_after[0]
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
            text += "%s" % after_score

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

            if before_score != after_score and before_score != 'Start of Game':
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
            rollback_msg = await ctx.send('Clear last result?```%s```React to this message with ⚾ to confirm or 👎 to '
                                          'cancel.' % result_txt)
            await rollback_msg.add_reaction('\N{baseball}')
            await rollback_msg.add_reaction('👎')

            def check(result_reaction, ump_user):
                return result_reaction.message.id == rollback_msg.id and ump_user == ctx.message.author and str(
                    result_reaction.emoji) in ['👎', '\N{baseball}']

            reaction, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
            if reaction.emoji == '\N{baseball}':
                sheets.update_sheet(sheet_id, 'Game Log!G%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!H%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!I%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!J%s' % index, '', lazy=True)
                sheets.update_sheet(sheet_id, 'Game Log!K%s' % index, '', lazy=True)
                check_game_log = sheets.read_sheet(sheet_id, assets.calc_cell['game_log'])
                if len(check_game_log[-1]) == 6:
                    await rollback_msg.add_reaction('✅')
                else:
                    await ctx.send('Something went wrong, please check the sheet for errors.')
            elif reaction.emoji == '👎':
                await rollback_msg.add_reaction('❌')

    @commands.command(brief='Set game thread URL for current game',
                      description='Adds the given game thread URL to the umpire table in the database.')
    @commands.has_role(ump_role)
    async def set_game_thread(self, ctx, reddit_url):
        if is_ump(ctx.author.id):
            standardize_url = await reddit.get_thread_url(reddit_url)
            sql = '''UPDATE umpData SET gameThread=? WHERE discordID = ?'''
            db.update_database(sql, (standardize_url.url, ctx.author.id))
            url = db.fetch_data('''SELECT gameThread FROM umpData WHERE discordID = ?''', (ctx.author.id, ))
            if url:
                await ctx.send('Set game thread to %s' % url[0])

    @commands.command(brief='Set google sheets ID for game',
                      description='Adds the given google sheet ID to the umpire table in the database.')
    @commands.has_role(ump_role)
    async def set_sheet_id(self, ctx, sheet_id):
        if is_ump(ctx.author.id):
            if 'docs.google.com/spreadsheets/' in sheet_id:
                sheet_id = sheets.get_sheet_id(sheet_id)
            sql = '''UPDATE umpData SET sheetID=? WHERE discordID = ?'''
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


def setup(bot):
    bot.add_cog(Ump(bot))


# Helper Functions

async def at_bat_ping(bot, msg, channel_id):
    ab_ping_channel = bot.get_channel(channel_id)
    await ab_ping_channel.send(msg)


async def get_ump_data(ctx, discord_id):
    sql = '''SELECT * FROM umpData WHERE discordID=?'''
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
    sql = '''SELECT * FROM umpData WHERE discordID=?'''
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


def raw_text(rows):
    string = ''
    for row in rows:
        if len(row) > 0:
            string += row[0]
        string += "\n"
    return string


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
