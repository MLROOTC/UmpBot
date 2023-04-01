import configparser
import random
import re

import src.db_controller as db
import src.assets as assets
import src.sheets_reader as sheets
import src.Ump.robo_ump as robo_ump

config_ini = 'config.ini'


def generate_flavor_text(league, season, session, game_id, text, runs):
    sql = '''SELECT current_batter, current_pitcher FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
    current_batter, current_pitcher = db.fetch_one(sql, (league, season, session, game_id))
    sql = '''SELECT homeTeam, awayTeam, homeScore, awayScore, inning, outs, obc FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
    home_team, away_team, home_score, away_score, inning, outs, obc = db.fetch_one(sql, (league, season, session, game_id))

    if 'B' in inning:
        batter_gm, = db.fetch_one('''SELECT gm FROM teamData WHERE abb=%s''', (home_team,))
        pitcher_gm, = db.fetch_one('''SELECT gm FROM teamData WHERE abb=%s''', (away_team,))
        batter_score = home_score
        pitcher_score = away_score
        batter_team = home_team
        pitcher_team = away_team
        current_positions = get_current_lineup(league, season, session, game_id, True)
    else:
        batter_gm, = db.fetch_one('''SELECT gm FROM teamData WHERE abb=%s''', (away_team,))
        pitcher_gm, = db.fetch_one('''SELECT gm FROM teamData WHERE abb=%s''', (home_team,))
        batter_score = away_score
        pitcher_score = home_score
        batter_team = away_team
        pitcher_team = home_team
        current_positions = get_current_lineup(league, season, session, game_id, False)

    if '[BATTER]' in text.upper():
        text = text.replace('[BATTER]', get_last_name(get_player_name(current_batter)))
    if '[BATTER_FULL_NAME]' in text.upper():
        text = text.replace('[BATTER_FULL_NAME]', get_player_name(current_batter))
    if '[PITCHER]' in text.upper():
        text = text.replace('[PITCHER]', get_last_name(get_player_name(current_pitcher)))
    if '[PITCHER_FULL_NAME]' in text.upper():
        text = text.replace('[PITCHER_FULL_NAME]', get_player_name(current_pitcher))
    if '[HT_CITY]' in text.upper():
        text = text.replace('[HT_CITY]', assets.team_cities.get(home_team))
    if '[AT_CITY]' in text.upper():
        text = text.replace('[AT_CITY]', assets.team_cities.get(away_team))
    if '[HT_NICKNAME]' in text.upper():
        text = text.replace('[HT_NICKNAME]', assets.team_nicknames.get(home_team))
    if '[AT_NICKNAME]' in text.upper():
        text = text.replace('[AT_NICKNAME]', assets.team_nicknames.get(away_team))
    if '[BATTER_TEAM_CITY]' in text.upper():
        text = text.replace('[BATTER_TEAM_CITY]', assets.team_cities.get(batter_team))
    if '[PITCHER_TEAM_CITY]' in text.upper():
        text = text.replace('[PITCHER_TEAM_CITY]', assets.team_cities.get(pitcher_team))
    if '[BATTER_TEAM_NICKNAME]' in text.upper():
        text = text.replace('[BATTER_TEAM_NICKNAME]', assets.team_nicknames.get(batter_team))
    if '[PITCHER_TEAM_NICKNAME]' in text.upper():
        text = text.replace('[PITCHER_TEAM_NICKNAME]', assets.team_nicknames.get(pitcher_team))
    if '[BATTER_SCORE]' in text.upper():
        text = text.replace('[BATTER_SCORE]', f'{batter_score}')
    if '[PITCHER_SCORE]' in text.upper():
        text = text.replace('[PITCHER_SCORE]', f'{pitcher_score}')
    if '[RUNS]' in text.upper():
        text = text.replace('[RUNS]', f'{runs}')
    if '[RUN_DIFF]' in text.upper():
        text = text.replace('[RUN_DIFF]', f'{abs(batter_score - pitcher_score)}')
    if '[PARK]' in text.upper():
        text = text.replace('[PARK]', f'{get_park(home_team)}')
    if '[BATTER_GM]' in text.upper():
        text = text.replace('[BATTER_GM]', f'{get_last_name(batter_gm)}')
    if '[PITCHER_GM]' in text.upper():
        text = text.replace('[PITCHER_GM]', f'{get_last_name(pitcher_gm)}')
    if '[C]' in text.upper():
        text = text.replace('[C]', get_last_name(current_positions.get('C')))
    if '[1B]' in text.upper():
        text = text.replace('[1B]', get_last_name(current_positions.get('1B')))
    if '[2B]' in text.upper():
        text = text.replace('[2B]', get_last_name(current_positions.get('2B')))
    if '[3B]' in text.upper():
        text = text.replace('[3B]', get_last_name(current_positions.get('3B')))
    if '[SS]' in text.upper():
        text = text.replace('[SS]', get_last_name(current_positions.get('SS')))
    if '[LF]' in text.upper():
        text = text.replace('[LF]', get_last_name(current_positions.get('LF')))
    if '[CF]' in text.upper():
        text = text.replace('[CF]', get_last_name(current_positions.get('CF')))
    if '[RF]' in text.upper():
        text = text.replace('[RF]', get_last_name(current_positions.get('RF')))
    return text


def get_current_lineup(league, season, session, game_id, home):
    positions = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    current_positions = {}
    sql = '''SELECT player_id from lineups WHERE league=%s AND season=%s AND session=%s AND game_id=%s AND home=%s AND position=%s ORDER BY row_id DESC'''
    for position in positions:
        p = db.fetch_data(sql, (league, season, session, game_id, home, position))
        if len(p) >= 1:
            p = p[0]
        current_positions[position] = db.fetch_one('''SELECT playerName FROM playerData WHERE playerID=%s''', p)[0]
    return current_positions


def get_last_name(name):
    not_last_names = ['jr', 'ii', 'iii', 'iv', 'vi',  'xiv', 'cdxx', 'cccxxvii', 'lxix', 'esq', 'sr']
    name = name.split(' ')
    last_name = name[-1]
    if last_name.replace('.', '').lower() in not_last_names:
        new_name = name[:-1]
        last_name = get_last_name(' '.join(new_name))
    return last_name


def get_player_name(player_id):
    sql = '''SELECT playerName FROM playerData WHERE playerID=%s'''
    player_name, = db.fetch_one(sql, (player_id,))
    return player_name


def get_park(team):
    park_name, = db.fetch_one('''SELECT parkName FROM parkFactors WHERE team=%s''', (team,))
    return park_name


async def import_templates(ctx):
    sheet_id = robo_ump.read_config(config_ini, 'URLs', 'writeup_sheet_id')
    page_name = 'Templates'
    templates = sheets.read_sheet(sheet_id, page_name)
    for i in range(len(templates)):
        template = templates[i]
        if template[0] != 'Timestamp' and template[0] != '':
            play_type = template[2]
            properties = template[3]
            text = template[4]
            approved = template[5]
            validated = template[6]
            imported = template[7]
            if validated == 'FALSE':
                validated = await validate_text(ctx, text, i+1)

            if approved == 'TRUE' and imported == 'FALSE' and validated:
                run_scores = False
                walkoff = False
                game_tying = False
                go_ahead = False
                solo_hr = False
                if 'Run Scores' in properties:
                    run_scores = True
                if 'Walkoff' in properties:
                    walkoff = True
                if 'Game-tying' in properties:
                    game_tying = True
                if 'Go-ahead' in properties:
                    go_ahead = True
                if 'Solo HR' in properties:
                    solo_hr = True
                sql = '''INSERT INTO flavorText (result, text, run_scores, walkoff, game_tying, go_ahead, solo_hr) VALUES (%s, %s, %s, %s, %s, %s, %s)'''
                db.update_database(sql, (play_type, text, run_scores, walkoff, game_tying, go_ahead, solo_hr))
                sheets.update_sheet(sheet_id, f'{page_name}!H{i+1}', 'TRUE')
                robo_ump.log_msg(f'Added new writeup template: `[RESULT]{play_type} [RUN SCORES]{run_scores} [WALKOFF]{walkoff} [GAME-TYING]{game_tying} [GO-AHEAD]{go_ahead} [SOLO HR]{solo_hr}`\n```{text}```')
    return


def select_template(result_type, run_scores, walkoff, game_tying, go_ahead, solo_hr):
    sql = '''SELECT text FROM flavorText WHERE result=%s AND run_scores=%s AND walkoff=%s AND game_tying=%s AND go_ahead=%s AND solo_hr=%s ORDER BY RAND() LIMIT 1'''
    text = db.fetch_one(sql, (result_type, run_scores, walkoff, game_tying, go_ahead, solo_hr))
    if text:
        return text[0]
    return random.choice(assets.writeup_fails)


async def validate_text(ctx, text, row):
    sheet_id = robo_ump.read_config(config_ini, 'URLs', 'writeup_sheet_id')
    page_name = 'Templates'
    placeholders = re.findall(r'\[.*?\]', text)
    for var in placeholders:
        if var not in assets.writeup_placeholders:
            sheets.update_sheet(sheet_id, f'{page_name}!G{row}', 'FALSE')
            await ctx.send(f'**Invalid writeup on row {row}.** Found term **{var}** in text:\n ```{text}```')
            return False
    sheets.update_sheet(sheet_id, f'{page_name}!G{row}', 'TRUE')
    return True
