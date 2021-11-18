import asyncio
import discord
from discord.ext import commands, tasks
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime, timedelta
import json
import random
import shelve
import requests
import re
#import logging

#logging.basicConfig(level=logging.INFO)


ANSWER_CHOICES = ["A", "B", "C", "D", "E", "F", "G", "H"]
TEST_BANK_JSON = open('/root/rocketBot/test.json', encoding="utf8")
TEST_BANK = json.load(TEST_BANK_JSON)
DB = shelve.open('/root/rocketBot/database', writeback=True)

TOKEN = '¯\_(ツ)_/¯'
### TEST
# SERVER = 893858035955560478
# QUESTION_CHANNEL = 893858133234032681
# STOCK_CHANNEL = 894251066487627787
# STOCK_ROLE = 895400454966607902

### PROD
SERVER = 723644976638066845
QUESTION_CHANNEL = 895315342262427719
STOCK_CHANNEL = 723671000750751854
STOCK_ROLE = 895391825903386635

bot = discord.Client()


def generate_question_message(question_id, include_answer=False):
    """ Generates a markdown formatted message for a given question, optionally with answer

    param question_id: question number in the test bank for which to generate the message
    param include_answer: set to true to include a (spoilered) answer in the message

    returns: the markdown formatted message
    """

    global TEST_BANK
    question = TEST_BANK[question_id]

    response = ""
    if not include_answer:
        response += "**Question of the Day:**"
    else:
        response += "**Question**:"

    response += "\n> " + question["content"]

    response += "\n> "

    for i in range(int(question["num_answers"])):
        response += "\n> **" + ANSWER_CHOICES[i] + ".** " + question[ANSWER_CHOICES[i]]

    response += "\nSource: " + question["source"]

    if include_answer:
        response += "\nAnswer:  ||" + question["answer"] + "||"
        response += "\nExplanation: ||" + question["explanation"] + "||"
    else:
        response += "\n DM me your answer choice, the correct answer will be revealed here soon."
        response += "  You can also DM me '!question' at any time for extra practice."

    return response


def generate_answer_message(question_id) -> str:
    """ Generates a markdown formatted message for the answer of yesterday's question.
    Generates an answer distribution from the database's collected answers and saves it to 'answer_distribution.png'

    param question_id: question number in the test bank for which to generate the message

    returns: the markdown formatted message
    """
    question = TEST_BANK[question_id]
    response = "The correct answer was: **" + question["answer"] + ".** " + question[question["answer"]]
    response += "\n**Explanation:** " + question["explanation"]

    # Plot
    fig = plt.figure()
    plt.gca().yaxis.set_major_locator(ticker.NullLocator())
    plt.title("Answer Distribution")
    plt.bar(DB["collected_answers"].keys(), DB["collected_answers"].values())
    for index, value in enumerate(DB["collected_answers"].values()):
        plt.text(index, value+0.02, str(value), ha='center')
    plt.savefig('answer_distribution.png')

    return response


def process_answer(answer_choice):
    """Increments the count of answer_choice in the database"""
    DB["collected_answers"][answer_choice] += 1
    DB.sync()


def daily_update():
    """Daily update function - picks a new question and resets the collected answers counts"""
    if "remaining_questions" not in DB or len(DB["remaining_questions"]) is 0:
        DB["remaining_questions"] = [*range(1, len(TEST_BANK))]

    # Pick new question
    question_id = random.choice(DB["remaining_questions"])
    DB["remaining_questions"].remove(question_id)
    DB['todays_question'] = str(question_id)

    # Build empty answers entry
    answers = {}
    for i in range(0, TEST_BANK[str(question_id)]["num_answers"]):
        answers[ANSWER_CHOICES[i]] = 0

    DB["collected_answers"] = answers
    DB["users_who_answered"] = []
    DB.sync()

async def auto_react(message):
    """Auto reacts on message content"""
    # Emma no sorry
    if message.author.id == 621107119781052426 and isinstance(message.channel, discord.abc.GuildChannel) \
            and re.search(r'\bsorry\b', message.content.lower()):
        emoji = bot.get_emoji(873442529297723413)
        await message.add_reaction(emoji)

    if re.search(r'\bduel deploy\b', message.content.lower()):
        emoji = '⚔'
        await message.add_reaction(emoji)

    if re.search(r'\bope\b', message.content.lower()):
        emoji = bot.get_emoji(751215601229234237)
        await message.add_reaction(emoji)

    if re.search(r'\bmabey\b', message.content.lower()):
        emoji = bot.get_emoji(873043099578953758)
        await message.add_reaction(emoji)

    if re.search(r'\bcheep\b', message.content.lower()):
        emoji = '🐦'
        await message.add_reaction(emoji)

    if re.search(r'\bking of random\b', message.content.lower()) or re.search(r'\btkor\b', message.content.lower()) \
            or (re.search(r'\bfirst rocket\b', message.content.lower()) and re.search(r'\bliquid\b', message.content.lower())):
        emoji = '🚩'
        await message.add_reaction(emoji)

@bot.event
async def on_message(message):
    """Async callback run on every message the bot sees"""
    await auto_react(message)

    # Private DMs
    if isinstance(message.channel, discord.abc.PrivateChannel) and message.author.id != bot.user.id:
        # Give random question with hidden answer
        if message.content.lower().startswith("!question"):
            response = generate_question_message(str(random.randint(1, len(TEST_BANK))), include_answer=True)
            await message.channel.send(response)

        # Process answer for the day's question
        elif message.author.id not in DB['users_who_answered'] \
                and message.content.upper().replace('"', '').replace('\'', '')[0] \
                in ANSWER_CHOICES[0:len(DB['collected_answers'])]:
            process_answer(message.content.upper()[0])
            DB["users_who_answered"].append(message.author.id)
            DB.sync()
            await message.channel.send('Answer recorded, check the server later for the correct answer!')



@bot.event
async def on_ready():
    """Callback run when bot is ready, sets discord activity"""
    activity = discord.Activity(name='with Mach Diamonds', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)

    print('Logged in as:')
    print(bot.user.name)


@tasks.loop(hours=24)
async def post_question():
    """Daily task to generate and send new message"""
    server = bot.get_guild(SERVER)
    channel = server.get_channel(QUESTION_CHANNEL)
    daily_update()

    question_msg = generate_question_message(DB['todays_question'])
    await channel.send(question_msg)


@tasks.loop(hours=24)
async def post_answer():
    """Daily task to generate and send answer of yesterday's question"""
    server = bot.get_guild(SERVER)
    channel = server.get_channel(QUESTION_CHANNEL)

    response = generate_answer_message(DB['todays_question'])
    await channel.send(file=discord.File('answer_distribution.png'))
    await channel.send(response)


@tasks.loop(seconds=15)
async def check_slcf_stock():
    """Task to check if SLCF is in stock.  Active while SLCF is OUT of stock, sending a message once it becomes IN
    stock """
    await bot.wait_until_ready()

    url = 'https://www.perfectflitedirect.com/stratologgercf-altimeter/'
    slcf_obj = requests.get(url)

    if 'Out of Stock' not in slcf_obj.text and '<div class="Label QuantityInput" style="display: ">Quantity:</div>' in slcf_obj.text:
        server = bot.get_guild(SERVER)
        channel = server.get_channel(STOCK_CHANNEL)
        role = server.get_role(STOCK_ROLE)

        response = "\nStratoLogger CF is back in stock!"
        response += "\nLink: https://www.perfectflitedirect.com/stratologgercf-altimeter/"

        # Send message, start the out of stock task, cancel this task
        await channel.send(role.mention + response)
        check_slcf_oostock.start()
        check_slcf_stock.cancel()


@tasks.loop(seconds=15)
async def check_slcf_oostock():
    """Task to check if SLCF is out of stock.  Active while SLCF is IN stock, sending a message once it becomes OUT
    of stock """
    url = 'https://www.perfectflitedirect.com/stratologgercf-altimeter/'
    slcf_obj = requests.get(url)

    with open('test.html') as f:
        lines = f.readlines();
        f.close()

    if 'Out of Stock' in slcf_obj.text:
        server = bot.get_guild(SERVER)
        channel = server.get_channel(STOCK_CHANNEL)

        response = "\nStratoLogger CF is out of stock again :("
        response += "\nI will ping stonk watchers once it is in stock again."

        # Send message, start the out of stock task, cancel this task
        await channel.send(response)
        check_slcf_stock.cancel()
        check_slcf_oostock.start()


@tasks.loop(seconds=15)
async def check_fsm_stock():
    await bot.wait_until_ready()

    url = 'https://flightsketch.com/store/catalog/flightsketch-mini_1/'
    fsm_obj = requests.get(url)

    if 'alert_form' not in fsm_obj.text:
        server = bot.get_guild(SERVER)
        channel = server.get_channel(STOCK_CHANNEL)
        role = server.get_role(STOCK_ROLE)

        response = "\nFLightSketch Mini is back in stock!"
        response += "\nLink: https://flightsketch.com/store/catalog/flightsketch-mini_1/"
        response += "\nMuting FlightSketch Mini stock notifications for 1 day."

        await channel.send(role.mention + response)
        await asyncio.sleep(24 * 60 * 60)


@post_question.before_loop
async def before_post_question():
    hour = 16
    minute = 15
    await bot.wait_until_ready()
    now = datetime.now()
    future = datetime(now.year, now.month, now.day, hour, minute)
    if now.hour >= hour and now.minute > minute:
        future += timedelta(days=1)
    await asyncio.sleep((future - now).seconds)


@post_answer.before_loop
async def before_post_answer():
    hour = 16
    minute = 0
    await bot.wait_until_ready()
    now = datetime.now()
    future = datetime(now.year, now.month, now.day, hour, minute)
    if now.hour >= hour and now.minute > minute:
        future += timedelta(days=1)
    await asyncio.sleep((future - now).seconds)

post_question.start()
post_answer.start()
check_slcf_stock.start()
# check_fsm_stock.start()
generate_answer_message(DB['todays_question'])
bot.run(TOKEN)
