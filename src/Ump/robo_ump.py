import configparser
import datetime

import discord
from discord.ui import Button, View
from dhooks import Webhook
import re
import src.assets as assets
import src.db_controller as db
import src.reddit_interface as reddit
import src.sheets_reader as sheets
import src.Ump.flavor_text_generator as flavor

config_ini = configparser.ConfigParser()
config_ini = 'config.ini'
league_config = 'league.ini'
master_ump_sheet = "1DTcSKkfpIn3_zRGY2_jdEGt3mSGT2nC2y1aJoXe--Rk"
regex = "[^0-9]"
lineup_string = "That\'s a good lineup!"


def commit_at_bat(sheet_id):
    rows = sheets.read_sheet(sheet_id, 'NewGL')
    game_update = sheets.read_sheet(sheet_id, assets.calc_cell2['at_bat'])[0]
    sheets.update_sheet(sheet_id, f'NewGL!G{len(rows)}', game_update[0])
    sheets.update_sheet(sheet_id, f'NewGL!H{len(rows)}', game_update[1])
    sheets.update_sheet(sheet_id, f'NewGL!I{len(rows)}', game_update[2])
    sheets.update_sheet(sheet_id, f'NewGL!J{len(rows)}', game_update[3])
    sheets.update_sheet(sheet_id, f'NewGL!K{len(rows)}', game_update[4])
    sheets.update_sheet(sheet_id, assets.calc_cell2['pitch'], ' ')
    sheets.update_sheet(sheet_id, assets.calc_cell2['swing'], ' ')
    sheets.update_sheet(sheet_id, assets.calc_cell2['event'], 'Swing')
    return


async def create_ump_sheets(bot, session: int):
    games = sheets.read_sheet(master_ump_sheet, f'Session {session}')
    for game in games:
        if game[0] != 'League':
            league = game[0]
            away_team = game[1]
            home_team = game[2]
            away_name, away_role_id = db.fetch_one('SELECT name, role_id FROM teamData WHERE abb=%s', (away_team,))
            home_name, home_role_id = db.fetch_one('SELECT name, role_id FROM teamData WHERE abb=%s', (home_team,))
            flavor_text = ''
            if len(game) == 4:
                flavor_text = game[3]
            season = int(read_config(league_config, league, 'season'))
            game_check = db.fetch_one(
                'SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND awayTeam=%s AND homeTeam=%s',
                (league, season, session, away_team, home_team))
            if not game_check:
                # Create Copy of Ump Sheet
                file_id = read_config(league_config, league.upper(), 'sheet')
                sheet_title = f'{league.upper()} {season}.{session} - {away_team} vs {home_team}'
                sheet_id = sheets.copy_ump_sheet(file_id, sheet_title)
                sheets.update_sheet(sheet_id, assets.calc_cell2['away_team'], away_name)
                sheets.update_sheet(sheet_id, assets.calc_cell2['home_team'], home_name)
                log_msg(
                    f'Created ump sheet {league.upper()} {season}.{session} - {away_team}@{home_team}: <https://docs.google.com/spreadsheets/d/{sheet_id}>')

                # Insert New Game into Database
                game_id = int(read_config(league_config, league.upper(), 'gameid'))
                write_config(league_config, league.upper(), 'gameid', str(game_id + 1))
                sql = '''INSERT INTO gameData (league, season, session, gameID, sheetID, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                data = (league, season, session, game_id, sheet_id, away_team, home_team, 0, 0, 'T1', 0, 0, 0, 'SETUP')
                db.update_database(sql, data)
                sql = '''INSERT INTO pitchData (league, season, session, game_id) VALUES (%s,%s,%s,%s)'''
                data = (league, season, session, game_id)
                db.update_database(sql, data)

                # Post Thread
                thread = await post_thread(sheet_id, league, season, session, away_name, home_name, flavor_text)
                db.update_database('''UPDATE gameData SET threadURL=%s WHERE sheetID=%s''', (thread.url, sheet_id))

                # Ping in #game-discussion
                hype_ping = f'<@&{away_role_id}> <@&{home_role_id}> your game thread has been created! {thread.url}'
                channel = int(read_config(league_config, league.upper(), 'game_discussion'))
                channel = bot.get_channel(channel)
                await channel.send(hype_ping)
                set_state(league, season, session, game_id, 'WAITING FOR LINEUPS')
    return


async def edit_warning(bot, league, season, session, game_id):
    # TODO Ping ump warden (ump council?) when someone edits a swing/pitch
    # include user ID, message id,
    ump_hq = read_config(config_ini, 'Channels', 'ump_hq')
    ump_hq = bot.get_channel(int(ump_hq))
    await ump_hq.send('SWING HAS BEEN EDITED MODS PLS BAN')
    set_state(league, season, session, game_id, 'PAUSED')
    return


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
                game_data = db.fetch_one('''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',game[0:4])
                prompt += f'{i + 1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if active_games[game_number - 1][4] == pitcher_id[0]:
                return active_games[game_number - 1][0:4], 'home'
            elif active_games[game_number - 1][5] == pitcher_id[0]:
                return active_games[game_number - 1][0:4], 'away'
            else:
                await ctx.send('Are you even pitching right now??')
    else:
        await ctx.send(
            "I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


async def fetch_game_conditional_pitch(ctx, bot):
    pitcher_id, = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (ctx.author.id,))
    if pitcher_id:
        active_games = db.fetch_data('''SELECT league, season, session, game_id FROM pitchData WHERE conditional_pitcher=%s AND conditional_pitch_src IS NULL''', (pitcher_id, ))
        if not active_games:
            await ctx.send("I couldn't find any active games you are pitching in.")
            return None
        if len(active_games) == 1:
            return active_games[0]
        else:
            prompt = f'**Multiple games found. Please select a game:** \n```'
            for i in range(len(active_games)):
                game = active_games[i]
                game_data = db.fetch_one('''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',game[0:4])
                prompt += f'{i + 1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if active_games[game_number - 1][4] == pitcher_id[0]:
                return active_games[game_number - 1][0:4]
            elif active_games[game_number - 1][5] == pitcher_id[0]:
                return active_games[game_number - 1][0:4]
            else:
                await ctx.send('Are you even pitching right now??')
    else:
        await ctx.send(
            "I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


async def fetch_game_swing(ctx, bot):
    batter_id = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (ctx.author.id,))
    if batter_id:
        active_games = db.fetch_data(
            '''SELECT league, season, session, game_id, current_batter FROM pitchData WHERE current_batter=%s''',
            (batter_id[0],))
        if not active_games:
            await ctx.send("You aren't up to bat anywhere.")
            return None
        if len(active_games) == 1:
            if active_games[0][4] == batter_id[0]:
                return active_games[0][0:4]
            elif active_games[0][5] == batter_id[0]:
                return active_games[0][0:4]
            else:
                await ctx.send('Are you even pitching right now??')
        else:
            prompt = f'**Multiple games found. Please select a game:** \n```'
            for i in range(len(active_games)):
                game = active_games[i]
                game_data = db.fetch_one(
                    '''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
                    game[0:4])
                prompt += f'{i + 1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if active_games[game_number - 1][4] == batter_id[0]:
                return active_games[game_number - 1][0:4]
            elif active_games[game_number - 1][5] == batter_id[0]:
                return active_games[game_number - 1][0:4]
            else:
                await ctx.send('You aren\'t up to bat anywhere.')
    else:
        await ctx.send(
            "I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


async def fetch_game_conditional_swing(ctx, bot):
    batter_id = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (ctx.author.id,))
    if batter_id:
        active_games = db.fetch_data('''SELECT league, season, session, game_id, current_batter FROM pitchData WHERE conditional_batter=%s''', (batter_id[0],))
        if not active_games:
            await ctx.send("You aren't up to bat anywhere.")
            return None
        if len(active_games) == 1:
            if active_games[0][4] == batter_id[0]:
                return active_games[0][0:4]
            elif active_games[0][5] == batter_id[0]:
                return active_games[0][0:4]
            else:
                await ctx.send('Are you even pitching right now??')
        else:
            prompt = f'**Multiple games found. Please select a game:** \n```'
            for i in range(len(active_games)):
                game = active_games[i]
                game_data = db.fetch_one('''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',game[0:4])
                prompt += f'{i + 1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if active_games[game_number - 1][4] == batter_id[0]:
                return active_games[game_number - 1][0:4]
            elif active_games[game_number - 1][5] == batter_id[0]:
                return active_games[game_number - 1][0:4]
            else:
                await ctx.send('You aren\'t up to bat anywhere.')
    else:
        await ctx.send(
            "I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


def fetch_game_team(team, season, session):
    if season is not None and session is not None:
        sql = '''SELECT league, season, session, gameID FROM gameData WHERE (awayTeam=%s OR homeTeam=%s) AND (season=%s AND session=%s) ORDER BY league, season, session, gameID'''
        data = (team, team, season, session)
    else:
        sql = '''SELECT league, season, session, gameID FROM gameData WHERE awayTeam=%s OR homeTeam=%s ORDER BY league, season, session, gameID'''
        data = (team, team)
    games = db.fetch_data(sql, data)
    if games:
        return games[-1]
    return None


def get_active_games():
    sql = '''SELECT league, season, session, gameID, state FROM gameData WHERE complete=%s AND state IS NOT NULL'''
    return db.fetch_data(sql, (0,))


def get_box_score(sheet_id):
    text = ''
    rows = sheets.read_sheet(sheet_id, assets.calc_cell2['boxscore'])
    for row in rows:
        if len(row) > 0:
            text += row[0]
        text += "\n"
    return text


def lineup_check(sheet_id):
    lineup_checker = sheets.read_sheet(sheet_id, assets.calc_cell2['good_lineup'])
    if lineup_checker:
        lineup_checker = lineup_checker[0]
    else:
        return False
    if len(lineup_checker) == 4:
        if lineup_string in lineup_checker[0] and lineup_string in lineup_checker[3]:
            return True
    return False


def get_current_lineup(league, season, session, game_id, home):
    sql = '''SELECT player_id, position, batting_order, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND home=%s ORDER BY batting_order'''
    lineup = db.fetch_data(sql, (league, season, session, game_id, home))
    print(lineup)
    lineup_string = ''
    for line in lineup:
        player_id, position, order, starting = line
        player_name = get_player_name(player_id)
        if not starting:
            order = ''
        lineup_string += f'{order: <3} {player_name: <25} - {position}\n'
        print(f'{order: <3} {player_name: <25} - {position}\n')
    return lineup_string


def get_current_session(team):
    league = db.fetch_one('''SELECT league FROM teamData WHERE abb=%s''', (team,))
    if league:
        league = league[0]
        season = int(read_config(league_config, league.upper(), 'season'))
        session = int(read_config(league_config, league.upper(), 'session'))
        return season, session
    return None, None


async def get_pitch(bot, player_id, league, season, session, game_id):
    discord_id, reddit_name = db.fetch_one('''SELECT discordID, redditName FROM playerData WHERE playerID=%s''', (player_id,))
    sheet_id, inning, state = db.fetch_one('SELECT sheetID, inning, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
    if 'T' in inning:
        home = 'home'
    else:
        home = 'away'

    if discord_id:
        sql = f'SELECT list_{home}, swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'
        current_list, swing_src = db.fetch_one(sql, (league, season, session, game_id))
        if current_list:
            current_list = current_list.split()
            current_pitcher = bot.get_user(int(discord_id))
            dm_channel = await current_pitcher.create_dm()
            pitch_src = await dm_channel.fetch_message(int(current_list[0]))
            if not pitch_src.edited_at:
                sql = '''UPDATE pitchData SET pitch_src=%s, pitch_requested=%s, pitch_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                db.update_database(sql, (pitch_src.id, datetime.datetime.utcnow(), datetime.datetime.utcnow(), league, season, session, game_id))
                await dm_channel.send(f'Using {await parse_pitch(bot, discord_id, pitch_src.id)}')
                current_list = current_list[1:]
                if len(current_list) == 0:
                    await dm_channel.send('List depleted, use `.queue_pitch` to add more pitches.')
                else:
                    current_list = ' '.join(current_list)
                    sql = f'''UPDATE pitchData SET list_{home}=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                    db.update_database(sql, (current_list, league, season, session, game_id))
                if swing_src and state != 'PAUSED':
                    set_state(league, season, session, game_id, 'WAITING FOR RESULT')
                else:
                    await post_at_bat(bot, league, season, session, game_id)
                    set_state(league, season, session, game_id, 'WAITING FOR SWING')
            else:
                edit_warning()
        else:
            ab_text = sheets.read_sheet(sheet_id, assets.calc_cell2['pitcher_ab'])
            ab_text = f'{ab_text[0][0]}\n{ab_text[1][0]}\n{ab_text[2][0]}'
            pitcher = bot.get_user(discord_id)
            pitch_request_msg = await pitcher.send(f'{ab_text}\r\nPitch time! Please submit a pitch using `.pitch ###` or create a list using `.queue_pitch ###`.')

            db.update_database('''UPDATE pitchData SET pitch_requested=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (pitch_request_msg.created_at, league, season, session, game_id))
    else:
        print('Im not supporting reddit only pitchers')
    return


async def get_player(ctx, name):
    sql = '''SELECT * from playerData WHERE playerName LIKE %s'''
    players = db.fetch_data(sql, ('%' + name + '%',))
    if len(players) == 1:
        return players[0]
    elif len(players) == 0:
        await ctx.send(f"Your search for {name} yielded no results.")
    else:
        reply = f"Your search for {name} returned too many results"
        for player in players:
            if player[1].lower() == name.lower():
                return player
            reply += f'\n - {player[1]}'
        await ctx.send(reply)
    return None


def get_player_id(player_name):
    player_id = db.fetch_one('''SELECT playerID FROM playerData WHERE playerName=%s''', (player_name,))
    if player_id:
        return player_id[0]
    return None


def get_player_name(player_id):
    player_name = db.fetch_one('''SELECT playerName FROM playerData WHERE playerID=%s''', (player_id,))
    if player_name:
        return player_name[0]
    return None


def get_player_from_discord(discord_id: int):
    player_id = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (discord_id,))
    if player_id:
        return player_id[0]
    return None


def get_sheet(league, season, session, game_id):
    sheet_id = db.fetch_one(
        '''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
        (league, season, session, game_id))
    if sheet_id:
        return sheet_id[0]
    return None


def get_swing_from_reddit(reddit_comment_url):
    swing_comment = reddit.get_comment(reddit_comment_url)

    numbers_in_comment = [int(i) for i in swing_comment.body.split() if i.isdigit()]
    if len(numbers_in_comment) == 1:
        swing = numbers_in_comment[0]
        if 0 < swing <= 1000:
            parent_thread = reddit.get_thread(swing_comment.submission)
            league, season, session, game_id, sheet_id, state = db.fetch_one('SELECT league, season, session, gameID, sheetID, state FROM gameData WHERE threadURL=%s',(parent_thread.url,))

            # Check for steal/bunt/etc
            event_check = check_for_event(sheet_id, swing_comment)
            if event_check:
                # Write swing src, swing submitted to database
                swing_submitted = datetime.datetime.utcfromtimestamp(swing_comment.created_utc)
                sql = '''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                db.update_database(sql, (swing_comment.id, swing_submitted, league, season, session, game_id))

                if state != 'WAITING FOR RESULT' or state != 'PAUSED':
                    set_state(league, season, session, game_id, 'WAITING FOR RESULT')
                return swing
            else:
                swing_comment.reply(f"Incorrect steal format. Please include one of the following in your swing to steal {assets.steal_types}")
                return None

    elif len(numbers_in_comment) == 0:
        swing_comment.reply("I couldn't find a valid number in your swing. Please reply to the original at-bat ping with a number between 1 and 1000 without any decimal spaces.")
        return None
    else:
        swing_comment.reply('I found too many numbers in your swing. Please reply to the original AB ping with only one number included in your swing.')
        return None


async def get_swing_from_reddit_async(reddit_comment_url):
    swing_comment = await reddit.get_comment_async(reddit_comment_url)

    numbers_in_comment = [int(i) for i in swing_comment.body.split() if i.isdigit()]
    if len(numbers_in_comment) == 1:
        swing = numbers_in_comment[0]
        if 0 < swing <= 1000:
            parent_thread = await reddit.get_thread_async(swing_comment.submission)
            league, season, session, game_id, sheet_id, state = db.fetch_one(
                'SELECT league, season, session, gameID, sheetID, state FROM gameData WHERE threadURL=%s',
                (parent_thread.url,))

            # Check for steal/bunt/etc
            event_check = check_for_event(sheet_id, swing_comment)
            if event_check:
                # Write swing src, swing submitted to database
                swing_submitted = datetime.datetime.utcfromtimestamp(swing_comment.created_utc)
                sql = '''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
                db.update_database(sql, (swing_comment.id, swing_submitted, league, season, session, game_id))
                if state != 'WAITING FOR RESULT' or state != 'PAUSED':
                    set_state(league, season, session, game_id, 'WAITING FOR RESULT')
                return swing
            else:
                steal_fail = "Incorrect steal format. Please include one of the following in your swing to steal: STEAL 2B, STEAL 3B, STEAL HOME, MULTISTEAL, 3B MULTISTEAL HOME"
                await swing_comment.reply(steal_fail)
                return None
    elif len(numbers_in_comment) == 0:
        await swing_comment.reply("I couldn't find a valid number in your swing. Please reply to the original at-bat ping with a number between 1 and 1000 without any decimal spaces.")
        return None
    else:
        await swing_comment.reply('I found too many numbers in your swing. Please reply to the original AB ping with only one number included in your swing.')
        return None


def check_for_event(sheet_id, swing_comment):
    if 'STEAL 2B' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL 2B')
        return True
    elif 'STEAL 3B' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL 3B')
        return True
    elif 'STEAL HOME' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL HOME')
        return True
    elif 'MULTISTEAL 3B' in swing_comment.body.upper():
        set_event(sheet_id, 'MULTISTEAL 3B')
        return True
    elif 'MULTISTEAL HOME' in swing_comment.body.upper():
        set_event(sheet_id, 'MULTISTEAL HOME')
        return True
    elif 'BUNT' in swing_comment.body.upper():
        set_event(sheet_id, 'BUNT')
    elif 'STEAL' in swing_comment.body.upper():
        return False
    else:
        return True


def log_msg(message: str):
    hook = Webhook(read_config(config_ini, 'Channels', 'error_log_webhook'))
    hook.send(message)
    return


def log_result(sheet_id, league, season, session, game_id, inning, outs, obc, away_score, home_score,
               pitcher_team, pitcher_name, pitcher_id, batter_name, batter_team, batter_id,
               pitch, swing, diff, exact_result, rbi, run,
               pitch_requested, pitch_submitted, swing_requested, swing_submitted
               ):
    play_number = sheets.read_sheet(sheet_id, assets.calc_cell2['play_number'])[0]
    pa_id = get_pa_id(league, season, session, game_id, play_number[0])

    # TODO finish log_result
    sql = '''SELECT inningID FROM PALogs WHERE league=%s AND season=%s AND session=%s AND gameID=%s AND inning = %s'''
    inning_id, = db.fetch_data(sql, (league, season, session, game_id, inning))
    if not inning_id:
        inningID = read_config(league_config, league.upper(), 'inningid')
        inningID = int(inningID)
        write_config(league_config, league.upper(), 'inningid', str(inningID + 1))

    result_log = sheets.read_sheet(sheet_id, assets.calc_cell2['log_result'])
    if result_log:
        result_log = result_log[0]
    old_result = result_log[0]
    result_at_neutral = result_log[2]
    result_all_neutral = result_log[3]
    batter_wpa = None
    pitcher_wpa = None
    pr_3B = result_log[10]
    pr_2B = result_log[11]
    pr_1B = result_log[12]
    pr_AB = result_log[13]

    # Check if result is already logged
    sql = '''SELECT * FROM PALogs WHERE paID=%s'''
    result_in_db = db.fetch_one(sql, (pa_id,))
    data = (pa_id, league, season, session, game_id, inning, inning_id, play_number, outs, obc, away_score, home_score,
            pitcher_team, pitcher_name, pitcher_id, batter_name, batter_team, batter_id,
            pitch, swing, diff, exact_result, old_result, result_at_neutral, result_all_neutral,
            rbi, run, batter_wpa, pitcher_wpa, pr_3B, pr_2B, pr_1B, pr_AB,
            pitch_requested, pitch_submitted, swing_requested, swing_submitted
            )
    if result_in_db:
        sql = '''UPDATE PALogs SET paID=%s, league=%s, season=%s, session=%s, gameID=%s, inning=%s, inningID=%s, playNumber=%s, outs=%s, obc=%s, awayScore=%s, homeScore=%s, pitcherTeam=%s, pitcherName=%s, pitcherID =%s, hitterTeam=%s, hitterName=%s, hitterID=%s, pitch=%s, swing=%s, diff=%s, exactResult=%s, oldResult=%s, resultAtNeutral=%s, resultAllNeutral=%s, rbi=%s, run=%s, batterWPA=%s, pitcherWPA=%s, pr3B=%s, pr2B=%s, pr1B =%s, prAB =%s, pitch_requested =%s, pitch_submitted=%s, swing_reqested =%s, swing_submitted=%s WHERE paID=%s'''
        data = data + (pa_id,)
    else:
        sql = '''INSERT INTO PALogs 
        (paID, league, season, session, gameID, inning, inningID, playNumber, outs, obc, awayScore, homeScore, pitcherTeam, pitcherName, pitcherID, hitterTeam, hitterName, hitterID, pitch, swing, diff, exactResult, oldResult, resultAtNeutral, resultAllNeutral, rbi, run, batterWPA, pitcherWPA, pr3B, pr2B, pr1B, prAB, pitch_requested, pitch_submitted, swing_reqested, swing_submitted)
         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
    db.update_database(sql, data)
    return


def remove_from_pa_log(pa_id):
    pa_logged = db.fetch_one('''SELECT * FROM PALogs WHERE paID=%s''', (pa_id,))
    if pa_logged:
        db.update_database('DELETE FROM PALogs WHERE paID=%s', (pa_id,))
    return


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

    return int(f'{str(season).zfill(2)}{str(session).zfill(2)}{str(game_id).zfill(3)}{str(play_number).zfill(3)}')


async def parse_pitch(ctx, message_id: int):
    pitch = await ctx.fetch_message(int(message_id))
    return int(re.sub(regex, '', pitch.content))


async def parse_pitch(bot, user_id: int, message_id: int):
    current_pitcher = bot.get_user(int(user_id))
    dm_channel = current_pitcher.dm_channel
    if not dm_channel:
        dm_channel = await current_pitcher.create_dm()
    pitch = await dm_channel.fetch_message(int(message_id))
    return int(re.sub(regex, '', pitch.content))


async def post_at_bat(bot, league, season, session, game_id):
    sheet_id, thread_url = db.fetch_one(
        'SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s',
        (league, season, session, game_id))
    current_batter = db.fetch_one(
        'SELECT current_batter FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s',
        (league, season, session, game_id))
    if current_batter:
        current_batter = db.fetch_one('SELECT discordID FROM playerData WHERE playerID=%s', (current_batter[0],))
        reddit_ping = sheets.read_sheet(sheet_id, assets.calc_cell2['reddit_ping'])
        discord_ping = sheets.read_sheet(sheet_id, assets.calc_cell2['discord_ping'])
        reddit_ab_ping = ''
        discord_ab_ping = ''
        for line in reddit_ping:
            if len(line) > 0:
                reddit_ab_ping += f'   {line[0]}\r\n\r\n'
        for line in discord_ping:
            if len(line) > 0:
                discord_ab_ping += f'{line[0]}\n'
        ab_ping = await reddit.post_comment(thread_url, reddit_ab_ping)
        swing_submitted = datetime.datetime.utcfromtimestamp(ab_ping.created_utc)
        db.update_database(
            'UPDATE pitchData SET swing_requested=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s',
            (swing_submitted, league, season, session, game_id))
        discord_ab_ping += f'\n{bot.get_user(current_batter[0]).mention} is up to bat! No need to ping your umps when you swing, we have bots for that. <https://www.reddit.com{ab_ping.permalink}>'
        ab_ping_channel = int(read_config(league_config, league, 'ab_pings'))
        channel = bot.get_channel(ab_ping_channel)
        await channel.send(discord_ab_ping)
    return


async def post_thread(sheet_id, league, season, session, away_team, home_team, flavor_text):
    thread_title = f'[{league.upper()} {season}.{session}] {away_team} vs {home_team}'
    if flavor_text:
        thread_title += f' - {flavor_text}'
    body = get_box_score(sheet_id)
    subreddit_name = read_config(config_ini, 'Reddit', 'subreddit_name')
    thread = await reddit.post_thread(subreddit_name, thread_title, body)
    log_msg(f'Created game thread: <{thread.url}>')
    return thread


def read_config(filename, section, setting):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    return ini_file[section][setting]


async def result(bot, league, season, session, game_id):
    sql = '''SELECT current_pitcher, current_batter, pitch_src, swing_src, steal_src, pitch_requested, pitch_submitted, swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
    current_pitcher, current_batter, pitch_src, swing_src, steal_src, pitch_requested, pitch_submitted, swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes = db.fetch_one(
        sql, (league, season, session, game_id))
    sheet_id, game_thread, away_team, home_team, away_score, home_score, inning, outs, obc = db.fetch_one(
        '''SELECT sheetID, threadURL, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
        (league, season, session, game_id))
    event = sheets.read_sheet(sheet_id, assets.calc_cell2['event'])[0][0]
    reddit_comment = ''
    ump_hq = read_config(config_ini, 'Channels', 'ump_hq')
    ump_hq = bot.get_channel(int(ump_hq))

    # Get the right team logo and color for embeds
    sql = '''SELECT color, logo_url FROM teamData WHERE abb=%s'''
    if 'T' in inning:
        color, logo_url = db.fetch_one(sql, (away_team,))
    else:
        color, logo_url = db.fetch_one(sql, (home_team,))

    # Have someone check if the conditional sub should be used instead
    if conditional_swing_requested:
        conditional_batter_name, conditional_batter_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (conditional_batter,))
        current_batter_discord = bot.get_user(int(conditional_batter_discord))
        conditional_batter_dm_channel = await current_batter_discord.create_dm()
        conditional_swing_src = await conditional_batter_dm_channel.fetch_message(int(conditional_swing_src))

        title = 'Conditional Swing Check'
        description = 'The swing is in, but a conditional sub is in place. Please check if the conditions for the sub applied BEFORE the swing came in.\n\nIf it does, please put the sub in the ump sheet before proceeding.'

        embed = discord.Embed(title=title, description=description, colour=discord.Color(value=int(color, 16)))
        embed.set_author(name=f'[{league.upper()} {season}.{session}.{game_id}] {away_team} @ {home_team}', icon_url=logo_url)
        embed.add_field(name='Conditional Batter', value=conditional_batter_name, inline=True)
        embed.add_field(name='Conditional Batter ID', value=conditional_batter, inline=True)
        embed.add_field(name='Condition', value=conditional_swing_notes, inline=True)
        embed.add_field(name='Conditional Time Requested', value=conditional_swing_requested, inline=True)
        embed.add_field(name='ConditionalTime Submitted', value=conditional_swing_src.created_at, inline=True)
        embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})')
        embed.add_field(name='Reddit Thread', value=f'[Link]({game_thread})', inline=True)
        await ump_hq.send(embed=embed, view=auto_buttons(bot, embed, league, season, session, game_id))
        set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')

    else:
        # Actually result the AB if there's no conditional sub
        log_msg(f'Resulting AB for {league.upper()} {season}.{session}.{game_id} - {away_team} @ {home_team}...')

        # If it's a steal and there is a steal number, then use the steal number instead.
        if 'STEAL' in event:
            if steal_src:
                pitch_src = steal_src

        # If there's no AB ping, post the entire AB with result as one top level comment.
        if event == 'IBB' or swing_src.isnumeric():
            reddit_starter = sheets.read_sheet(sheet_id, assets.calc_cell2['reddit_ping'])
            for line in reddit_starter:
                if len(line) > 0:
                    reddit_comment += f'{line[0]}  \n'
        pitcher_name, pitcher_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (current_pitcher,))
        batter_name, batter_discord = db.fetch_one('SELECT playerName, discordID FROM playerData WHERE playerID=%s', (current_batter,))
        current_pitcher = bot.get_user(int(pitcher_discord))
        dm_channel = await current_pitcher.create_dm()
        swing_number = None
        pitch_number = None
        if not event == 'IBB':
            try:
                pitch_src = await dm_channel.fetch_message(int(pitch_src))
            except Exception as e:
                print(e)
                edit_warning(bot, league, season, session, game_id)
            if pitch_src.edited_at:
                edit_warning(bot, league, season, session, game_id)
                return None
            else:
                pitch_number = int(re.sub(regex, '', pitch_src.content))

            # Get swing from Discord DMs if applicable

            if swing_src.isnumeric():
                swing_number = await parse_pitch(bot, batter_discord, swing_src)
            else:
                swing_comment = await reddit.get_comment_url(swing_src)
                if swing_comment.edited:
                    edit_warning(bot, league, season, session, game_id)
                    return None
                swing_number = await get_swing_from_reddit_async(f'https://www.reddit.com{swing_comment.permalink}')

            # Write pitch and swing to ump sheets
            set_swing_pitch(sheet_id, swing_number, pitch_number)

        # Get new game state from sheet
        result_data = sheets.read_sheet(sheet_id, assets.calc_cell2['result'])
        after_swing = sheets.read_sheet(sheet_id, assets.calc_cell2['after_swing'])
        diff, result_type, rbi, run = result_data[0]
        inning_after, outs_after, obc_after, home_score_after, away_score_after = after_swing[0]

        # Send the result to the pitcher's DMs
        pitcher_result = f'{batter_name} batting against {pitcher_name}\n'
        pitcher_result += f'{assets.obc_state[obc]} | {inning} with {outs} out(s)\n\n'
        pitcher_result += f'Pitch: {pitch_number}\nSwing: {swing_number}\nDiff: {diff} -> {result_type}\n\n'
        pitcher_result += f'{assets.obc_state[int(obc_after)]} | {inning_after} with {outs_after} out(s)\n'
        pitcher_result += f'{away_team.upper()} {away_score_after} - {home_team.upper()} {home_score_after}'
        await dm_channel.send(f'```{pitcher_result}```')

        # Generate reddit comment
        reddit_comment += f'{flavor.generate_flavor_text(result_type, batter_name)}\n\n'
        reddit_comment += f'Pitch: {pitch_number}  \nSwing: {swing_number}  \nDiff: {diff} -> {result_type}  \n\n'
        reddit_comment += f'{assets.obc_state[int(obc_after)]} | {inning_after} with {outs_after} out(s)  \n'
        reddit_comment += f'{away_team.upper()} {away_score_after} - {home_team.upper()} {home_score_after}'

        # Reply with a top level comment if its a swing via DM or an IBB, otherwise reply to swing
        if swing_src:
            if not swing_src.isnumeric():
                await swing_comment.reply(reddit_comment)
        else:
            await reddit.post_comment(game_thread, reddit_comment)

        # Log the result in the database
        if 'T' in inning:
            batter_team = away_team
            pitcher_team = home_team
        else:
            batter_team = home_team
            pitcher_team = away_team

        log_result(sheet_id, league, season, session, game_id, inning, outs, obc, away_score, home_score,
                   pitcher_team, pitcher_name, current_pitcher, batter_name, batter_team, current_batter,
                   pitch_number, swing_number, diff, result_type, rbi, run,
                   pitch_requested, pitch_submitted, swing_requested, swing_submitted)

        # Send result embeds
        result_embed = discord.Embed(description=pitcher_result, colour=discord.Color(value=int(color, 16)))
        result_embed.set_author(name=f'{league} {season}.{session} - {away_team.upper()} @ {home_team.upper()}', url=game_thread, icon_url=logo_url)
        result_embed.set_thumbnail(url=assets.obc_img[obc_after])
        result_embed.add_field(name='View on Reddit', value=f'[Link]({game_thread})')

        batter_team_data = db.fetch_one('SELECT webhook_url, role_id FROM teamData WHERE abb=%s', (batter_team,))
        pitcher_team_data = db.fetch_one('SELECT webhook_url, role_id FROM teamData WHERE abb=%s', (pitcher_team,))

        if batter_team_data[0]:
            hook = Webhook(batter_team_data[0])
            hook.send(embed=result_embed)
        if pitcher_team_data[0]:
            hook = Webhook(pitcher_team_data[0])
            hook.send(embed=result_embed)

        # Send hype pings
        if rbi != '0' or int(diff) == 500 or result_type == 'TP':
            channel = bot.get_channel(int(read_config(league_config, league.upper(), 'game_discussion')))
            if rbi != '0':
                await channel.send(content=f'<@&{batter_team_data[1]}>', embed=result_embed)
            elif diff == 500 or result_type == 'TP':
                await channel.send(content=f'<@&{pitcher_team_data[1]}>', embed=result_embed)

        # Commit AB to game log and reset the front end calc and then update the box score on reddit
        commit_at_bat(sheet_id)
        await reddit.edit_thread(game_thread, get_box_score(sheet_id))

        # Update gameData with new game state and remove AB data from pitchData
        sql = '''UPDATE gameData SET awayScore=%s, homeScore=%s, inning=%s, outs=%s, obc=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
        db.update_database(sql, (away_score_after, home_score_after, inning_after, outs_after, obc_after, league, season, session, game_id))
        sql = '''UPDATE pitchData SET pitch_requested=%s, pitch_submitted=%s, pitch_src=%s, steal_src=%s, swing_requested=%s, swing_submitted=%s, swing_src=%s, conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s, conditional_pitch_notes=%s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, league, season, session, game_id))

        # Set next pitcher and batter in the database
        next_matchup = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])[0]
        sql = '''UPDATE pitchData SET current_batter=%s, current_pitcher=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (next_matchup[0], next_matchup[3], league, season, session, game_id))

        # Set state to "WAITING FOR PITCH"
        set_state(league, season, session, game_id, 'WAITING FOR PITCH')


def get_game_discussion(bot, league):
    return bot.get_channel(int(read_config(league_config, league.upper(), 'game_discussion')))


def set_event(sheet_id: str, event_type: str):
    sheets.update_sheet(sheet_id, assets.calc_cell2['event'], event_type)
    return sheets.read_sheet(sheet_id, assets.calc_cell2['event'])[0][0]


def set_swing_pitch(sheet_id, swing: int, pitch: int):
    sheets.update_sheet(sheet_id, assets.calc_cell2['swing'], swing)
    sheets.update_sheet(sheet_id, assets.calc_cell2['pitch'], pitch)
    return


def set_state(league, season, session, game_id, state):
    db.update_database('''UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
                       (state, league, season, session, game_id))
    log_msg(f'{datetime.datetime.utcnow()} - {league.upper()} {season}.{session}.{game_id} state changed to {state}')


async def starting_lineup(league, season, session, game_id):
    sheet_id = db.fetch_one(
        '''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
        (league, season, session, game_id))
    if sheet_id:
        sheet_id = sheet_id[0]
        home_lineup = sheets.read_sheet(sheet_id, assets.calc_cell['home_lineup'])
        away_lineup = sheets.read_sheet(sheet_id, assets.calc_cell['away_lineup'])
        sql_insert = 'INSERT IGNORE INTO lineups (league, season, session, game_id, player_id, position, batting_order, home, starter) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) '
        for i in range(len(home_lineup)):
            player = home_lineup[i]
            if player:
                player_id = get_player_id(player[0])
                data = (league, season, session, game_id, player_id, player[1], i + 1, 1, 1)
                check = db.fetch_one(
                    'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                    data)
                if not check:
                    db.update_database(sql_insert, data)
        for i in range(len(away_lineup)):
            player = away_lineup[i]
            if player:
                player_id = get_player_id(player[0])
                data = (league, season, session, game_id, player_id, player[1], i + 1, 0, 1)
                check = db.fetch_one(
                    'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                    data)
                if not check:
                    db.update_database(sql_insert, data)


async def subs(league, season, session, game_id):
    sheet_id = db.fetch_one(
        '''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''',
        (league, season, session, game_id))
    if sheet_id:
        sheet_id = sheet_id[0]
        away_subs = sheets.read_sheet(sheet_id, assets.calc_cell['away_subs'])
        home_subs = sheets.read_sheet(sheet_id, assets.calc_cell['home_subs'])
        away_position_changes = sheets.read_sheet(sheet_id, assets.calc_cell['away_position_changes'])
        home_position_changes = sheets.read_sheet(sheet_id, assets.calc_cell['home_position_changes'])
        sql_insert = 'INSERT IGNORE INTO lineups (league, season, session, game_id, player_id, position, batting_order, home, starter) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) '
        for sub in away_subs:
            player_out, player_in, position = sub
            player_out = get_player_id(player_out)
            player_in = get_player_id(player_in)
            batting_order = db.fetch_data(
                '''SELECT batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''',
                (league, season, session, game_id, player_out, False))
            if batting_order:
                batting_order = batting_order[-1][0]
            data = (league, season, session, game_id, player_in, position, batting_order, 0, 0)
            check = db.fetch_one(
                'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                data)
            if not check:
                db.update_database(sql_insert, data)
        for sub in home_subs:
            player_out, player_in, position = sub
            player_out = db.fetch_one('''SELECT playerID FROM playerData WHERE playerName=%s''', (player_out,))[0]
            player_in = db.fetch_one('''SELECT playerID FROM playerData WHERE playerName=%s''', (player_in,))[0]
            batting_order = db.fetch_data(
                '''SELECT batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''',
                (league, season, session, game_id, player_out, True))
            if batting_order:
                batting_order = batting_order[-1][0]
            data = (league, season, session, game_id, player_in, position, batting_order, 1, 0)
            check = db.fetch_one(
                'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                data)
            if not check:
                db.update_database(sql_insert, data)
        for sub in away_position_changes:
            player, old_pos, new_pos = sub
            player = get_player_id(player)
            data = db.fetch_data(
                '''SELECT position, batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''',
                (league, season, session, game_id, player, False))
            if data:
                position, batting_order = data[-1]
            data = (league, season, session, game_id, player, new_pos, batting_order, 0, 0)
            check = db.fetch_one(
                'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                data)
            if not check:
                db.update_database(sql_insert, data)
        for sub in home_position_changes:
            player, old_pos, new_pos = sub
            player = get_player_id(player)
            data = db.fetch_data(
                '''SELECT position, batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''',
                (league, season, session, game_id, player, True))
            if data:
                position, batting_order = data[-1]
            data = (league, season, session, game_id, player, new_pos, batting_order, 1, 0)
            check = db.fetch_one(
                'SELECT league, season, session, game_id, player_id, position, batting_order, home, starter FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND position=%s AND batting_order=%s AND home=%s AND starter=%s',
                data)
            if not check:
                db.update_database(sql_insert, data)
        print('done')


def time_to_pitch(league, season, session, game_id):
    sql = '''SELECT pitch_requested, pitch_submitted FROM pitchData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
    pitch_requested, pitch_submitted = db.fetch_one(sql, (league, season, session, game_id))
    if pitch_requested and pitch_submitted:
        return pitch_submitted - pitch_requested
    return None


def time_to_swing(league, season, session, game_id):
    sql = '''SELECT swing_requested, swing_submitted FROM pitchData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
    swing_requested, swing_submitted = db.fetch_one(sql, (league, season, session, game_id))
    if swing_requested and swing_submitted:
        return swing_requested - swing_submitted
    return None


def write_config(filename, section, setting, value):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    ini_file.set(section, setting, value)
    with open(filename, 'w') as configfile:
        ini_file.write(configfile)


def auto_buttons(bot, embed, league, season, session, game_id):
    conditional_batter_id = None
    conditional_batter_name = None
    conditional_swing_requested = None
    conditional_swing_submitted = None
    conditional_swing_src = None
    conditional_pitcher_id = None
    conditional_pitch_requested = None
    conditional_pitch_submitted = None
    conditional_pitch_src = None

    for field in embed.fields:
        if field.name == 'Ump Sheet':
            sheet_id = field.value[46:-1]
        if field.name == 'Conditional Batter ID':
            conditional_batter_id = field.value
        if field.name == 'Conditional Time Requested':
            conditional_swing_requested = field.value
        if field.name == 'Conditional Time Submitted':
            conditional_swing_submitted = field.value
        if field.name == 'Conditional Pitcher ID':
            conditional_batter_id = field.value
        if field.name == 'Conditional Pitcher ID':
            conditional_pitcher_id = field.value
        if field.name == 'Conditional Pitch Requested':
            conditional_pitch_requested = field.value
        if field.name == 'Conditional Pitch Submitted':
            conditional_pitch_submitted = field.value
        if field.name == 'Conditional Pitcher ID':
            conditional_pitcher_id = field.value

    auto_k = Button(label="Confirm Auto", style=discord.ButtonStyle.red)
    auto_bb = Button(label="Confirm Auto", style=discord.ButtonStyle.red)
    original_swing = Button(label="Use Original Swing", style=discord.ButtonStyle.green)
    original_pitch = Button(label="Use Original Pitch", style=discord.ButtonStyle.green)
    conditional_swing = Button(label="Use Conditional Sub", style=discord.ButtonStyle.red)
    conditional_pitch = Button(label="Use Conditional Sub", style=discord.ButtonStyle.red)
    no_auto = Button(label="No Auto", style=discord.ButtonStyle.green)

    async def auto_k_callback(interaction):
        set_event(sheet_id, 'AUTO K')
        set_state(league, season, session, game_id, 'WAITING FOR RESULT')
        await interaction.response.edit_message(view=None, embed=embed)
        await interaction.followup.send(content='Auto K processed.')

    async def auto_bb_callback(interaction):
        set_event(sheet_id, 'AUTO BB')
        set_state(league, season, session, game_id, 'WAITING FOR RESULT')
        await interaction.response.edit_message(view=None, embed=embed)
        await interaction.followup.send(content='Auto BB processed.')

    async def use_conditional_pitch_callback(interaction):
        matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
        if matchup_info[0][3] == conditional_batter_id:
            sql = 'UPDATE pitchData SET current_pitcher=%s, pitch_requested=%s, pitch_submitted=%s, conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'
            db.update_database(sql, (conditional_pitcher_id, conditional_pitch_requested, conditional_pitch_submitted, None, None, None, league, season, session, game_id))
            set_state(league, season, session, game_id, 'WAITING FOR SWING')
            await interaction.response.edit_message(view=None, embed=embed, content=None)
            await interaction.followup.send(content='Using conditional pitch.')
        else:
            await interaction.response.edit_message(content='Pitcher has not been updated on the ump helper sheet!!')
        return

    async def use_conditional_swing_callback(interaction):
        matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
        if matchup_info[0][0] == conditional_batter_id:
            sql = 'UPDATE pitchData SET current_batter=%s, swing_requested=%s, swing_submitted=%s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'
            db.update_database(sql, (conditional_batter_id, conditional_swing_requested, conditional_swing_submitted, None, None, None, league, season, session, game_id))
            current_pitcher = db.fetch_one('SELECT current_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
            await interaction.response.edit_message(view=None, embed=embed, content=None)
            await interaction.followup.send(content='Using conditional pitch.')
            current_pitcher_discord, keep_pitch = db.fetch_one('SELECT discordID, keep_pitch FROM playerData WHERE playerID=%s', current_pitcher)
            if keep_pitch:
                set_state(league, season, session, game_id, 'WAITING FOR RESULT')
            else:
                prompt = f'A sub has been requested. To keep your pitch, use `.keep_pitch`. To change your pitch use `.pitch ###`.'
                current_pitcher = bot.get_user(int(current_pitcher_discord))
                dm_channel = await current_pitcher.create_dm()
                if keep_pitch:
                    set_state(league, season, session, game_id, 'WAITING FOR RESULT')
                else:
                    await dm_channel.send(prompt)
                    set_state(league, season, session, game_id, 'WAITING FOR PITCH CONFIRMATION')
        else:
            await interaction.response.edit_message(content='Pitcher has not been updated on the ump helper sheet!!')
        return

    async def use_original_pitch_callback(interaction):
        set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        await interaction.response.edit_message(content='Conditional sub does not apply. Using original pitch.', view=None)
        return

    async def use_original_swing_callback(interaction):
        set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
        await interaction.response.edit_message(content='Conditional sub does not apply. Using original swing.', view=None)
        return

    async def no_auto_callback(interaction):
        await interaction.response.edit_message(view=None, embed=embed)
        await interaction.followup.send(content='Auto request rejected.')

    view = View(timeout=None)

    if 'Auto K' in embed.title:
        auto_k.callback = auto_k_callback
        conditional_swing.callback = use_conditional_swing_callback
        no_auto.callback = no_auto_callback
        view.add_item(conditional_swing)
        view.add_item(auto_k)
        view.add_item(no_auto)
    elif 'Auto BB' in embed.title:
        auto_bb.callback = auto_bb_callback
        conditional_pitch.callback = use_conditional_pitch_callback
        no_auto.callback = no_auto_callback
        view.add_item(conditional_pitch)
        view.add_item(auto_bb)
        view.add_item(no_auto)
    elif 'Conditional Pitch' in embed.title:
        original_pitch.callback = use_original_pitch_callback
        conditional_pitch.callback = use_conditional_pitch_callback
        view.add_item(original_pitch)
        view.add_item(conditional_pitch)
    elif 'Conditional Swing' in embed.title:
        original_swing.callback = use_original_swing_callback
        conditional_swing.callback = use_conditional_swing_callback
        view.add_item(original_swing)
        view.add_item(conditional_swing)

    return view


def umpdate_buttons(sheet_id, embed, league, season, session, game_id):
    ump_sheet = Button(label="Ump Sheet", style=discord.ButtonStyle.link, url=f'https://docs.google.com/spreadsheets/d/{sheet_id}')
    submit = Button(label="Umpdate", style=discord.ButtonStyle.blurple)

    async def submit_callback(interaction):
        for field in embed.fields:
            if field.name == 'State':
                set_state(league, season, session, game_id, field.value)
                continue
        await interaction.response.edit_message(content='Sub processed.', view=None, embed=embed)
        return

    submit.callback = submit_callback
    view = View(timeout=None)
    view.add_item(ump_sheet)
    view.add_item(submit)
    return view
