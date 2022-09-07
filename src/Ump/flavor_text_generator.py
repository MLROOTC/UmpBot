import src.db_controller as db


def generate_flavor_text(result_type, batter_name, fielding_positions):
    text = ''
    return text


def get_current_lineup(league, season, session, game_id, home):
    positions = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    current_positions = {}
    sql = '''SELECT player_id from lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND home=%s AND position=%s ORDER BY row_id DESC'''
    for position in positions:
        p = db.fetch_data(sql, (league, season, session, game_id, home, position))
        if len(p) > 1:
            p = p[0]
        else:
            p = p[0]
        current_positions[position] = db.fetch_one('''SELECT playerName FROM playerData WHERE playerID=%s''', p)[0]
    print(current_positions)
    return current_positions
