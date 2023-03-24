obc_img = {
    '0': 'https://i.imgur.com/hDI37FB.png',
    '1': 'https://i.imgur.com/UPLvY9X.png',
    '2': 'https://i.imgur.com/mJMa2L3.png',
    '3': 'https://i.imgur.com/H1zBoJ7.png',
    '4': 'https://i.imgur.com/67TIglP.png',
    '5': 'https://i.imgur.com/KmhskOq.png',
    '6': 'https://i.imgur.com/5unj2l8.png',
    '7': 'https://i.imgur.com/fbZnSUy.png'
}

calc_cell = {
    'al_east': 'Standings!A14:D18',
    'al_central': 'Standings!E14:H18',
    'al_west': 'Standings!I14:L18',
    'al_wildcard': 'Standings!S3:V14',
    'at_bat': 'Calculator!B6:F6',
    'awards': 'Calculator!A1:H1',
    'away_lineup': 'Starting Lineups!B6:C14',
    'away_position_changes': 'Subs!F4:H16',
    'away_score': 'CalculatorBE!F3',
    'away_subs': 'Subs!B4:D16',
    'away_team': 'Starting Lineups!B2',
    'batter_name': 'Calculator!B6',
    'boxscore': 'Box Score!A1:A77',
    'calc_be': 'CalculatorBE!A3:CM3',
    'current_situation': 'Box Score!C6',
    'dia_standings': 'Standings!F4:I7',
    'discord_name': 'Calculator!B22',
    'discord_ping': 'Calculator!B18:B21',
    'due_up': 'Box Score!C69',  # nice
    'event': 'Calculator!F6',
    'game_awards_input': 'Game Awards Input',
    'game_complete': 'Calculator!G12',
    'game_data': 'Starting Lineups!B2:H2',
    'game_data_import': 'Game Data Import!A1:I1',
    'game_end': 'Calculator!I5',
    'game_log': 'Game Log',
    'game_state': 'Calculator!B3:F3',
    'home_lineup': 'Starting Lineups!E6:F14',
    'home_position_changes': 'Subs!F22:H34',
    'home_score': 'CalculatorBE!E3',
    'home_subs': 'Subs!B22:D34',
    'home_team': 'Starting Lineups!E2',
    'ind_standings': 'Standings!A4:D7',
    'league': 'Starting Lineups!G2',
    'milr': 'Starting Lineups!G2',
    'milr_appointments': 'Player Appointments!J3:Q30',
    'mlr_appointments': 'Player Appointments!A3:I32',
    'next_up': 'Box Score!C8',
    'nl_east': 'Standings!A4:D8',
    'nl_central': 'Standings!E4:H8',
    'nl_west': 'Standings!I4:L8',
    'nl_wildcard': 'Standings!N3:Q14',
    'deprecated_pitch': 'Calculator!E6',
    'pitcher_name': 'Calculator!D6',
    'play_number': 'Calculator!G6',
    'reddit_ping': 'Calculator!B15',
    'result': 'Calculator!F8:F10',
    'lineup_check': 'Starting Lineups!B18:E18',
    'season_session': 'Template!C17',
    'starting_pitchers': 'Starting Lineups!B16:F16',
    'swing': 'Calculator!C6',
    'twi_standings': 'Standings!A12:D15',
    'ump_list': 'Calculator!F24:F26',
    'wnd_standings': 'Standings!F12:I15'
}

calc_cell2 = {
    'after_swing': 'CalcBE!Q3:U3',
    'all_players': 'LineupBE!A2:A52',
    'at_bat': 'CalcBE!G3:K3',
    'awards': 'Calc!I24:L24',
    'away_lineup': 'Starting Lineups!B6:C16',
    'away_pitcher': 'Subs!J14',
    'away_sub_list': 'LineupBE!C3:C27',
    'away_team': 'Starting Lineups!B2',
    'before_swing': 'CalcBE!B3:F3',
    'boxscore': 'Box Score!A1:A77',
    'current_matchup': 'Calc!C6:E6',
    'current_situation': 'Box Score!C3',
    'discord_ping': 'Calc!C23:E26',
    'due_up': 'Box Score!C7',
    'event': 'Calc!G10',
    'game_complete': 'Calc!L21',
    'game_log': 'NewGL!G:BL',
    'game_sheet_input': 'Game Sheet Input',
    'good_lineup': 'Starting Lineups!B18:E18',
    'home_lineup': 'Starting Lineups!E6:F16',
    'home_pitcher': 'Subs!J32',
    'home_sub_list': 'LineupBE!C30:C54',
    'home_team': 'Starting Lineups!E2',
    'line_score': 'Box Score!A10:A13',
    'log_result': 'CalcBE!BK3:CB3',
    'matchup_info': 'CalcBE!V3:AB3',
    'milr_check': 'Starting Lineups!G2',
    'next_up': 'Box Score!C5',
    'obc_before': 'CalcBE!D3',
    'swing': 'Calc!C10',
    'pitch': 'Calc!E10',
    'starting_pitchers': 'Starting Lineups!B16:E16',
    'pitcher_list': 'newGL!I3:I130',
    'pitcher_performance': 'Box Score!A39:A43',
    'pitcher_ab': 'Calc!C24:26',
    'play_number': 'Calc!H3',
    'reddit_ping': 'Calc!C16:G19',
    'result': 'CalcBE!L3:O3',
    'result_embed': 'Calc!J7:J16',
    'scoring_plays': 'boxscoreBE!T140:T165'
}

batting_types = {
    '1B': '1B/BB',
    'BC': 'Basic Contact',
    'BN': 'Basic Neutral',
    'BP': 'Basic Power',
    'EN': 'Extremely Neutral',
    'HK': 'Homerun/K',
    'MH': 'Max Homers',
    'P': 'Pitcher',
    'S': 'Speedy',
    'SF': 'Single Focused',
    'SM': 'Sacrifice Master',
    'TT': 'Three True Outcomes',
    'WC': 'Work the Count',
    'XB': 'Extra Base Focused'
}

pitching_types = {
    '1B': '1B/BB',
    'BB': 'Basic Balanced',
    'BF': 'Basic Finesse',
    'BS': 'Basic Strikeout',
    'EG': 'Extreme Groundball',
    'EN': 'Extreme Neutral',
    'FP': 'Flyball',
    'NH': 'No Homers',
    'NT': 'Nothing to Hit',
    'SF': 'Single Focused',
    'TD': 'Trust Your Defense',
    'TT': 'Three True Outcomes',
    'WC': 'Weak Contact'
}

hand_bonus = {
    'B': 'Balanced',
    'H': 'Anti-Homer',
    'S': 'Anti-Single'
}

stadium_image = {
    'ARI': 'https://i.imgur.com/ZzNi54t.png',
    'ATL': 'https://i.imgur.com/prvTr0u.png',
    'BAL': 'https://i.imgur.com/nKEZqzw.png',
    'BOS': 'https://i.imgur.com/kTFgR40.png',
    'CHC': 'https://i.imgur.com/yPQk4bc.png',
    'CIN': 'https://i.imgur.com/V3lU8rw.png',
    'CLE': 'https://i.imgur.com/k6hCgre.png',
    'COL': 'https://i.imgur.com/dRNnoo1.png',
    'CWS': 'https://i.imgur.com/q3F5D9l.png',
    'DET': 'https://i.imgur.com/qBGE3GV.png',
    'HOU': 'https://i.imgur.com/wWma73L.png',
    'KCR': 'https://i.imgur.com/Vq3EsTc.png',
    'LAA': 'https://i.imgur.com/pXzslBP.png',
    'LAD': 'https://i.imgur.com/h3y8OMU.png',
    'MIA': 'https://i.imgur.com/ozdMxFF.png',
    'MIL': 'https://i.imgur.com/7GiIIBP.png',
    'MIN': 'https://i.imgur.com/cBZ6hap.png',
    'MTL': 'https://i.imgur.com/0pHqrWB.png',
    'NYM': 'https://i.imgur.com/0dG69NA.png',
    'NYY': 'https://i.imgur.com/4zhZ8em.png',
    'OAK': 'https://i.imgur.com/jMskirU.png',
    'PHI': 'https://i.imgur.com/Ss28gcL.png',
    'PIT': 'https://i.imgur.com/BCY71yA.png',
    'SDP': 'https://i.imgur.com/BXGVWh3.png',
    'SEA': 'https://i.imgur.com/WujQvK9.png',
    'SFG': 'https://i.imgur.com/Uex5Rq9.png',
    'STL': 'https://i.imgur.com/H6QrapF.png',
    'TBR': 'https://i.imgur.com/q2sxEwi.png',
    'TEX': 'https://i.imgur.com/usXdKAY.png',
    'TOR': 'https://i.imgur.com/Nj3ncm5.png'
}

main_role_ids = {
    'Player': 490008203925389344,
    'GM': 344859708022194176,
    'MiLR GM': 537383086007255049,
    'Committee': 496778795328602112,
    'Draftee': 588923566091665412,
    'Free Agent': 416390298961313792,
    'Retired': 782318487305060442,
    'Awards Association Member': 451733045054275606,
    'MVP': 798747944962359336,
    'Pitcher of the Year': 801834040302764064,
    'GM of the Year': 801834106584956951,
    'Rookie of the Year': 801834153636266034,
    'Reliever of the Year': 818978149210521691,
    'Silver Slugger': 801834215724941383,
    'Paper Cup Winner': 801834274319368284,
    'Styrofoam Cup Winner': 801840064803635220,
    'Ump Warden': 436348522246438912,
    'Ump Council': 600416061455859753,
    'LOM': 805537549615366154,
}

fcb_team_ids = ['PUR', 'ORD', 'MSU', 'MCH', 'HRW', 'PAN']

valid_positions = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'PH', 'PR']

steal_types = ['STEAL 2B', 'STEAL 3B', 'STEAL HOME', 'MSTEAL 3B', 'MSTEAL HOME']

event_types = ['Swing', 'Auto K', 'Auto BB', 'Bunt', 'Steal 2B', 'Steal 3B', 'Infield In', 'IBB']

states = ['WAITING FOR LINEUPS',
          'WAITING FOR PITCH',
          'WAITING FOR SWING',
          'WAITING FOR RESULT',
          'PAUSED',
          'WAITING FOR PITCHER CONFIRMATION',
          'WAITING FOR UMP CONFIRMATION',
          'FINALIZING',
          'COMPLETE']

obc_state = {
    0: 'Bases Empty',
    1: 'Runner on First',
    2: 'Runner on Second',
    3: 'Runner on Third',
    4: 'Runners on First and Second',
    5: 'Runners on First and Third',
    6: 'Runners on Second and Third',
    7: 'Bases Loaded',
}

team_cities = {
    'ARI': 'Arizona',
    'ATL': 'Atlanta',
    'BAL': 'Baltimore',
    'BOS': 'Boston',
    'CHC': 'Chicago',
    'CIN': 'Cincinatti',
    'CLE': 'Cleveland',
    'COL': 'Colorado',
    'CWS': 'Chicago',
    'DET': 'Detroit',
    'HOU': 'Houston',
    'KCR': 'Kansas City',
    'LAA': 'Los Angeles',
    'LAD': 'Los Angeles',
    'MIA': 'Miami',
    'MIL': 'Milwaukee',
    'MIN': 'Minnesota',
    'MTL': 'Montreal',
    'NYM': 'New York',
    'NYY': 'New York',
    'OAK': 'Oakland',
    'PHI': 'Philadelphia',
    'PIT': 'Pittsburgh',
    'SDP': 'San Diego',
    'SEA': 'Seattle',
    'SFG': 'San Francisco',
    'STL': 'St. Louis',
    'TBR': 'Tampa Bay',
    'TEX': 'Texas',
    'TOR': 'Toronto',
    'AL': 'American League',
    'NL': 'National League',
    'BAG': 'Bay Area',
    'BIS': 'Bismark',
    'BLO': 'Bloomington',
    'CCD': 'Chattanooga',
    'CDT': 'Carolina',
    'GND': 'Gondor',
    'LAC': 'La Crosse',
    'MKW': 'Mackinaw City',
    'MMM': 'Michigan',
    'NXS': 'Anxiety',
    'PPM': 'Point Pleasant',
    'SCU': 'Santa Rosa',
    'IL': 'International League',
    'PCL': 'Pacific Coast League',
}

team_nicknames = {
    'ARI': 'Diamondbacks',
    'ATL': 'Braves',
    'BAL': 'Orioles',
    'BOS': 'Red Sox',
    'CHC': 'Cubs',
    'CIN': 'Reds',
    'CLE': 'Guardians',
    'COL': 'Rockies',
    'CWS': 'White Sox',
    'DET': 'Tigers',
    'HOU': 'Colt 45s',
    'KCR': 'Royals',
    'LAA': 'Angels',
    'LAD': 'Dodgers',
    'MIA': 'Marlins',
    'MIL': 'Brewers',
    'MIN': 'Twins',
    'MTL': 'Expos',
    'NYM': 'Mets',
    'NYY': 'Yankees',
    'OAK': 'Athletics',
    'PHI': 'Phillies',
    'PIT': 'Pirates',
    'SDP': 'Padres',
    'SEA': 'Mariners',
    'SFG': 'Giants',
    'STL': 'Cardinals',
    'TBR': 'Rays',
    'TEX': 'Rangers',
    'TOR': 'Blue Jays',
    'AL': 'AL All Stars',
    'NL': 'NL All Stars',
    'BAG': 'Goldfish',
    'BIS': 'Balks',
    'BLO': 'Onions',
    'CCD': 'Coconut Dogs',
    'CDT': 'Disco Turkeys',
    'GND': 'Gronds',
    'LAC': 'Loggers',
    'MKW': 'Trolls',
    'MMM': 'Marksmen',
    'NXS': 'Attacks',
    'PPM': 'Mothmen',
    'SCU': 'Scuba Divers',
    'IL': 'IL All Stars',
    'PCL': 'PCL All Stars',
}