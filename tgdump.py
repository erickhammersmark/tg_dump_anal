#!/usr/bin/env python3

import html
import json
import os
import re
import sys

from html2text import HTML2Text

"""
TgDumpParser accepts a path to a single JSON file or a path to a directory
containing a Telegram dump of HTML message files.  Calling the instance
returns a dict of messages keyed on message id. For example:

{
    id: str: {
        from_name: str,
        timestamp: float,
        text: str,
        message_links: [str],
        mentions: [str],
        media: str,
        reply_to: [str],
        id: str
    }
}

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

href_re = re.compile(r"<a href.*?>(.*?)</a>")

class TgDump(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.from_cache = {}

    def has_link(self, _id):
        if _id not in self:
            return False
        msg = self[_id]
        return len(msg["links"]) != 0

    def allfrom(self, from_name):
        if from_name not in self.from_cache:
            self.from_cache[from_name] = (msg for msg in self.values() if msg["from_name"] == from_name)
        return self.from_cache[from_name]

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
        messages = TgDump()
        actions = []
        for message in data["messages"]:
            if "action" in message:
                actions.append(message)
            msg = {
                "id": None,
                "from_name": None,
                "from_id": None,
                "timestamp": None,
                "text": "",
                "message_links": [],
                "links": [],
                "mentions": [],
                "media": "",
                "reply_to": ""
            }
            msg["id"] = message["id"]
            msg["timestamp"] = int(message["date_unixtime"])
            if "from" in message:
                msg["from_name"] = message["from"]
            if "from_id" in message:
                msg["from_id"] = message["from_id"]
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
                        if "link" in entry["type"]:
                            msg["links"].append(entry["text"])
                    else:
                        text.append(entry)
            msg["text"] = " ".join(text)

            messages[msg["id"]] = msg
        self.messages = messages
        return (messages, actions)

"""
In reply to <a href="#go_to_message286750" onclick="return GoToMessage(286750)">this message</a>\n', 'id': '286751'}
"""


class TgHtmlParser(object):
    div_re = re.compile(r'(\w+)="(.*?)"')
    message_link_re = re.compile(r'onclick="return GoToMessage\((.*?)\)"')
    mention_re = re.compile(r'ShowMentionName\(\)">(.*?)</a>')

    def __init__(self, directory):
        self.dump_dir = directory
        self.html_parser = HTML2Text()

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
            msg["text"] = href_re.sub("\g<1>", msg["text"])
            self.html_parser.feed(msg["text"])
            try:
                msg["text"] = self.html_parser.finish().strip()
            except Exception as e:
                print("Unable to parse html {}".format(e))
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

        if msg["id"]:
            messages[msg["id"]] = self.post_process(msg)
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
    parser = TgDumpParser(sys.argv[1])
    print(len(parser()))
