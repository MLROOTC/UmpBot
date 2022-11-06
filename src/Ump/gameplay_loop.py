import src.db_controller as db
import src.Ump.robo_ump as robo_ump


async def gameplay_loop(bot):
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        if state:
            try:
                await update_game(bot, league, season, session, game_id, state)
            except Exception as e:
                away_team, home_team, sheet_id, thread_url = db.fetch_one('SELECT awayTeam, homeTeam, sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
                robo_ump.log_msg(f'<@330153321262219284> Ran into an issue with {league} {season}.{season}.{game_id} - {away_team} vs {home_team}\n<{thread_url}>\n<https://docs.google.com/spreadsheets/d/{sheet_id}>')
                robo_ump.set_state(league, season, session, game_id, 'PAUSED')
                print(e)
    return


async def update_game(bot, league, season, session, game_id, state):
    if state in ['WAITING FOR PITCH', 'WAITING FOR SWING', 'WAITING FOR RESULT']:
        current_batter, current_pitcher = db.fetch_one('''SELECT current_batter, current_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (league, season, session, game_id))
        if not (current_pitcher and current_batter):
            data = (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, league, season, session, game_id)
            db.update_database('UPDATE pitchData SET current_batter=%s, current_pitcher=%s, pitch_requested=%s, pitch_submitted=%s, pitch_src=%s, steal_src=%s, swing_requested=%s, swing_submitted=%s, swing_src=%s, conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_src=%s, conditional_pitch_notes=%s, conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_src=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', data)
            await robo_ump.update_matchup(league, season, session, game_id)
            return
    if state == 'WAITING FOR PITCH':
        sql = '''SELECT pitch_requested, pitch_submitted, pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        pitch_requested, pitch_submitted, pitch_src = db.fetch_one(sql, (league, season, session, game_id))
        if not pitch_requested:
            await robo_ump.get_pitch(bot, current_pitcher, league, season, session, game_id)
        elif pitch_requested and pitch_submitted:
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR SWING')
    elif state == 'WAITING FOR SWING':
        sql = '''SELECT current_batter, swing_requested, swing_submitted, swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        current_batter, swing_requested, swing_submitted, swing_src = db.fetch_one(sql, (league, season, session, game_id))
        if not swing_requested:
            await robo_ump.post_at_bat(bot, league, season, session, game_id)
        if swing_requested and swing_submitted:
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
    elif state == 'WAITING FOR RESULT':
        await robo_ump.result(bot, league, season, session, game_id)
    return


async def startup_loop(bot):
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        await prompt_for_conditionals(bot, league, season, session, game_id)
    return


async def prompt_for_conditionals(bot, league, season, session, game_id):
    sql = '''SELECT conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
    conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src = db.fetch_one(sql, (league, season, session, game_id))
    if conditional_swing_requested and not conditional_swing_src:
        conditional_batter_discord, = db.fetch_one('SELECT discordID FROM playerData WHERE playerID=%s', (conditional_batter,))
        conditional_batter_discord = bot.get_user(int(conditional_batter_discord))
        await conditional_batter_discord.send(f"I've been rebooted! If you previously replied with a swing I didn't catch it.  Please use `.submit_conditional_swing ###` to submit your swing.")
    if conditional_pitch_requested and not conditional_pitch_src:
        conditional_pitcher_discord, = db.fetch_one('SELECT discordID FROM playerData WHERE playerID=%s', (conditional_pitcher,))
        conditional_pitcher_discord = bot.get_user(int(conditional_pitcher_discord))
        await conditional_pitcher_discord.send(f"I've been rebooted! If you previously replied with a pitch I didn't catch it.  Please use `.submit_conditional_pitch ###` to submit your pitch.")
    return


def audit_all_games():
    mlr_season = robo_ump.read_config('league.ini', 'MLR', 'season')
    mlr_session = robo_ump.read_config('league.ini', 'MLR', 'session')
    milr_season = robo_ump.read_config('league.ini', 'MILR', 'season')
    milr_session = robo_ump.read_config('league.ini', 'MILR', 'session')
    mlr_games = db.fetch_data('SELECT sheetID, awayTeam FROM gameData WHERE season=%s AND session=%s AND complete=%s', (mlr_season, mlr_session, 0))
    milr_games = db.fetch_data('SELECT sheetID, awayTeam FROM gameData WHERE season=%s AND session=%s AND complete=%s', (milr_season, milr_session, 0))
    for game in mlr_games:
        sheet_id, team = game
        league, season, session, game_id = robo_ump.fetch_game_team(team, mlr_season, mlr_session)
        robo_ump.audit_game_log(league, season, session, game_id, sheet_id)
    for game in milr_games:
        sheet_id, team = game
        league, season, session, game_id = robo_ump.fetch_game_team(team, milr_season, milr_session)
        robo_ump.audit_game_log(league, season, session, game_id, sheet_id)