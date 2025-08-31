#!/usr/bin/env python3

import html
import json
import os
import re
import sys
import time

from collections import defaultdict
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

class TgDump(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_cache = {}
        self.id_map = defaultdict(list)
        self.earliest = 99999999999
        self.latest = 0

    def check_timestamp(self, msg):
        try:
            if "timestamp" in msg:
                if msg["timestamp"] < self.earliest:
                    self.earliest = msg["timestamp"]
                if msg["timestamp"] > self.latest:
                    self.latest = msg["timestamp"]
        except Exception as e:
            pass
            #print("Bad timestamp in message, ignoring")
            #print(msg)
            #print(self.earliest)
            #print(self.latest)

    def update_earliest_and_latest(self):
        for msg in self.values():
            self.check_timestamp(msg)

    def has_link(self, _id):
        if _id not in self:
            return False
        msg = self[_id]
        if "links" not in msg:
            return False
        return len(msg["links"]) != 0

    def allfrom(self, from_name):
        if from_name not in self.from_cache:
            self.from_cache[from_name] = (msg for msg in self.values() if msg["from_name"] == from_name)
        return self.from_cache[from_name]

    def isnull(self, value):
        # the use case here is figuring out if one dump or another has a better value
        # so it should be fine to call 0 (or other type defaults) "null", as a non-default
        # value should always be preferable.
        if not value:
            return True
        if value in ["null", "Null", "NULL", "none", "None", "NONE"]:
            return True
        return False

    def merge(self, other_tgdump):
        """
        merge another tg dump into this one.
        only add data, do not lose anything.
        call this on an older dump with a newer one as its argument.
        when in doubt, new dump wins.
        """
        for msg_id, msg in other_tgdump.items():
            if msg_id not in self:
                self[msg_id] = msg
                continue
            for field, value in msg.items():
                if field not in self[msg_id]:
                    self[msg_id][field] = value
                    continue
                if self.isnull(value):
                    continue
                if self.isnull(self[msg_id][field]):
                    self[msg_id][field] = value
                else:
                    if self[msg_id][field] == value:
                        continue
                    if field == "from_name":
                        # always take an updated from_name, this needs to be consistent for the reports
                        if value == "Deleted Account":
                            # unless it's not their name any more
                            continue
                        self[msg_id]["from_name"] = value
                    else:
                        self[msg_id][field] = value
                        #raise Exception(f"Message id {msg_id} has conflicting values for field {field}. Ours is {self[msg_id][field]}, other is {value}")
        self.normalize_from_name()
        self.update_earliest_and_latest()

    def normalize_from_name(self):
        msg_ids = list(self.keys())
        msg_ids.sort(key=lambda x: 0 - x)
        for msg_id in msg_ids:
            msg = self[msg_id]
            if "from_id" not in msg:
                continue
            from_id = msg["from_id"]
            names = self.id_map[from_id]
            name = msg.get("from_name", None)
            if name and name not in names:
                names.append(name)
            # walking through the messages backwards, keep the last not-sucky name
            if names and names[0] and not self.isnull(names[0]) and names[0] != "Deleted Account":
                msg["from_name"] = names[0]

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

    The HTML dumps do not contain the from_id field, only from_name, but
    the message IDs are consistent. Dumps can be merged by messsage ID.
    I think.
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
            if "date_unixtime" in message:
                msg["timestamp"] = int(message["date_unixtime"])
                messages.check_timestamp(msg)
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
        self.messages.normalize_from_name()
        return (messages, actions)

"""
In reply to <a href="#go_to_message286750" onclick="return GoToMessage(286750)">this message</a>\n', 'id': '286751'}
"""


class TgHtmlParser(object):
    div_re = re.compile(r'(\w+)="(.*?)"')
    message_link_re = re.compile(r'onclick="return GoToMessage\((.*?)\)"')
    mention_re = re.compile(r'ShowMentionName\(\)">(.*?)</a>')
    href_re = re.compile(r"<a href.*?>(.*?)</a>")

    def __init__(self, directory):
        self.dump_dir = directory
        self.html_parser = HTML2Text()

    def __call__(self):
        return self.parse()

    def parse(self, dump_dir=None):
        dump_dir = dump_dir or self.dump_dir
        messages = TgDump()
        if dump_dir:
            for filename in os.listdir(dump_dir):
                if filename.startswith("messages") and filename.endswith(".html"):
                    with open(os.path.join(dump_dir, filename), "r") as MESSAGES:
                        messages.update(self.parse_messages(MESSAGES.readlines()))
            self.messages = messages
        return (messages, [])

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
            msg["text"] = self.href_re.sub("<1>", msg["text"])
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

        wait_for_new = True
        for line in lines:
            if "</div" in line:
                target = None
            elif "<div" in line:
                div = self.parse_div_line(line)
                target = None
                if div["class"].startswith("message default clearfix"):
                    # new message.  if we were building an old message, save it.
                    wait_for_new = False
                    if msg["id"]:
                        if msg["timestamp"] is None:
                            msg["timestamp"] = messages[-1]["timestamp"] # HACK
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
                    msg["id"] = int(div["id"].replace("message",""))
                elif div["class"] == "forwarded body":
                    target = None
                    wait_for_new = True
                elif div["class"] == "from_name":
                    target = "from_name"
                elif div["class"] == "text":
                    target = "text"
                elif div["class"] == "pull_right date details":
                    msg["timestamp"] = div["title"]
                    try:
                        if 'UTC' in msg["timestamp"]:
                            msg["timestamp"] = time.mktime(time.strptime(msg["timestamp"], '%d.%m.%Y %H:%M:%S UTC%z'))
                        else:
                            msg["timestamp"] = time.mktime(time.strptime(msg["timestamp"], '%d.%m.%Y %H:%M:%S'))
                    except:
                        msg["timestamp"] = None
                elif div["class"] == "media_wrap clearfix":
                    target = "media"
                elif div["class"] == "reply_to details":
                    target = "reply_to"
            elif wait_for_new:
                continue
            elif target is not None:
                if target == "from_name":
                    if "<span" in line:
                        name, details = line.split(" ", 1)
                        line = name
                    try:
                        msg[target] = html.unescape(line.strip())
                    except:
                        msg[target] = line.strip()
                    target = None
                else:
                    msg[target] = msg[target] + line

        if msg["id"]:
            if msg["timestamp"] is None:
                msg["timestamp"] = messages[-1]["timestamp"] # HACK
            messages[msg["id"]] = self.post_process(msg)
        return messages

class TgDumpParser(object):
    def __init__(self, dump):
        self.parser = None
        if os.path.isdir(dump):
            self.parser = TgHtmlParser(dump)
        else:
            self.parser = TgJsonParser(dump)
        self.messages = TgDump()
        self.actions = []

    def __call__(self):
        self.messages, self.actions = self.parser()
        self.sanitize_messages()
        return (self.messages, self.actions)

    def sanitize_messages(self):
        for msg_id, msg in self.messages.items():
            if "timestamp" not in msg or not msg["timestamp"]:
                _id = msg_id - 1
                while _id in self.messages:
                    if "timestamp" in self.messages[_id] and self.messages[_id]["timestamp"]:
                        msg["timestamp"] = self.messages[_id]["timestamp"]
                        break
                    _id -= 1


if __name__ == "__main__":
    parser = TgDumpParser(sys.argv[1])
    print(len(parser()))
