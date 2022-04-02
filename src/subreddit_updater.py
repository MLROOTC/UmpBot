import configparser
import datetime
import src.assets as assets
import src.db_controller as db
import src.reddit_interface as reddit
import src.sheets_reader as sheets

config = configparser.ConfigParser()
config.read('config.ini')
website_url = config['URLs']['website_url']
config.read('league.ini')


async def scoreboard():
    scoreboard_post_id = config['Subreddit']['scoreboard_post']
    scoreboard_post = await reddit.get_thread(scoreboard_post_id)
    mlr_sheet = config['MLR']['sheet']
    mlr_season = config['MLR']['season']
    mlr_session = config['MLR']['session']
    milr_sheet = config['MILR']['sheet']
    milr_season = config['MILR']['season']
    milr_session = config['MILR']['session']

    sql = '''SELECT awayTeam, awayScore, homeTeam, homeScore, inning, outs, obc, complete, threadURL FROM gameData WHERE league=%s AND season=%s AND session=%s ORDER BY awayTeam'''
    mlr_games = db.fetch_data(sql, ('mlr', mlr_season, mlr_session))
    milr_games = db.fetch_data(sql, ('milr', milr_season, milr_session))

    scoreboard_text = '#Scoreboard \n\n'
    scoreboard_text += f'##Season {mlr_season} - Session {mlr_session}\n\n'

    if mlr_games:
        scoreboard_text += f'**MLR Scoreboard**\n\n'
        scoreboard_text += f'|Away|Score|Home|Score|Game State|Game Thread|\n'
        scoreboard_text += f'|:--:|:---:|:--:|:---:|:---------|:----------|\n'
        for game in mlr_games:
            if game[0]:
                if game[7] == 0:
                    game_state = f'{assets.obc_icon[game[6]]} - {game[4]} {game[5]} out(s)'
                else:
                    game_state = 'Final'
                scoreboard_text += f'|[{game[0]}]({website_url}/team/{game[0]})|{game[1]}|[{game[2]}]({website_url}/team/{game[2]})|{game[3]}|{game_state}|[Link]({game[8]})|\r\n'
        scoreboard_text += '\r\n'
    if milr_games:
        scoreboard_text += f'**MiLR Scoreboard**\r\n\r\n'
        scoreboard_text += f'|Away|Score|Home|Score|Game State|Game Thread|\r\n'
        scoreboard_text += f'|:--:|:---:|:--:|:---:|:--------:|:---------:|\r\n'
        for game in milr_games:
            if game[0]:
                if game[7] == 0:
                    game_state = f'{assets.obc_icon[game[6]]} - {game[4]} {game[5]} out(s)'
                else:
                    game_state = 'Final'
                scoreboard_text += f'|[{game[0]}]({website_url}/team/{game[0]})|{game[1]}|[{game[2]}]({website_url}/team/{game[2]})|{game[3]}|{game_state}|[Link]({game[8]})|\r\n'
        scoreboard_text += '\r\n'

    scoreboard_text += '# Standings\r\n\r\n'

    nl_standings = sheets.read_sheet(mlr_sheet, assets.calc_cell['nl_standings'])
    al_standings = sheets.read_sheet(mlr_sheet, assets.calc_cell['al_standings'])
    wildcard = sheets.read_sheet(mlr_sheet, assets.calc_cell['wildcard'])

    scoreboard_text += '**American League**\r\n\r\n'
    scoreboard_text += '|East|W|L|GB|Central|W|L|GB|West|W|L|GB|\r\n'
    scoreboard_text += '|:---|:--:|:----:|:-:|:-----|:--:|:----:|:-:|:--|:--:|:----:|:-:|\r\n'
    for line in al_standings:
        scoreboard_text += f'|{line[0]}|{line[1]}|{line[2]}|{line[3]}|{line[4]}|{line[5]}|{line[6]}|{line[7]}|{line[8]}|{line[9]}|{line[10]}|{line[11]}|\r\n'

    scoreboard_text += '**National League**\r\n\r\n'
    scoreboard_text += '|East|W|L|GB|Central|W|L|GB|West|W|L|GB|\r\n'
    scoreboard_text += '|:---|:--:|:----:|:-:|:-----|:--:|:----:|:-:|:--|:--:|:----:|:-:|\r\n'
    for line in nl_standings:
        scoreboard_text += f'|{line[0]}|{line[1]}|{line[2]}|{line[3]}|{line[4]}|{line[5]}|{line[6]}|{line[7]}|{line[8]}|{line[9]}|{line[10]}|{line[11]}|\r\n'

    scoreboard_text += '**Wildcard**\r\n\r\n'
    scoreboard_text += '|American League|W|L|GB|National League|W|L|GB|\r\n'
    scoreboard_text += '|:--------------|:-:|:-:|:-:|:--------------|:-:|:-:|:-:|\r\n'
    for line in wildcard:
        scoreboard_text += f'|{line[5]}|{line[6]}|{line[7]}|{line[7]}|{line[0]}|{line[1]}|{line[2]}|{line[3]}|\r\n'

    scoreboard_text += '\n---\nLast Updated at %s' % datetime.datetime.now()
    print(scoreboard_text)

    await reddit.edit_thread(scoreboard_post.url, scoreboard_text)
