import configparser
import os
from io import BytesIO

import discord
import requests
from dhooks import Webhook
from discord.ext import commands
import src.db_controller as db
import src.Cogs.player as p
import src.assets as assets
import src.sheets_reader as sheets
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

config = configparser.ConfigParser()
config.read('config.ini')
ump_admin = int(config['Discord']['ump_admin_role'])
league_ops_role = int(config['Discord']['league_ops_role'])
error_log = Webhook(config['Channels']['error_log_webhook'])
league_config = 'league.ini'
config_ini = 'config.ini'
loading_emote = '<a:baseball:872894282032365618>'


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        config = configparser.ConfigParser()
        config.read('config.ini')

    @commands.command(brief='Sets the webhook URL for team servers',
                      description='Adds a webhook URL into the database for results to get posted to different servers.'
                                  ' Accepts the abbreviated team name and the URL as arguments.')
    @commands.has_role(ump_admin)
    async def add_webhook(self, ctx, team, *, url):
        sql = '''UPDATE teamData SET webhook_url = %s WHERE abb=%s'''
        db.update_database(sql, (url, team.upper()))
        db_team = db.fetch_data('''SELECT * FROM teamData WHERE abb = %s''', (team,))
        if db_team[0][4] == url:
            await ctx.send('Webhook URL set successfully.')
        else:
            await ctx.send('Something went wrong.')

    @commands.command(brief='Add an upmire to the database',
                      description='Adds a discord user to the umpire table in the database. @ the discord user and then'
                            ' provide their player ID.\n\nNote: Tech role is required to use this command.')
    @commands.has_role(ump_admin)
    async def add_ump(self, ctx, member: discord.Member, player_id):
        player_id = int(player_id)
        sql = '''SELECT * FROM playerData WHERE playerID=%s'''
        player = db.fetch_data(sql, (int(player_id),))
        ump_data = (player[0][1], member.id, player_id)
        sql = '''INSERT INTO umpData(umpName, discordID, playerID) VALUES (%s, %s, %s)'''
        db.update_database(sql, ump_data)
        await ctx.send('%s added to ump database.' % member.display_name)

    @commands.has_role(league_ops_role)
    @commands.command(brief='',
                      description='')
    async def draft(self, ctx, draft_round, draft_pick, team, *, player_name):
        team_data = db.fetch_data('SELECT name, color, logo_url FROM teamData WHERE abb=%s', (team,))
        if not team_data:
            await ctx.send('Could not find team %s.' % team)
            return
        player = await p.get_player(ctx, player_name)
        if not player:
            return

        sheet_id = sheets.get_sheet_id(config['URLs']['fcb_roster'])
        player_stats = sheets.read_sheet(sheet_id, 'Player Stats')
        fcb_stats1 = ''
        fcb_stats2 = ''
        for stats in player_stats:
            if stats[0] == player[1]:
                if player[7] == 'P':
                    fcb_stats1 = '%s IP %s ERA' % (stats[44], stats[68])
                    fcb_stats2 = '%s WHIP %s DBF' % (stats[70], stats[77])
                else:
                    fcb_stats1 = '%s AVG %s OBP' % (stats[17], stats[18])
                    fcb_stats2 = '%s SLG %s DPA' % (stats[19], stats[38])

        image_size = (1920, 1080)
        font_name = 'arial.ttf'

        # Background
        response = requests.get(assets.stadium_image[team.upper()])
        img = Image.open(BytesIO(response.content)).convert('RGB')
        img = img.resize(image_size, Image.ANTIALIAS)
        overlay = Image.new(mode='RGB', size=image_size, color=ImageColor.getrgb('#%s' % team_data[0][1]))
        img = Image.blend(img, overlay, 0.2)
        overlay = Image.new(mode='RGB', size=image_size, color=(0, 0, 0))
        img = Image.blend(img, overlay, 0.7)
        img = ImageOps.expand(img, border=20, fill=(255, 255, 255))

        # Team Logo
        response = requests.get(team_data[0][2])
        logo = Image.open(BytesIO(response.content)).convert('RGBA')
        logo = logo.resize((200, 200), Image.ANTIALIAS)
        img.paste(logo, (75, image_size[1]-200-75), logo)

        draw_text = ImageDraw.Draw(img)
        team_font = ImageFont.truetype(font_name, 150)
        draft_font = ImageFont.truetype(font_name, 80)
        player_font = ImageFont.truetype(font_name, 225)
        position_font = ImageFont.truetype(font_name, 100)
        stats_font = ImageFont.truetype(font_name, 64)
        
        # Team Name
        text_size = draw_text.textsize(team_data[0][0], font=team_font)
        draw_text.text((((image_size[0]-text_size[0])/2)+10, 75+10), team_data[0][0], font=team_font, fill=(0, 0, 0))  # shadow
        draw_text.text(((image_size[0]-text_size[0])/2, 75), team_data[0][0], font=team_font, fill=ImageColor.getrgb('#%s' % team_data[0][1]), stroke_width=1, stroke_fill=(255, 255, 255))

        # Draft Round/Pick
        draft_round_pick = 'Round %s - Pick %s' % (draft_round, draft_pick)
        text_size = draw_text.textsize(draft_round_pick, font=draft_font)
        draw_text.text((((image_size[0]-text_size[0])/2)+5, 285+5), draft_round_pick, font=draft_font, fill=(0, 0, 0))
        draw_text.text((((image_size[0]-text_size[0])/2), 285), draft_round_pick, font=draft_font, fill=(255, 255, 255))

        # Player Name
        text_size = draw_text.textsize(player[1], font=player_font)
        while text_size[0] > (image_size[0] - 200):
            player_font = ImageFont.truetype("arial.ttf", player_font.size-20)
            text_size = draw_text.textsize(player[1], font=player_font)
        draw_text.text((((image_size[0] - text_size[0]) / 2) + 10, ((image_size[1] - text_size[1]) / 2) + 10), player[1], font=player_font, fill=(0, 0, 0))
        draw_text.text((((image_size[0] - text_size[0]) / 2), ((image_size[1] - text_size[1]) / 2)), player[1], font=player_font, fill=(255, 255, 255), stroke_width=5, stroke_fill=ImageColor.getrgb('#%s' % team_data[0][1]))

        # Positions
        positions = '%s %s' % (player[2], player[7])  # FCB Team, primary position
        if player[8]:
            positions += '/%s' % player[8]  # secondary position
        if player[9]:
            positions += '/%s' % player[9]  # tertiary position
        text_size = draw_text.textsize(positions, font=position_font)
        draw_text.text((((image_size[0] - text_size[0]) / 2)+10, 700+10), positions, font=position_font, fill=(0, 0, 0))
        draw_text.text((((image_size[0] - text_size[0]) / 2), 700), positions, font=position_font, fill=(255, 255, 255))

        # FCB Stats
        text_size = draw_text.textsize(fcb_stats1, font=stats_font)
        draw_text.text((((image_size[0] - text_size[0]) / 2) + 10, 850 + 10), fcb_stats1, font=stats_font, fill=(0, 0, 0))
        draw_text.text((((image_size[0] - text_size[0]) / 2), 850), fcb_stats1, font=stats_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=ImageColor.getrgb('#%s' % team_data[0][1]))
        text_size = draw_text.textsize(fcb_stats2, font=stats_font)
        draw_text.text((((image_size[0] - text_size[0]) / 2) + 10, 930 + 10), fcb_stats2, font=stats_font, fill=(0, 0, 0))
        draw_text.text((((image_size[0] - text_size[0]) / 2), 930), fcb_stats2, font=stats_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=ImageColor.getrgb('#%s' % team_data[0][1]))

        img.save('draft.jpg')
        file = discord.File('draft.jpg', filename='draft.jpg')
        await ctx.send(file=file)
        os.remove('draft.jpg')

    @commands.has_role(ump_admin)
    @commands.command()
    async def exit(self, ctx):
        await ctx.send("Bye")
        exit()

    @commands.command(brief='Gets discord IDs for players')
    @commands.has_role(ump_admin)
    async def get_discord_ids(self, ctx):
        await ctx.message.add_reaction(loading_emote)

        for guild in self.bot.guilds:
            for member in guild.members:
                user = db.fetch_data('''SELECT discordName, discordID FROM playerData WHERE discordName=%s''', (str(member),))
                if user:
                    user = user[0]
                    if not user[1]:
                        db.update_database('''UPDATE playerData SET discordID=%s WHERE discordName=%s''', (member.id, str(member)))
                        user = db.fetch_data('''SELECT discordName, discordID FROM playerData WHERE discordName=%s''', (str(member),))
                        if user[0][1]:
                            error_log.send('Added discord ID to database for <@%s>' % member.id)
                        else:
                            error_log.send('Failed to set user ID for <@%s>' % member.id)
        await ctx.send('Done.')

    @commands.command(brief='Removes a discord user as an umpire',
                      description='Adds a discord user to the umpire table in the database. @ the discord user as an '
                                  'argument.\n\nNote: Tech role is required to use this command.')
    @commands.has_role(ump_admin)
    async def remove_ump(self, ctx, member: discord.Member):
        sql = '''DELETE FROM umpData WHERE discordID=%s'''
        db.update_database(sql, (member.id,))
        await ctx.send('%s removed from ump database.' % member.display_name)

    @commands.command(brief='Removes a team\'s existing webhook URL',
                      description='Removes a webhook URL from the database.\n\nNote: Tech role is required to use this'
                                  ' command.')
    @commands.has_role(ump_admin)
    async def remove_webhook(self, ctx, team):
        sql = '''UPDATE teamData SET webhook_url = %s WHERE abb=%s'''
        db.update_database(sql, ('', team.upper()))
        db_team = db.fetch_data('''SELECT * FROM teamData WHERE abb = %s''', (team,))
        if db_team[0][4] == '':
            await ctx.send('Webhook URL reset successfully.')
        else:
            await ctx.send('Something went wrong.')

    @commands.command(brief='Set season number',
                      description='Set season number in the config.')
    @commands.has_role(ump_admin)
    async def set_season(self, ctx, league, season):
        write_config(league_config, league.upper(), 'season', season)
        sql = '''UPDATE seasonData SET season=%s WHERE league=%s'''
        db.update_database(sql, (season, league))
        await ctx.send('%s season set to %s.' % (league, read_config(league_config, league.upper(), 'season')))

    @commands.command(brief='Set session number',
                      description='Sets session number in the config.')
    @commands.has_role(ump_admin)
    async def set_session(self, ctx, league, session):
        write_config(league_config, league.upper(), 'session', session)
        sql = '''UPDATE seasonData SET session=%s WHERE league=%s'''
        db.update_database(sql, (session, league))
        await ctx.send('%s session set to %s.' % (league, read_config(league_config, league.upper(), 'session')))

    @commands.command(brief='Syncs the database to the backend sheet',
                      description='Syncs the database with the backend sheet',
                      aliases=['sync'])
    @commands.has_role(league_ops_role)
    async def sync_database(self, ctx):
        await ctx.message.add_reaction(loading_emote)
        # Update player appointments...
        # mlr_roster = read_config(config_ini, 'URLs', 'backend_sheet_id')
        # mlr_appointments = sheets.read_sheet(mlr_roster, assets.calc_cell['mlr_appointments'])
        # milr_appointments = sheets.read_sheet(mlr_roster, assets.calc_cell['milr_appointments'])
        # for team in mlr_appointments:
        #     cogm = ''
        #     captain1 = ''
        #     captain2 = ''
        #     captain3 = ''
        #     committee1 = ''
        #     committee2 = ''
        #     awards1 = ''
        #     awards2 = ''
        #     abb = team[0]
        #     gm = team[1]
        #     if len(team) >= 3:
        #         cogm_check = sheets.read_sheet(mlr_roster, '%s!I2' % abb)
        #         if cogm_check[0][0] == 'Co-GM:':
        #             cogm = team[2]
        #         else:
        #             captain1 = team[2]
        #     if len(team) >= 4:
        #         captain2 = team[3]
        #     if len(team) >= 5:
        #         captain3 = team[4]
        #     if len(team) >= 6:
        #         committee1 = team[5]
        #     if len(team) >= 7:
        #         committee2 = team[6]
        #     if len(team) >= 8:
        #         awards1 = team[7]
        #     if len(team) >= 9:
        #         awards2 = team[8]
        #     team_data = (gm, cogm, captain1, captain2, captain3, committee1, committee2, awards1, awards2, abb)
        #     sql = '''UPDATE teamData SET gm=%s, cogm=%s, captain1=%s, captain2=%s, captain3=%s, committee1=%s, committee2=%s, awards1=%s, awards2=%s WHERE abb=%s'''
        #     db.update_database(sql, team_data)
        # for team in milr_appointments:
        #     gm = ''
        #     cogm = ''
        #     captain1 = ''
        #     captain2 = ''
        #     captain3 = ''
        #     abb = team[0]
        #     if len(team) >= 2:
        #         gm = team[1]
        #     if len(team) >= 3:
        #         cogm = team[2]
        #     if len(team) >= 6:
        #         captain1 = team[5]
        #     if len(team) >= 7:
        #         captain2 = team[6]
        #     if len(team) >= 8:
        #         captain3 = team[7]
        #     team_data = (gm, cogm, captain1, captain2, captain3, abb)
        #     sql = '''UPDATE teamData SET gm=%s, cogm=%s, captain1=%s, captain2=%s, captain3=%s WHERE abb=%s'''
        #     db.update_database(sql, team_data)

        # Update Discord Username In the Backend Sheet based on the Discord ID
        sheet_id = read_config(config_ini, 'URLs', 'backend_sheet_id')
        rows = sheets.read_sheet(sheet_id, 'Player List Input')
        for i in range(len(rows)):
            row = rows[i]
            if row:
                if row[0] != 'Player ID':
                    discord_id = row[12]
                    if discord_id:
                        user = ctx.bot.get_user(int(discord_id))
                        if user:
                            discord_name = '%s#%s' % (user.name, user.discriminator)
                            if discord_name != row[11]:
                                sheets.update_sheet(sheet_id, 'Player List Input!L%s' % (i+1), discord_name)
                                error_log.send('Updated discord name in Player List Input for `%s` to `%s`' % (row, discord_name))

        # Sync playerData with backend player list
        rows = sheets.read_sheet(sheet_id, 'Player List')
        for row in rows:
            if row[0] != 'Player ID':
                player_id = int(row[0])
                player_name = row[1]
                team = row[2]
                batting_type = row[3]
                pitching_type = row[4]
                pitching_bonus = row[5]
                hand = row[6]
                pos1 = row[7]
                pos2 = row[8]
                pos3 = row[9]
                reddit_name = row[10]
                discord_name = row[11]
                status = int(row[13])
                pos_value = int(row[14])
                player_in_sheet = (player_name, team, batting_type, pitching_type, pitching_bonus, hand, pos1, pos2, pos3, reddit_name, discord_name, status, pos_value, player_id)
                sql = '''SELECT playerName, Team, batType, pitchType, pitchBonus, hand, priPos, secPos, tertPos, redditName, discordName, Status, posValue, playerID FROM playerData WHERE playerID = %s'''
                player_in_db = db.fetch_data(sql, (player_id,))
                if player_in_db:
                    player_in_db = player_in_db[0]
                else:
                    sql = '''INSERT INTO playerData (playerName, Team, batType, pitchType, pitchBonus, hand, priPos, secPos, tertPos, redditName, discordName, Status, posValue, playerID) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                    db.update_database(sql, player_in_sheet)
                    error_log.send(f'Added new player: `{player_in_sheet}`')
                    continue
                if player_in_db != player_in_sheet:
                    sql = '''UPDATE playerData SET playerName=%s, Team=%s, batType=%s, pitchType=%s, pitchBonus=%s, hand=%s, priPos=%s, secPos=%s, tertPos=%s, redditName=%s, discordName=%s, Status=%s, posValue=%s WHERE playerID=%s'''
                    db.update_database(sql, player_in_sheet)
                    error_log.send('Updated existing player from `%s` to `%s`' % (player_in_db, player_in_sheet))
        await ctx.message.remove_reaction(loading_emote, ctx.bot.user)
        await ctx.send('Done.')


async def setup(bot):
    await bot.add_cog(Admin(bot))


def read_config(filename, section, setting):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    return ini_file[section][setting]


def write_config(filename, section, setting, value):
    ini_file = configparser.ConfigParser()
    ini_file.read(filename)
    ini_file.set(section, setting, value)
    with open(filename, 'w') as configfile:
        ini_file.write(configfile)

