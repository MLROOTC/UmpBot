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

    @commands.command(brief='Gets discord IDs for players')
    @commands.has_role(ump_admin)
    async def get_discord_ids(self, ctx):
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


def setup(bot):
    bot.add_cog(Admin(bot))
