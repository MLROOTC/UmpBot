import db_controller as db
import reddit_interface as reddit


async def get_pitch(bot, player_id, league, season, session, game_id):
    discord_id, reddit_name = db.fetch_one('''SELECT discordID, redditName FROM playerData WHERE playerID=%s''', (player_id,))
    if discord_id:
        def wait_for_pitch(msg):
            return msg.author == pitcher and msg.guild is None and msg.content.isnumeric() and int(
                msg.content) > 0 and int(msg.content) <= 1000

        pitcher = bot.get_user(discord_id)
        pitch_request_msg = await pitcher.send('Gib pitch')
        db.update_database('''UPDATE gameData SET pitch_requested=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (pitch_request_msg.created_at, league, season, session, game_id))

        pitch_msg = await bot.wait_for('message', check=wait_for_pitch)
        sql = '''UPDATE gameData SET pitch=aes_encrypt(%s,%s), pitch_src=%s, pitch_submitted=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
        db.update_database(sql, (int(pitch_msg.content), pitch_msg.id, pitch_msg.id, pitch_msg.created_at, league, season, session, game_id))
        await pitch_msg.add_reaction('👍')
    else:
        print('send a reddit DM')
    return


def decrypt_pitch(league, season, session, game_id):
    pitch_src = db.fetch_one('''SELECT pitch_src FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', (league, season, session, game_id))
    sql = f'''SELECT CAST(aes_decrypt(pitch, "{pitch_src[0]}") as char) FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
    decrypted_pitch = db.fetch_one(sql, (league, season, session, game_id))
    return int(decrypted_pitch[0])


def time_to_pitch(league, season, session, game_id):
    sql = '''SELECT pitch_requested, pitch_submitted FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
    pitch_requested, pitch_submitted = db.fetch_one(sql, (league, season, session, game_id))
    if pitch_requested and pitch_submitted:
        return pitch_submitted - pitch_requested
    return None


async def get_swing(reddit_comment_url):
    swing_comment = await reddit.get_comment(reddit_comment_url)
    numbers_in_comment = [int(i) for i in swing_comment.body.split() if i.isdigit()]
    if len(numbers_in_comment) == 1:
        swing = numbers_in_comment[0]
        if 0 < swing <= 1000:
            await swing_comment.reply(f'Found a valid swing: {swing}')
    elif len(numbers_in_comment) == 0:
        await swing_comment.reply('I couldnt find a valid number in your swing. Please reply to the original at-bat ping with a number between 1 and 1000 without any decimal spaces.')
    else:
        await swing_comment.reply('I found too many numbers in your swing. Please reply to the original AB ping with only one number included in your swing.')
    return

