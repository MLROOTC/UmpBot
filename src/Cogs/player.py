import configparser
from discord.ext import commands
import src.db_controller as db
import src.assets as assets
import discord
import src.sheets_reader as sheets

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')
gm_role_id = int(config_ini['Discord']['gm_role_id'])


class Player(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config_ini = configparser.ConfigParser()
        self.config_ini.read('config.ini')
        self.timeout = float(config_ini['Discord']['timeout']) * 60
        self.league_ops_channel = int(config_ini['Discord']['league_ops_channel'])
        self.league_ops_role = int(config_ini['Discord']['league_ops_role'])
        self.ump_admin = int(config_ini['Discord']['ump_admin_role'])
        self.main_guild_id = config_ini['Discord']['main_guild_id']

    @commands.command(brief='Bunt ranges',
                      description='Bunt rules and ranges')
    async def bunt(self, ctx):
        await ctx.send(self.config_ini['URLs']['bunt'])

    @commands.command(brief='Calculates an AB result. Use .help calc for more info.',
                      description='Calculates a result after being passed in a pitcher, batter, swing, and pitch. Park is an optional argument.\n\nFormat:\n\n\t.calc <batterName>; <swing#>; <pitcherName>; <pitch#>; <park>')
    async def calc(self, ctx, *, calc_data):
        result_types = ['HR', '3B', '2B', '1B', 'BB', 'FO', 'K', 'PO', 'RGO', 'LGO']
        calc_data = calc_data.replace(' ;', ';')
        calc_data = calc_data.replace('; ', ';')
        calc_data = calc_data.split(';')
        batter = await get_player(ctx, calc_data[0])
        swing = int(calc_data[1])
        pitcher = await get_player(ctx, calc_data[2])
        pitch = int(calc_data[3])
        if not 0 < pitch <= 1000:
            await ctx.send('Pitch must be between 1 and 1000')
            return
        if not 0 < swing <= 1000:
            await ctx.send('Swing must be between 1 and 1000')
            return
        hand_bonus = False
        response = '%s batting against %s' % (batter[1], pitcher[1])
        if len(calc_data) > 4:
            park = calc_data[4]
            park = db.fetch_data('''SELECT team, parkName FROM parkFactors WHERE team=%s''', (park.upper(),))
            response += ' at %s' % park[0][1]
            if not park:
                await ctx.send('Park not found. Please try again.')
            response += ' at %s' % park[0][1]
            park = park[0][0]
        else:
            park = None
        if not pitcher or not batter:
            return None
        if pitcher[4]:
            pitching_type = pitcher[4]
        else:
            pitching_type = 'POS'
            response += '\n*Warning, %s is using the position player pitching batting type.*' % pitcher[1]

        if batter[3]:
            batting_type = batter[3]
        else:
            batting_type = 'P'
            response += '\n*Warning, %s is using the pitcher batting type.*' % batter[1]

        if batter[6] == pitcher[6]:
            hand_bonus = pitcher[5]
        ranges = calculate_ranges(batting_type, pitching_type, hand_bonus, park)
        diff = calculate_diff(pitch, swing)
        total = 0
        for i in range(len(ranges)):
            total += ranges[i]
            if diff <= total:
                result = result_types[i]
                break
        response += '\n> Swing: %s\n> Pitch: %s\n> Diff: %s -> %s' % (swing, pitch, diff, result)
        await ctx.send(response)

    @commands.command(brief='Sync a discord account with the player in the database',
                      description='Links your discord ID to your player in the database. Used for AB pings, player and stats commands.')
    async def claim(self, ctx, *, player_name):
        claiming_player = await get_player(ctx, player_name)
        if not claiming_player:
            return
        if claiming_player[14]:
            await ctx.send('Player has already been claimed.')
            return
        claiming_account = db.fetch_data('''SELECT * FROM playerData WHERE discordID = %s''', (ctx.author.id,))
        if claiming_account:
            await ctx.send('There is already a player associated with your discord account.')
            return
        await ctx.send('Claim the following player?')
        embed = player_embed(claiming_player)
        claim_msg = await ctx.send(embed=embed)
        await claim_msg.add_reaction('✅')
        await claim_msg.add_reaction('❌')

        def check(result_reaction, ump_user):
            return result_reaction.message.id == claim_msg.id and ump_user == ctx.message.author and str(
                result_reaction.emoji) in ['✅', '❌']

        user_react, user = await self.bot.wait_for('reaction_add', timeout=self.timeout, check=check)
        if user_react.emoji == '✅':
            await claim_msg.edit(content='Request submitted for approval.', embed=None)
            channel = self.bot.get_channel(self.league_ops_channel)
            approval_msg = await channel.send(content='<@%s> has claimed the following user:' % ctx.author.id, embed=embed)
            await approval_msg.add_reaction('✅')
            await approval_msg.add_reaction('❌')

            main = self.bot.get_guild(int(self.main_guild_id))
            league_ops_role = discord.utils.get(main.roles, id=self.league_ops_role)
            
            def approval(approval_reaction, admin_user):
                return approval_reaction.message.id == approval_msg.id and league_ops_role in main.get_member(admin_user.id).roles and str(approval_reaction.emoji) in ['✅', '❌']

            admin_react, admin_react_user = await self.bot.wait_for('reaction_add', timeout=None, check=approval)
            if admin_react.emoji == '✅':
                db.update_database('''UPDATE playerData SET discordID=%s, discordName=%s WHERE playerID=%s''', (ctx.author.id, str(ctx.author), claiming_player[0]))
                updated_player = await get_player(ctx, claiming_player[1])
                if updated_player[14]:
                    await ctx.author.send(content='Your request to claim the following player has been approved.', embed=player_embed(updated_player))
                    await approval_msg.add_reaction('👌')
                else:
                    await approval_msg.add_reaction('❗')
            elif admin_react.emoji == '❌':
                await ctx.author.send(content='Your request to claim the following player has been denied.', embed=embed)
        elif user_react.emoji == '❌':
            return

    @commands.command(brief='FCB Pitching Stats',
                      description='Displays pitching stats for MiLR')
    async def fpstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send(
                    'Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = pstats_embed(player, 'fcb')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='FCB Batting Stats',
                      description='Displays batting stats for MLR')
    async def fstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send(
                    'Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = stats_embed(player, 'fcb')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='FCB Pitching Stats',
                      description='Displays pitching stats for MiLR')
    async def gpstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send(
                    'Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = pstats_embed(player, 'gib')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='FCB Batting Stats',
                      description='Displays batting stats for MLR')
    async def gstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send(
                    'Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = stats_embed(player, 'gib')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='Link to Umpire Handbook',
                      description='A link to the umpire handbook, contains additional guidelines and practices not included in the official rulebook.')
    async def handbook(self, ctx):
        await ctx.send(self.config_ini['URLs']['ump_handbook'])

    @commands.command(brief='Server invite link for the bot',
                      description='Provides an invite link to add the bot to your server. Limited to GMs only.')
    @commands.has_role(gm_role_id)
    async def invite(self, ctx):
        await ctx.send(self.config_ini['URLs']['bot_invite_link'])

    @commands.command(brief='Sends the MiLR roster sheet',
                      description='Gives the MiLR roster sheet')
    async def milrrosters(self, ctx):
        await ctx.send(self.config_ini['URLs']['milr_roster'])

    @commands.command(brief='MiLR Standings')
    async def milrstandings(self, ctx):
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['milr_roster'])
        il_standings = sheets.read_sheet(sheet_id, assets.calc_cell['il_standings'])
        pcl_standings = sheets.read_sheet(sheet_id, assets.calc_cell['pcl_standings'])
        il = 'Team                     W  L GB'
        pcl = 'Team                     W  L GB'
        for team in il_standings:
            il += '\n%-23s %2s %2s %2s' % (team[0][:23], team[1], team[2], team[3])
        for team in pcl_standings:
            pcl += '\n%-23s %2s %2s %2s' % (team[0][:23], team[1], team[2], team[3])
        embed = discord.Embed(title='MiLR Standings')
        embed.add_field(name='International League', value='```%s```' % il, inline=False)
        embed.add_field(name='Pacific Coast League', value='```%s```' % pcl, inline=False)
        embed.set_footer(text='x - Clinched Playoffs\ny - Clinched Bye\ne - Eliminated')
        await ctx.send(embed=embed)

    @commands.command(brief='MiLR Pitching Stats',
                      description='Displays pitching stats for MiLR')
    async def mpstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send('Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = pstats_embed(player, 'milr')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='MiLR Batting Stats',
                      description='Displays batting stats for MiLR')
    async def mstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send(
                    'Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = stats_embed(player, 'milr')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='Display player info',
                      description='Displays information about a player. Note: username is currently required.')
    async def player(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send('Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        if player:
            sheet_id = sheets.get_sheet_id(self.config_ini['URLs']['mlr_roster'])
            player_stats = sheets.read_sheet(sheet_id, 'Player Stats')
            embed = player_embed(player)
            for p in player_stats:
                if p[1] == 'Hitting Stats':
                    session = p[90]
                elif p[0] == player[1]:
                    if player[7] != 'P':
                        embed.add_field(name='AVG/OBP/SLG/OPS', value='%s/%s/%s/%s' % (p[17], p[18], p[19], p[20]), inline=False)
                    if player[7] == 'P' or player[7] == 'PH':
                        embed.add_field(name='IP/ER/ERA/WHIP', value='%s/%s/%s/%s' % (p[44], p[47], p[68], p[70]), inline=False)
                    embed.set_footer(text='*Stats shown through Session %s' % session)
            await ctx.send(embed=embed)

    @commands.command(brief='MLR Pitching Stats',
                      description='Displays pitching stats for MLR')
    async def pstats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send('Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = pstats_embed(player, 'mlr')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='Quit',
                      description='Quit.')
    async def quit(self, ctx):
        await ctx.send('https://media.discordapp.net/attachments/792980248094441473/859569440872988693/quit.png?width=1056&height=528')

    @commands.command(brief='Calculates ranges for a given pitcher, batter, park, and infield in.',
                      description='Gives the ranges for a batter vs pitcher matchup. Optionally takes a park as a '
                                  'parameter using the three letter team abbreviation, as well as a 4th option for '
                                  'infield in.\n\nExample:\n\n\t.ranges batter name; pitcher name; park; true')
    async def ranges(self, ctx, *, players):
        players = players.replace(' ;', ';')
        players = players.replace('; ', ';')
        players = players.split(';')
        result_types = ['HR', '3B', '2B', '1B', 'BB', 'FO', 'K', 'PO', 'RGO', 'LGO']
        batter = await get_player(ctx, players[0])
        pitcher = await get_player(ctx, players[1])
        if not pitcher or not batter:
            return None
        hand_bonus = False
        park = None
        if_in = False
        total = 0
        response = '%s (%s|%s) batting against %s (%s|%s-%s)' % (batter[1], batter[6][0], batter[3], pitcher[1], pitcher[6][0], pitcher[4], pitcher[5])

        if len(players) >= 3:
            park = players[2]
            park = db.fetch_data('''SELECT team, parkName FROM parkFactors WHERE team=%s''', (park.upper(),))
            if not park:
                await ctx.send('Park not found. Please try again.')
            response += ' at %s' % park[0][1]
            park = park[0][0]
        if len(players) >= 4:
            if_in = True
            response += ' with the infield in'
        response += '.'
        if pitcher[4]:
            pitching_type = pitcher[4]
        else:
            pitching_type = 'POS'
            response += '\n*Warning, %s is using the position player pitching batting type.*' % pitcher[1]

        if batter[3]:
            batting_type = batter[3]
        else:
            batting_type = 'P'
            response += '\n*Warning, %s is using the pitcher batting type.*' % batter[1]

        if batter[6] == pitcher[6]:
            hand_bonus = pitcher[5]

        ranges = calculate_ranges(batting_type, pitching_type, hand_bonus, park)

        if if_in:
            ranges[3] += 18
            ranges[8] -= 9
            ranges[9] -= 9
        response += '\n```'
        for i in range(len(result_types)):
            response += '%3s: %3s - %3s\n' % (result_types[i], total, total + ranges[i] - 1)
            total += ranges[i]
        response += '```'

        await ctx.send(response)

    @commands.command(brief='Sends the MLR roster sheet',
                      description='Gives the MiLR roster sheet')
    async def rosters(self, ctx):
        await ctx.send(self.config_ini['URLs']['mlr_roster'])

    @commands.command(brief='Link to MLR Rulebook',
                      description='Link to MLR Rulebook')
    async def rulebook(self, ctx):
        await ctx.send(self.config_ini['URLs']['rulebook'])

    @commands.command(brief='Division Standings',
                      description='Displays division standings from MLR roster sheet')
    async def standings(self, ctx):
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['mlr_roster'])
        al_east = sheets.read_sheet(sheet_id, assets.calc_cell['al_east'])
        al_central = sheets.read_sheet(sheet_id, assets.calc_cell['al_central'])
        al_west = sheets.read_sheet(sheet_id, assets.calc_cell['al_west'])
        nl_east = sheets.read_sheet(sheet_id, assets.calc_cell['nl_east'])
        nl_central = sheets.read_sheet(sheet_id, assets.calc_cell['nl_central'])
        nl_west = sheets.read_sheet(sheet_id, assets.calc_cell['nl_west'])
        ale = 'Team                     W  L GB'
        alc = 'Team                     W  L GB'
        alw = 'Team                     W  L GB'
        nle = 'Team                     W  L GB'
        nlc = 'Team                     W  L GB'
        nlw = 'Team                     W  L GB'
        for team in al_east:
            ale += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in al_central:
            alc += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in al_west:
            alw += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in nl_east:
            nle += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in nl_central:
            nlc += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in nl_west:
            nlw += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        embed = discord.Embed(title='Division Standings')
        embed.add_field(name='AL East', value='```%s```' % ale, inline=False)
        embed.add_field(name='AL Central', value='```%s```' % alc, inline=False)
        embed.add_field(name='AL West', value='```%s```' % alw, inline=False)
        embed.add_field(name='NL East', value='```%s```' % nle, inline=False)
        embed.add_field(name='NL Central', value='```%s```' % nlc, inline=False)
        embed.add_field(name='NL West', value='```%s```' % nlw, inline=False)
        embed.set_footer(text='x - Clinched Playoff Spot\ny - Clinched Division\nz - Clinched Bye\nq - Eliminated')
        await ctx.send(embed=embed)

    @commands.command(brief='MLR Batting Stats',
                      description='Displays batting stats for MLR')
    async def stats(self, ctx, *, playername=None):
        if playername:
            player = await get_player(ctx, playername)
        else:
            sql = '''SELECT * from playerData WHERE discordID=%s'''
            player = db.fetch_data(sql, (ctx.author.id,))
            if player:
                player = player[0]
            else:
                await ctx.send('Could not find a player associated with your discord account. Please use .claim <playername> to link your player to your discord account.')
        if not player:
            return
        embed = stats_embed(player, 'mlr')
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Couldn\'t find any stats for this player.')

    @commands.command(brief='Stealing ranges',
                      description='Stealing ranges')
    async def steals(self, ctx):
        await ctx.send(self.config_ini['URLs']['steals'])

    @commands.command(brief='Display team info',
                      description='Displays team name, park, ranges, etc.')
    async def team(self, ctx, abbr):
        embed = team_embed(abbr)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send('Could not find team %s' % abbr.upper())

    @commands.command(brief='List of MLR teams + MiLR teams',
                      description='Gives a list of all MLR teams and their asssociated MiLR team.')
    async def teamlist(self, ctx):
        await ctx.send(self.config_ini['URLs']['team_list'])

    @commands.command()
    async def test(self, ctx):
        return

    @commands.command(brief='Ump council form',
                      description='Returns a link to the google form for an ump council ruling.')
    async def umpcouncil(self, ctx):
        await ctx.send(self.config_ini['URLs']['ump_council_form'])

    @commands.command(brief='Wildcard Standings',
                      description='Displays wildcard standings from MLR roster sheet')
    async def wildcard(self, ctx):
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['mlr_roster'])
        al_wildcard = sheets.read_sheet(sheet_id, assets.calc_cell['al_wildcard'])
        nl_wildcard = sheets.read_sheet(sheet_id, assets.calc_cell['nl_wildcard'])
        al_wc = 'Team                     W  L GB'
        nl_wc = 'Team                     W  L GB'
        for team in al_wildcard:
            al_wc += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        for team in nl_wildcard:
            nl_wc += '\n%-23s %2s %2s %2s' % (team[0], team[1], team[2], team[3])
        embed = discord.Embed(title='Wildcard Standings')
        embed.add_field(name='American League', value='```%s```' % al_wc, inline=False)
        embed.add_field(name='National League', value='```%s```' % nl_wc, inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Player(bot))


# Helper Functions

def calculate_diff(pitch, swing):
    diff = abs(swing - pitch)
    if diff > 500:
        if swing > 500:
            return abs(1000 - swing + pitch)
        else:
            return abs(1000 - pitch + swing)
    return diff


def calculate_ranges(batting_type, pitching_type, hand_bonus, park):
    batting_ranges = db.fetch_data('''SELECT rangeHR, range3B, range2B, range1B, rangeBB, rangeFO, rangeK, rangePO, rangeRGO, rangeLGO FROM battingTypes WHERE type=%s ''', (batting_type,))[0]
    pitching_ranges = db.fetch_data('''SELECT rangeHR, range3B, range2B, range1B, rangeBB, rangeFO, rangeK, rangePO, rangeRGO, rangeLGO FROM pitchingTypes WHERE type=%s ''', (pitching_type,))[0]
    if hand_bonus:
        hand_bonus_ranges = db.fetch_data('''SELECT rangeHR, range3B, range2B, range1B, rangeBB, rangeFO, rangeK, rangePO, rangeRGO, rangeLGO FROM handBonuses WHERE type=%s ''',(hand_bonus,))[0]
    if park:
        park_factors = db.fetch_data('''SELECT rangeHR, range3B, range2B, range1B, rangeBB FROM parkFactors WHERE team=%s ''', (park,))[0]

    result_types = ['HR', '3B', '2B', '1B', 'BB', 'FO', 'K', 'PO', 'RGO', 'LGO']
    ranges = []
    offset = 0
    index = 0

    for i in range(len(result_types)):
        matchup = batting_ranges[i] + pitching_ranges[i]
        if hand_bonus:
            matchup += hand_bonus_ranges[i]
        if park and i < 5:
            neutral_matchup = matchup
            matchup = round(float(matchup * park_factors[i]))
            offset += (matchup - neutral_matchup)
        ranges.append(matchup)

    while offset != 0:
        if offset > 0:
            ranges[index + 5] = ranges[index + 5] - 1
            offset -= 1
        elif offset < 0:
            ranges[index + 5] = ranges[index + 5] + 1
            offset += 1
        index += 1
        if index >= 5:
            index = 0
    return ranges


async def get_player(ctx, name):
    sql = '''SELECT * from playerData WHERE playerName LIKE %s'''
    players = db.fetch_data(sql, ('%'+name+'%',))
    if len(players) == 1:
        return players[0]
    elif len(players) == 0:
        await ctx.send("Your search for %s yielded no results." % name)
    else:
        reply = "Your search for %s returned too many results" % name
        for player in players:
            if player[1].lower() == name.lower():
                return player
            reply += '\n - %s' % player[1]
        await ctx.send(reply)
    return None


def player_embed(player):
    player_id, player_name, team, batting_type, pitching_type, hand_bonus, hand, pos1, pos2, pos3, reddit_name, discord_name, discord_id, format_no, status = player
    if not discord_name:
        discord_name = '--'
    if discord_id:
        discord_name = '<@%s>' % discord_id

    positions = pos1
    if pos2:
        positions += '/' + pos2
    if pos3:
        positions += '/' + pos3

    if team:
        team = db.fetch_data('SELECT * FROM teamData WHERE abb=%s', (team,))
        if team:
            team = team[0]
            embed_color = discord.Color(value=int(team[2], 16))
            embed = discord.Embed(title=player_name, color=embed_color)
            embed.set_thumbnail(url=team[3])
        else:
            embed = discord.Embed(title=player_name)
    else:
        embed = discord.Embed(title=player_name)
    embed.add_field(name='Hand', value=hand, inline=True)
    embed.add_field(name='Position', value=positions, inline=True)
    if batting_type:
        embed.add_field(name='Batting Type', value=assets.batting_types[batting_type], inline=False)
    if pitching_type:
        pitching = '%s (%s)' % (assets.pitching_types[pitching_type], assets.hand_bonus[hand_bonus])
        embed.add_field(name='Pitching Type', value=pitching, inline=False)
    embed.add_field(name='Discord', value=discord_name, inline=True)
    embed.add_field(name='Reddit', value='[%s](https://www.reddit.com/%s)' % (reddit_name, reddit_name), inline=True)
    embed.add_field(name='Player ID', value=player_id, inline=True)
    return embed


def pstats_embed(player, league):
    if league == 'milr':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['milr_roster'])
    elif league == 'mlr':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['mlr_roster'])
    elif league == 'fcb':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['fcb_roster'])
    elif league == 'gib':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['gib_roster'])
    else:
        return None
    player_stats = sheets.read_sheet(sheet_id, 'Player Stats')
    for p in player_stats:
        if p[1] == 'Hitting Stats':
            session = p[90]
        elif p[0] == player[1]:
            games = p[42]
            games_started = p[43]
            innings_pitched = p[44]
            wins = p[84]
            losses = p[85]
            saves = p[86]
            era = p[68]
            earned_runs = p[47]
            batters_faced = p[45]
            dbf = p[77]
            whip = p[70]
            pwar = p[83]
            title = player[1]
            pitching_type = db.fetch_data('''SELECT name FROM pitchingTypes WHERE type = %s''', (player[4],))
            if pitching_type:
                pitching_type = pitching_type[0][0]
            else:
                pitching_type = player[4]
            hand_bonus = db.fetch_data('''SELECT name FROM handBonuses WHERE type = %s''', (player[5],))
            if hand_bonus:
                hand_bonus = hand_bonus[0][0]
            else:
                hand_bonus = player[5]
            description = '%s (%s) | %s' % (pitching_type, hand_bonus, player[6])
            if player[2]:
                if league == 'mlr':
                    team = db.fetch_data('''SELECT * FROM teamData WHERE abb=%s''', (player[2],))
                elif league == 'milr':
                    team = db.fetch_data('''SELECT * FROM teamData WHERE abb=%s''', (assets.milr_affiliate[player[2]],))
                else:
                    team = None
                if team:
                    if len(team) == 1:
                        team = team[0]
                        embed_color = discord.Color(value=int(team[2], 16))
                        embed = discord.Embed(color=embed_color, title=title, description=description,
                                              url='https://www.reddit.com%s' % player[10])
                        embed.set_thumbnail(url=team[3])
                else:
                    embed = discord.Embed(title=title, description=description)
            else:
                embed = discord.Embed(title=title, description=description)
            embed.add_field(name='Games/Starts', value='%s (%s)' % (games, games_started), inline=False)
            embed.add_field(name='Record', value='%s - %s (%s)' % (wins, losses, saves), inline=True)
            embed.add_field(name='IP', value=innings_pitched, inline=True)
            embed.add_field(name='BF', value=batters_faced, inline=True)
            embed.add_field(name='ER', value=earned_runs, inline=True)
            embed.add_field(name='ERA', value=era, inline=True)
            embed.add_field(name='WHIP', value=whip, inline=True)
            embed.add_field(name='DBF', value=dbf, inline=True)
            embed.add_field(name='pWAR', value=pwar, inline=True)
            embed.set_footer(text='Stats shown through Session %s' % session)
            return embed
    return None


def stats_embed(player, league):
    if league == 'milr':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['milr_roster'])
    elif league == 'mlr':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['mlr_roster'])
    elif league == 'fcb':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['fcb_roster'])
    elif league == 'gib':
        sheet_id = sheets.get_sheet_id(config_ini['URLs']['gib_roster'])
    else:
        return None
    player_stats = sheets.read_sheet(sheet_id, 'Player Stats')
    for p in player_stats:
        if p[1] == 'Hitting Stats':
            session = p[90]
        elif p[0] == player[1]:
            at_bats = p[3]
            hits = p[4]
            homeruns = p[8]
            runs = p[10]
            rbis = p[11]
            steal_attempts = p[15]
            stolen_bases = p[16]
            avg = p[17]
            obp = p[18]
            slg = p[19]
            ops = p[20]
            dpa = p[38]
            war = p[40]
            title = player[1]
            batting_type = db.fetch_data('''SELECT name FROM battingTypes WHERE type = %s''', (player[3],))
            if batting_type:
                batting_type = batting_type[0][0]
            else:
                batting_type = player[3]
            description = '%s | %s ' % (batting_type, player[6])
            if player[2]:
                if league == 'mlr':
                    team = db.fetch_data('''SELECT * FROM teamData WHERE abb=%s''', (player[2],))
                elif league == 'milr':
                    team = db.fetch_data('''SELECT * FROM teamData WHERE abb=%s''', (assets.milr_affiliate[player[2]],))
                else:
                    team = None
                if team:
                    if len(team) == 1:
                        team = team[0]
                        embed_color = discord.Color(value=int(team[2], 16))
                        embed = discord.Embed(color=embed_color, title=title, description=description,
                                              url='https://www.reddit.com%s' % player[10])
                        embed.set_thumbnail(url=team[3])
                else:
                    embed = discord.Embed(title=title, description=description)
            else:
                embed = discord.Embed(title=title, description=description)
            embed.add_field(name='AVG / OBP / SLG / OPS', value='%s / %s / %s / %s' % (avg, obp, slg, ops),
                            inline=False)
            embed.add_field(name='ABs', value=at_bats, inline=True)
            embed.add_field(name='Hits', value=hits, inline=True)
            embed.add_field(name='HRs', value=homeruns, inline=True)
            embed.add_field(name='SB', value='%s/%s' % (stolen_bases, steal_attempts), inline=True)
            embed.add_field(name='Runs', value=runs, inline=True)
            embed.add_field(name='RBI', value=rbis, inline=True)
            embed.add_field(name='DPA', value=dpa, inline=True)
            embed.add_field(name='WAR', value=war, inline=True)
            embed.set_footer(text='Stats shown through Session %s' % session)
            return embed
    return None


def team_embed(team_abbr):
    team_abbr = team_abbr.upper()
    team = db.fetch_data('SELECT * FROM teamData WHERE abb=%s', (team_abbr,))
    if team:
        team = team[0]
    else:
        return None
    park = db.fetch_data('''SELECT * FROM parkFactors where team=%s''', (team_abbr,))
    embed_color = discord.Color(value=int(team[2], 16))
    embed = discord.Embed(title=team[0], color=embed_color)
    embed.set_thumbnail(url=team[3])
    embed.add_field(name='Abbr.', value=team[1])

    sheet_id = sheets.get_sheet_id(config_ini['URLs']['%s_roster' % team[5]])
    if team[5] == 'mlr':
        record = sheets.read_sheet(sheet_id, '%s!D4' % team_abbr)
        if record:
            if not (record[0][0] == '#N/A' or record[0][0] == '#VALUE!'):
                embed.add_field(name='Record', value=record[0][0][7:])
            else:
                embed.add_field(name='Record', value='--')
        appointments = sheets.read_sheet(sheet_id, assets.calc_cell['mlr_appointments'])
        for team_data in appointments:
            if team_data[0] == team_abbr:
                captain_list = 'None'
                committee_list = 'None'
                awards_list = 'None'
                if len(team_data) >= 3:
                    if team_data[2]:
                        captain_list = '%s' % team_data[2]
                if len(team_data) >= 4:
                    if team_data[3]:
                        captain_list += '\n%s' % team_data[3]
                if len(team_data) >= 5:
                    if team_data[4]:
                        captain_list += '\n%s' % team_data[4]
                if len(team_data) >= 6:
                    if team_data[5]:
                        committee_list = '%s' % team_data[5]
                if len(team_data) >= 7:
                    if team_data[6]:
                        committee_list += '\n%s' % team_data[6]
                if len(team_data) >= 8:
                    if team_data[7]:
                        awards_list = '%s' % team_data[7]
                if len(team_data) >= 9:
                    if team_data[8]:
                        awards_list += '\n%s' % team_data[8]
                embed.add_field(name='GM', value=team_data[1], inline=False)
                embed.add_field(name='Captains', value=captain_list)
                embed.add_field(name='Committee', value=committee_list)
                embed.add_field(name='Awards', value=awards_list)
                break
    elif team[5] == 'milr':
        appointments = sheets.read_sheet(sheet_id, assets.calc_cell['milr_appointments'])
        for team_data in appointments:
            if team_data[0] == team_abbr:
                teams = 'None'
                if len(team_data) >= 3:
                    if team_data[2]:
                        teams = team_data[2]
                if len(team_data) >= 4:
                    if team_data[3]:
                        teams += ', %s' % team_data[3]
                embed.add_field(name='MLR Team(s)', value=teams)
                embed.add_field(name='GM', value=team_data[1], inline=False)
                captains = 'None'
                if len(team_data) >= 5:
                    if team_data[4]:
                        captains = team_data[4]
                if len(team_data) >= 6:
                    if team_data[5]:
                        captains += '\n%s' % team_data[5]
                if len(team_data) >= 7:
                    if team_data[6]:
                        captains += '\n%s' % team_data[6]
                embed.add_field(name='Captains', value=captains)
                break

    if team[4]:
        embed.add_field(name='Result Webhook', value='Enabled', inline=True)
    else:
        embed.add_field(name='Result Webhook', value='Disabled', inline=True)

    if park:
        park = park[0]
        park_factors = '```HR: %s\n3B: %s\n2B: %s\n1B: %s\nBB: %s```' % (park[2], park[3], park[4], park[5], park[6])
        embed.add_field(name='Park', value=park[1], inline=False)
        embed.add_field(name='Park Factors', value=park_factors, inline=False)

    return embed


def scoreboard(league, season, session):
    sql = '''SELECT awayTeam, awayScore, homeTeam, homeScore, inning, outs, obc, complete FROM gameData WHERE league=%s AND season=%s AND session=%s ORDER BY awayTeam'''
    games = db.fetch_data(sql, (league, season, session))
    if games:
        scoreboard_txt = ''
        for game in games:
            away_team, away_score, home_team, home_score, inning, outs, obc, complete = game
            if away_team is None:
                continue
            b1 = '○'
            b2 = '○'
            b3 = '○'
            if obc in [1, 4, 5, 7]:
                b1 = '●'
            if obc in [2, 4, 6, 7]:
                b2 = '●'
            if obc in [3, 5, 6, 7]:
                b3 = '●'
            if 'T' in inning:
                inning = '▲' + inning[1]
            else:
                inning = '▼' + inning[1]
            if complete:
                scoreboard_txt += '```%3s %2s           Final\n' % (away_team, away_score)
                scoreboard_txt += '%3s %2s                \r\n\r\n```' % (home_team, home_score)
            else:
                scoreboard_txt += '```%3s %2s     %s       %s\n' % (away_team, away_score, b2, inning)
                scoreboard_txt += '%3s %2s   %s   %s   %s out\r\n\r\n```' % (home_team, home_score, b3, b1, outs)
            scoreboard_txt += ''
        scoreboard_txt += ''
        return scoreboard_txt
    return '--'
