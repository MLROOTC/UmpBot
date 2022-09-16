import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.reddit_interface as reddit


async def gameplay_loop(bot):
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        if state == 'SETUP':
            print('SETUP')
        if state == 'WAITING FOR LINEUPS':
            print('WAITING FOR LINEUPS')
            sheet_id, thread_url = db.fetch_one('SELECT sheetID, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
            await reddit.edit_thread(thread_url, robo_ump.get_box_score(sheet_id))
        if state == 'WAITING FOR PITCH':
            sql = '''SELECT current_pitcher, pitch_requested, pitch_submitted, pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, pitch_requested, pitch_submitted, pitch_src = db.fetch_one(sql, (league, season, session, game_id))
            if not pitch_requested:
                await robo_ump.get_pitch(bot, current_pitcher, league, season, session, game_id)
                print('request deprecated_pitch')
            elif pitch_requested and pitch_submitted:
                print('transition to waiting for swing')
            print('WAITING FOR PITCH')
        if state == 'WAITING FOR SWING':
            print('WAITING FOR SWING')
        if state == 'WAITING FOR RESULT':
            print('WAITING FOR RESULT')
        if state == 'SUB REQUESTED':
            print('SUB REQUESTED')
        if state == 'AUTO REQUESTED':
            print('AUTO REQUESTED')
        if state == 'CONFIRM PITCH':
            print('CONFIRM PITCH')
        if state == 'FINALIZING':
            print('FINALIZING')
        if state == 'COMPLETE':
            print('COMPLETE')
    return
