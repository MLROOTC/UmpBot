import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.sheets_reader as sheets


def gameplay_loop():
    active_games = robo_ump.get_active_games()
    for game in active_games:
        league, season, session, game_id, state = game
        if state == 'SETUP':
            print('SETUP')
        if state == 'WAITING FOR LINEUPS':
            print('WAITING FOR LINEUPS')
        if state == 'POST THREAD':
            print('POST THREAD')
        if state == 'WAITING FOR PITCH':
            print('WAITING FOR PITCH')
        if state == 'WAITING FOR SWING':
            print('WAITING FOR SWING')
        if state == 'WAITING FOR RESULT':
            print('WAITING FOR RESULT')
        if state == 'SUB REQUESTED':
            print('SUB REQUESTED')
        if state == 'AUTO REQUESTED':
            print('AUTO REQUESTED')
        if state == 'FINALIZING':
            print('FINALIZING')
        if state == 'COMPLETE':
            print('COMPLETE')
    return
