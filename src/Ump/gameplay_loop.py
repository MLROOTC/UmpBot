import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.reddit_interface as reddit


async def gameplay_loop(bot):
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        if state:
            await update_game(bot, league, season, session, game_id, state)
    return


async def update_game(bot, league, season, session, game_id, state):
    if state in ['WAITING FOR PITCH', 'WAITING FOR SWING', 'WAITING FOR RESULT']:
        current_batter, current_pitcher = db.fetch_one('''SELECT current_batter, current_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', (league, season, session, game_id))
        if not (current_pitcher and current_batter):
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
    elif state == 'SUB REQUESTED':
        print('SUB REQUESTED')
    elif state == 'AUTO REQUESTED':
        print('AUTO REQUESTED')
    elif state == 'CONFIRM PITCH':
        print('CONFIRM PITCH')
    elif state == 'FINALIZING':
        print('FINALIZING')
    elif state == 'COMPLETE':
        print('COMPLETE')
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
