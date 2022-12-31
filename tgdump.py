#!/usr/bin/env python3

import html
import json
import os
import re
import sys

from collections import defaultdict
from emoji import is_emoji

"""
Accepts a path to messages.json or a path to a Telegram dump of HTML message files.
Returns a dict of messages keyed on message id. For example:
{
    "363180": {
        'from_name': 'c0ldbru',
        'timestamp': 1660682202.0,
        'text': 'really we just want to get <a href="https://t.me/pubkraal">@pubkraal</a> on there drinking with us again, and get <a href="" onclick="return ShowMentionName()">b1n/&lt;</a> onto our car this next time',
        'message_links': [],
        'mentions': ['b1n/<'],
        'media': '',
        'reply_to': ['363176'],
        'id': '363180'
    }
}
"""


"""
{'from_name': 'c0ldbru',
 'timestamp': 1660682202.0,
 'text': 'really we just want to get <a href="https://t.me/pubkraal">@pubkraal</a> on there drinking with us again, and get <a href="" onclick="return ShowMentionName()">b1n/&lt;</a> onto our car this next time',
 'message_links': [],
 'mentions': ['b1n/&lt;'],
 'media': '',
 'reply_to': ['363176'],
 'id': '363180'
}

from -> from_name
id -> id
date_unixtime -> timestamp
reply_to_message_id -> reply_to
text_entities->type:mention->text -> mentions
text->join+extract "text" from the dicts -> text
??? -> message_links
??? -> media

 {
   "id": 363180,
   "type": "message",
   "date": "2022-08-16T13:36:42",
   "date_unixtime": "1660682202",
   "from": "c0ldbru",
   "from_id": "user1927162607",
   "reply_to_message_id": 363176,
   "text": [
    "really we just want to get ",
    {
     "type": "mention",
     "text": "@pubkraal"
    },
    " on there drinking with us again, and get ",
    {
     "type": "mention_name",
     "text": "b1n/<",
     "user_id": 1898901504
    },
    " onto our car this next time"
   ],
   "text_entities": [
    {
     "type": "plain",
     "text": "really we just want to get "
    },
    {
     "type": "mention",
     "text": "@pubkraal"
    },
    {
     "type": "plain",
     "text": " on there drinking with us again, and get "
    },
    {
     "type": "mention_name",
     "text": "b1n/<",
     "user_id": 1898901504
    },
    {
     "type": "plain",
     "text": " onto our car this next time"
    }
   ]
  },


{'from_name': 'c0ldbru',
 'timestamp': 1660849435.0,
 'text': 'also,
 <a href="" onclick="return ShowMentionName()">Skyehopper</a> I seriously cannot get over how rad that art you made was. seriously thank you so much for bringing those!!',
 'message_links': [],
 'mentions': ['Skyehopper'],
 'media': '',
 'reply_to': [],
 'id': '364602'
}

{'from_name': 'c0ldbru',
 'timestamp': 1660875138.0,
 'text': 'lol oh it was so much better than the poop knife. You could tell that some people in the audience were absolutely not prepared for the glorious talk that <a href="" onclick="return ShowMentionName()">J9</a> was about to give',
 'message_links': [],
 'mentions': ['J9'],
 'media': '',
 'reply_to': [],
 'id': '364881'
}

{'from_name': 'Nikolaevarius',
 'timestamp': 1661007457.0,
 'text': '<a href="" onclick="return ShowMentionName()">null_exception</a> you start skipping meals and sleep yet',
 'message_links': [],
 'mentions': ['null_exception'],
 'media': '',
 'reply_to': [],
 'id': '365353'
}

"""

class TgJsonParser(object):
    """
    Returns a dict of messages similar to TgHtmlParser

    from -> from_name
    id -> id
    date_unixtime -> timestamp
    reply_to_message_id -> reply_to
    text_entities->type:mention->text -> mentions
    text->join+extract "text" from the dicts -> text
    ??? -> message_links
    ??? -> media
    """

    def __init__(self, filename):
        self.filename = filename

    def __call__(self):
        return self.parse()

    def parse(self):
        with open(self.filename, "r") as JSON:
            data = json.load(JSON)
        if "messages" not in data:
            raise Exception("Unable to load json data from {}".format(self.filename))
        messages = {}
        for message in data["messages"]:
            if "action" in message:
                continue
            msg = {
                "id": None,
                "from_name": None,
                "timestamp": None,
                "text": "",
                "message_links": [],
                "mentions": [],
                "media": "",
                "reply_to": ""
            }
            msg["id"] = message["id"]
            msg["timestamp"] = int(message["date_unixtime"])
            if "from" in message:
                msg["from_name"] = message["from"]
            if "reply_to_message_id" in message:
                msg["reply_to"] = [message["reply_to_message_id"]]
            if "media_type" in message:
                msg["media"] = message["media_type"]
            text = []
            if isinstance(message["text"], str):
                text = [message["text"]]
            else:
                for entry in message["text"]:
                    if isinstance(entry, dict):
                        text.append(entry["text"])
                        if "mention" in entry["type"]:
                            msg["mentions"].append(entry["text"])
                    else:
                        text.append(entry)
            msg["text"] = " ".join(text)

            messages[msg["id"]] = msg
        self.messages = messages
        return messages


class TgHtmlParser(object):
    div_re = re.compile(r'(\w+)="(.*?)"')
    message_link_re = re.compile(r'onclick="return GoToMessage\((.*)\)"')
    mention_re = re.compile(r'ShowMentionName\(\)">(.*)</a>')

    def __init__(self, directory):
        self.dump_dir = directory

    def __call__(self):
        return self.parse()

    def parse(self, dump_dir=None):
        dump_dir = dump_dir or self.dump_dir
        if not dump_dir:
            return {}
        messages = {}
        for filename in os.listdir(dump_dir):
            if filename.startswith("messages") and filename.endswith(".html"):
                with open(os.path.join(dump_dir, filename), "r") as MESSAGES:
                    messages.update(self.parse_messages(MESSAGES.readlines()))
        self.messages = messages
        return messages

    def parse_div_line(self, line):
        if not line:
            return {}
        matches = self.div_re.findall(line)
        return dict(matches)

    def post_process(self, msg):
        if msg["reply_to"]:
            matches = self.message_link_re.findall(msg["reply_to"])
            msg["reply_to"] = list(matches)
        else:
            msg["reply_to"] = []
        if msg["text"]:
            msg["text"] = msg["text"].strip()
            if '<a href="#go_to_message' in msg["text"]:
                matches = self.message_link_re.findall(msg["text"])
                msg["message_links"] = list(matches)
            if "ShowMentionName" in msg["text"]:
                matches = self.mention_re.findall(msg["text"])
                msg["mentions"] = list(matches)
        return msg

    def parse_messages(self, lines):
        messages = {}

        # eat everything before the html body
        while '<div class="body">' not in lines[0]:
            lines.pop(0)

        msg = {
            "id": None,
            "from_name": None,
            "timestamp": None,
            "text": "",
            "message_links": [],
            "mentions": [],
            "media": "",
            "reply_to": ""
        }

        # use 'target' to track what field we want to fill in with subsequent lines
        target = None

        for line in lines:
            if "</div" in line:
                target = None
            elif "<div" in line:
                div = self.parse_div_line(line)
                target = None
                if div["class"].startswith("message default clearfix"):
                    # new message.  if we were building an old message, save it.
                    if msg["id"]:
                        messages[msg["id"]] = self.post_process(msg)
                    from_name = None
                    if div["class"].endswith("joined"):
                        # class "message default clearfix joined" inherits
                        # from_name from the preceding message
                        from_name = msg["from_name"]
                    msg = {
                        "from_name": from_name,
                        "timestamp": None,
                        "text": "",
                        "message_links": [],
                        "mentions": [],
                        "media": "",
                        "reply_to": ""
                    }
                    msg["id"] = div["id"].replace("message","")
                elif div["class"] == "from_name":
                    target = "from_name"
                elif div["class"] == "text":
                    target = "text"
                elif div["class"] == "pull_right date details":
                    msg["timestamp"] = div["title"]
                    try:
                        msg["timestamp"] = time.mktime(time.strptime(msg["timestamp"], '%d.%m.%Y %H:%M:%S UTC%z'))
                    except:
                        pass
                elif div["class"] == "media_wrap clearfix":
                    target = "media"
                elif div["class"] == "reply_to details":
                    target = "reply_to"
            elif target is not None:
                if target == "from_name":
                    try:
                        msg[target] = html.unescape(line.strip())
                    except:
                        msg[target] = line.strip()
                    target = None
                else:
                    msg[target] = msg[target] + line

        messages[msg["id"]] = msg
        return messages

class TgDumpParser(object):
    def __init__(self, dump):
        self.parser = None
        if os.path.isdir(dump):
            self.parser = TgHtmlParser(dump)
        else:
            self.parser = TgJsonParser(dump)

    def __call__(self):
        return self.parser()

if __name__ == "__main__":
    parser = TgDumpParser("/home/bink/result.json")
    print(len(parser()))
