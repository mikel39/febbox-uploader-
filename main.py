import asyncio
import json
import sys

from febbox import Febbox

config = json.load(open('config.json'))
dir = sys.argv[1]
try:
    rdir = sys.argv[2]
except IndexError:
    rdir = ''


febbox = Febbox(config['ui'], config['remove_after'])
asyncio.run(febbox.upload_folder(dir, rdir))
