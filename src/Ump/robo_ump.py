import configparser
import datetime

from dhooks import Webhook
import re
import src.assets as assets
import src.db_controller as db
import src.reddit_interface as reddit
import src.sheets_reader as sheets


config_ini = configparser.ConfigParser()
config_ini = 'config.ini'
league_config = 'league.ini'
master_ump_sheet = "1DTcSKkfpIn3_zRGY2_jdEGt3mSGT2nC2y1aJoXe--Rk"
regex = "[^0-9]"
lineup_string = "That\'s a good lineup!"


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
            game_check = db.fetch_one('SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND awayTeam=%s AND homeTeam=%s', (league, season, session, away_team, home_team))
            if not game_check:
                # Create Copy of Ump Sheet
                file_id = read_config(league_config, league.upper(), 'sheet')
                sheet_title = f'{league.upper()} {season}.{session} - {away_team} vs {home_team}'
                sheet_id = sheets.copy_ump_sheet(file_id, sheet_title)
                sheets.update_sheet(sheet_id, assets.calc_cell2['away_team'], away_name)
                sheets.update_sheet(sheet_id, assets.calc_cell2['home_team'], home_name)
                log_msg(f'Created ump sheet {league.upper()} {season}.{session} - {away_team}@{home_team}: <https://docs.google.com/spreadsheets/d/{sheet_id}>')

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
            if active_games[game_number-1][4] == pitcher_id[0]:
                return active_games[game_number-1][0:4], 'home'
            elif active_games[game_number-1][5] == pitcher_id[0]:
                return active_games[game_number-1][0:4], 'away'
            else:
                await ctx.send('Are you even pitching right now??')
    else:
        await ctx.send("I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


async def fetch_game_swing(ctx, bot):
    batter_id = db.fetch_one('''SELECT playerID FROM playerData WHERE discordID=%s''', (ctx.author.id,))
    if batter_id:
        active_games = db.fetch_data('''SELECT league, season, session, game_id, current_batter FROM pitchData WHERE current_batter=%s''', (batter_id[0],))
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
                game_data = db.fetch_one('''SELECT awayTeam, homeTeam, inning, outs FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', game[0:4])
                prompt += f'{i+1}. {game[0]:4} {game[1]}.{game[2]} - {game_data[0]} @ {game_data[1]} | {game_data[2]} {game_data[3]} Out(s)\n'
            prompt += '```'
            await ctx.send(prompt)

            def wait_for_response(msg):
                return msg.content.isnumeric() and 0 < int(msg.content) <= len(active_games)

            game_number = await bot.wait_for('message', check=wait_for_response)
            game_number = int(game_number.content)
            if active_games[game_number-1][4] == batter_id[0]:
                return active_games[game_number-1][0:4]
            elif active_games[game_number-1][5] == batter_id[0]:
                return active_games[game_number-1][0:4]
            else:
                await ctx.send('Are you even pitching right now??')
    else:
        await ctx.send("I couldn't find a player linked to your Discord account. Please use `.claim <playername>` to link your account.")
        return None


def fetch_game_team(team, season, session):
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


def get_active_games():
    sql = '''SELECT league, season, session, gameID, state FROM gameData WHERE complete=%s'''
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
    if discord_id:
        pitcher = bot.get_user(discord_id)
        pitch_request_msg = await pitcher.send(f'Pitch time! Please submit a pitch using `.pitch ###` or create a list using `.queue_pitch ###`.')
        db.update_database('''UPDATE pitchData SET pitch_requested=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (pitch_request_msg.created_at, league, season, session, game_id))
    else:
        print('Im not supporting reddit only pitchers')
    return


async def get_player(ctx, name):
    sql = '''SELECT * from playerData WHERE playerName LIKE %s'''
    players = db.fetch_data(sql, ('%'+name+'%',))
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
    sheet_id = db.fetch_one('''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (league, season, session, game_id))
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
            league, season, session, game_id, sheet_id = db.fetch_one('SELECT league, season, session, gameID, sheetID FROM gameData WHERE threadURL=%s', (parent_thread.url,))

            # Check for steal/bunt/etc
            check_for_event(sheet_id, swing_comment)

            # Write swing src, swing submitted to database
            swing_submitted = datetime.datetime.utcfromtimestamp(swing_comment.created_utc)
            sql = '''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            db.update_database(sql, (swing_comment.id, swing_submitted, league, season, session, game_id))
            set_state(league, season, session, game_id, 'WAITING FOR RESULT')
            # Set state to waiting for result
            return swing

    elif len(numbers_in_comment) == 0:
        swing_comment.reply("I couldn't find a valid number in your swing. Please reply to the original at-bat ping with a number between 1 and 1000 without any decimal spaces.")
        return None
    else:
        swing_comment.reply('I found too many numbers in your swing. Please reply to the original AB ping with only one number included in your swing.')
        return None


def check_for_event(sheet_id, swing_comment):
    if 'STEAL 2B' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL 2B')
    elif 'STEAL 3B' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL 3B')
    elif 'STEAL HOME' in swing_comment.body.upper():
        set_event(sheet_id, 'STEAL HOME')
    elif 'MULTISTEAL 3B' in swing_comment.body.upper():
        set_event(sheet_id, 'MULTISTEAL 3B')
    elif 'MULTISTEAL HOME' in swing_comment.body.upper():
        set_event(sheet_id, 'MULTISTEAL HOME')
    elif 'BUNT' in swing_comment.body.upper():
        set_event(sheet_id, 'BUNT')


def log_msg(message: str):
    hook = Webhook(read_config(config_ini, 'Channels', 'error_log_webhook'))
    hook.send(message)
    return


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
    sheet_id, thread_url = db.fetch_one('SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
    current_batter = db.fetch_one('SELECT current_batter FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
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
        db.update_database('UPDATE pitchData SET swing_requested=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (swing_submitted, league, season, session, game_id))
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
    sql = '''SELECT current_pitcher, current_batter, pitch_src, swing_src, steal_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
    current_pitcher, current_batter, pitch_src, swing_src, steal_src = db.fetch_one(sql, (league, season, session, game_id))
    sheet_id, game_thread = db.fetch_one('''SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (league, season, session, game_id))
    event = sheets.read_sheet(sheet_id, assets.calc_cell2['event'])[0][0]
    if pitch_src and swing_src:
        current_pitcher = db.fetch_one('''SELECT discordID FROM playerData WHERE playerID=%s''', (current_pitcher,))
        if 'STEAL' in event.upper():
            pitch = await parse_pitch(bot, int(current_pitcher[0]), int(steal_src))
        elif event == 'Swing':
            pitch = await parse_pitch(bot, int(current_pitcher[0]), int(pitch_src))
        if swing_src.isnumeric():  # Discord DM Swing
            current_batter = db.fetch_one('''SELECT discordID FROM playerData WHERE playerID=%s''', (current_batter,))
            swing = await parse_pitch(bot, int(current_batter[0]), int(swing_src))
        else:
            swing = get_swing_from_reddit(swing_src)
        set_swing_pitch(sheet_id, swing, pitch)
        return pitch
    else:
        return None


def set_event(sheet_id: str, event_type: str):
    sheets.update_sheet(sheet_id, assets.calc_cell2['event'], event_type)
    return sheets.read_sheet(sheet_id, assets.calc_cell2['event'])[0][0]


def set_swing_pitch(sheet_id, swing: int, pitch: int):
    sheets.update_sheet(sheet_id, assets.calc_cell2['swing_pitch'], [swing, pitch])
    return


def set_state(league, season, session, game_id, state):
    db.update_database('''UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (state, league, season, session, game_id))
    log_msg(f'{league.upper()} {season}.{session}.{game_id} state changed to {state}')


async def starting_lineup(league, season, session, game_id):
    sheet_id = db.fetch_one('''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (league, season, session, game_id))
    if sheet_id:
        sheet_id = sheet_id[0]
        home_lineup = sheets.read_sheet(sheet_id, assets.calc_cell['home_lineup'])
        away_lineup = sheets.read_sheet(sheet_id, assets.calc_cell['away_lineup'])
        sql_insert = 'INSERT IGNORE INTO lineups (league, season, session, game_id, player_id, position, batting_order, home, starter) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) '
        for i in range(len(home_lineup)):
            player = home_lineup[i]
            if player:
                player_id = get_player_id(player[0])
                data = (league, season, session, game_id, player_id, player[1], i+1, 1, 1)
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
    sheet_id = db.fetch_one('''SELECT sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (league, season, session, game_id))
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
            batting_order = db.fetch_data('''SELECT batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''', (league, season, session, game_id, player_out, False))
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
            batting_order = db.fetch_data('''SELECT batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''', (league, season, session, game_id, player_out, True))
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
            data = db.fetch_data('''SELECT position, batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''', (league, season, session, game_id, player, False))
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
            data = db.fetch_data('''SELECT position, batting_order FROM lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND player_id=%s AND home=%s''', (league, season, session, game_id, player, True))
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


