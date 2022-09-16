import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.reddit_interface as reddit


async def gameplay_loop(bot):
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        if state == 'WAITING FOR LINEUPS':
            sheet_id, thread_url = db.fetch_one('SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
            await reddit.edit_thread(thread_url, robo_ump.get_box_score(sheet_id))
        if state == 'WAITING FOR PITCH':
            sql = '''SELECT current_pitcher, pitch_requested, pitch_submitted, pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, pitch_requested, pitch_submitted, pitch_src = db.fetch_one(sql, (league, season, session, game_id))
            if not pitch_requested:
                await robo_ump.get_pitch(bot, current_pitcher, league, season, session, game_id)
            elif pitch_requested and pitch_submitted:
                robo_ump.set_state(league, season, session, game_id, 'WAITING FOR SWING')
        if state == 'WAITING FOR SWING':
            # TODO
            sql = '''SELECT current_batter, swing_requested, swing_submitted, swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_batter, swing_requested, swing_submitted, swing_src = db.fetch_one(sql, (league, season, session, game_id))
            if not swing_requested:
                await robo_ump.post_at_bat()
            if swing_requested and swing_submitted:
                robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
        if state == 'WAITING FOR RESULT':
            # TODO
            print('WAITING FOR RESULT')
        if state == 'SUB REQUESTED':
            # TODO
            print('SUB REQUESTED')
        if state == 'AUTO REQUESTED':
            # TODO
            print('AUTO REQUESTED')
        if state == 'CONFIRM PITCH':
            # TODO
            print('CONFIRM PITCH')
        if state == 'FINALIZING':
            # TODO
            print('FINALIZING')
        if state == 'COMPLETE':
            # TODO
            print('COMPLETE')
    return
