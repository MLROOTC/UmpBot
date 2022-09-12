import src.assets as assets
import src.db_controller as db
import src.reddit_interface as reddit
import src.sheets_reader as sheets
import re


regex = "[^0-9]"


async def get_pitch(bot, player_id, league, season, session, game_id):
    discord_id, reddit_name = db.fetch_one('''SELECT discordID, redditName FROM playerData WHERE playerID=%s''', (player_id,))
    if discord_id:
        def wait_for_pitch(msg):
            return msg.author == pitcher and msg.guild is None and msg.content.isnumeric() and int(
                msg.content) > 0 and int(msg.content) <= 1000

        pitcher = bot.get_user(discord_id)
        pitch_request_msg = await pitcher.send('Gib pitch')
        db.update_database('''UPDATE pitchData SET pitch_requested=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (pitch_request_msg.created_at, league, season, session, game_id))

        pitch_msg = await bot.wait_for('message', check=wait_for_pitch)
        sql = '''UPDATE pitchData SET pitch_src=%s, pitch_submitted=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
        db.update_database(sql, pitch_msg.id, pitch_msg.id, pitch_msg.created_at, league, season, session, game_id)
        await pitch_msg.add_reaction('👍')
    else:
        print('Im not supporting reddit only pitchers')
    return


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


async def get_swing_from_reddit(reddit_comment_url):
    swing_comment = await reddit.get_comment(reddit_comment_url)
    numbers_in_comment = [int(i) for i in swing_comment.body.split() if i.isdigit()]
    if len(numbers_in_comment) == 1:
        swing = numbers_in_comment[0]
        if 0 < swing <= 1000:
            await swing_comment.reply(f'Found a valid swing: {swing}')
    elif len(numbers_in_comment) == 0:
        await swing_comment.reply("I couldn't find a valid number in your swing. Please reply to the original at-bat ping with a number between 1 and 1000 without any decimal spaces.")
    else:
        await swing_comment.reply('I found too many numbers in your swing. Please reply to the original AB ping with only one number included in your swing.')
    return


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


async def parse_pitch(ctx, message_id: int):
    pitch = await ctx.fetch_message(int(message_id))
    return int(re.sub(regex, '', pitch.content))


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


def fetch_game_by_team(team, season, session):
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


def set_event(sheet_id: str, event_type: str):
    # TODO
    print(sheet_id, event_type)
    return
