#!/usr/bin/env python3

import argparse
import html
import json
import numpy
import os
import pickle
import re
import sys
import time

from collections import defaultdict
from emoji import is_emoji
from html2text import HTML2Text
from PIL import Image
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator

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

href_re = re.compile(r"<a href.*?>(.*?)</a>")

class TgJsonParser(object):
    """
    Returns a dict of messages similar to TgDumpParser

    from -> from_name
    id -> id
    date_unixtime -> timestamp
    reply_to_message_id -> reply_to
    text_entities->type:mention->text -> mentions
    text->join+extract "text" from the dicts -> text
    ??? -> message_links
    ??? -> media
    """

    def __init__(self, filename="result.json"):
        self.filename = filename

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
            else:
                print(message)
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
        return messages


class TgDumpParser(object):
    div_re = re.compile(r'(\w+)="(.*?)"')
    message_link_re = re.compile(r'onclick="return GoToMessage\((.*)\)"')
    mention_re = re.compile(r'ShowMentionName\(\)">(.*)</a>')

    def __init__(self, directory=None):
        self.dump_dir = directory
        self.html_parser = HTML2Text()

    def parse(self, dump_dir=None):
        dump_dir = dump_dir or self.dump_dir
        if not dump_dir:
            return {}
        messages = {}
        for filename in os.listdir(dump_dir):
            if filename.startswith("messages") and filename.endswith(".html"):
                with open(os.path.join(dump_dir, filename), "r") as MESSAGES:
                    messages.update(self.parse_messages(MESSAGES.readlines()))
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
            self.html_parser.reset()
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

        messages[msg["id"]] = msg
        return messages


def top_n(dct, n):
    '''
    Takes a dict and a count.
    Returns a sorted list of tuples of the top n entries in
    the dict, where the sorting key is the dict value.
    '''
    sorted_list_of_tuples = sorted(dct.items(), key = lambda foo: foo[1])
    if n == 1:
        return [sorted_list_of_tuples[-1]]
    return sorted_list_of_tuples[-1 * n :]

def find_replied_to(messages, from_name):
    '''
    Given a dict of tg messages and a name, returns a dict
    of { name: count } of all of the people to which that name
    has replied.
    '''
    replied_tos = defaultdict(int)
    for msg in messages.values():
        if msg["from_name"] == from_name and msg["reply_to"]:
            for replied_to_msg in msg["reply_to"]:
                if replied_to_msg in messages:
                    replyee = messages[replied_to_msg]["from_name"]
                    replied_tos[replyee] += 1
                else:
                    replied_tos["Unknown"] += 1
    return replied_tos

def tg_time_range(messages):
    msgs = iter(messages.items())
    _id, first = next(msgs)
    earliest = first["timestamp"]
    latest = first["timestamp"]
    for _id, msg in msgs:
        earliest = min(earliest, msg["timestamp"])
        latest = max(latest, msg["timestamp"])
    return (
        time.strftime('%d.%m.%Y %H:%M:%S UTC%z', time.gmtime(earliest)),
        time.strftime('%d.%m.%Y %H:%M:%S UTC%z', time.gmtime(latest))
    )

def tg_report(messages):
    '''
    Takes a dict of tg messages (key is the message id as a string,
    value is a dict of the message).
    Prints some analysis of those messages.
    '''

    if not messages:
        return

    print("Total messages: {}".format(len(messages)))
    print("Between {} and {}".format(*tg_time_range(messages)))

    ##### Top talkers #####

    print()
    print("Top talkers:")

    talkers = defaultdict(int)
    shitposters = defaultdict(int)

    for msg in messages.values():
        talkers[msg["from_name"]] += 1
        if "media" in msg and msg["media"]:
            shitposters[msg["from_name"]] += 1

    for talker in top_n(talkers, 20):
        print("{}\t{}".format(talker[1], talker[0]))


    ##### Top repliers #####

    print()
    print("Top repliers to messages:")

    repliers = defaultdict(int)
    for msg in messages.values():
        if msg["reply_to"]:
            repliers[msg["from_name"]] += 1

    for replier in top_n(repliers, 20):
        repliees = top_n(find_replied_to(messages, replier[0]), 20)
        replyee = repliees[-1]
        print("{}\t{} (most replies was {} to {})".format(
            replier[1],
            replier[0],
            replyee[1],
            replyee[0]
        ))


    ##### Top replied to #####

    print()
    print("Top people replied to:")

    replied_to = defaultdict(int)

    for msg in messages.values():
        for replied_to_message in msg["reply_to"]:
            if replied_to_message in messages:
                replied_to[messages[replied_to_message]["from_name"]] += 1

    for replyee in top_n(replied_to, 20):
        print("{}\t{}".format(replyee[1], replyee[0]))


    ##### Top media posters #####

    print()
    print("Top shitposters:")

    for shitposter in top_n(shitposters, 20):
        print("{}\t{}".format(shitposter[1], shitposter[0]))


def tg_word_cloud(messages, args):
    html_tag_re = re.compile(r"<.*?>")
    html_escape_re = re.compile(r"&.*?;")

    punctuation = ",.:;!()&@/?=+"

    mask = None
    if args.wc_mask:
        mask = numpy.array(Image.open(args.wc_mask))

    excluded_words = set()
    if args.wc_exclude:
        with open(args.wc_exclude, "r") as EXCLUDE:
            for line in EXCLUDE.readlines():
                excluded_words.add(line.strip())
                excluded_words.add(line.strip().replace("'", ""))

    if not messages:
        return

    words = []
    for msg in messages.values():
        if not msg["text"]:
            continue
        for word in html_escape_re.subn("", html_tag_re.subn("", msg["text"])[0])[0].split():
            word = word.strip(punctuation).replace('’', '\'')
            if word and word.lower() not in excluded_words and not is_emoji(word) and "://" not in word:
                words.append(word)
    
    topwords = defaultdict(int)
    for word in words:
        topwords[word] += 1
    print(top_n(topwords, 100))

    text = ' '.join(words)

    wc = WordCloud(max_words=args.wc_num, mask=mask, background_color="white").generate(text)
    wc.to_file(args.wc)

def parse_args():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--json", default=None, help="json dump of tg chat")
    source.add_argument("--directory", default=".", help="directory containing message*.html")
    source.add_argument("--directories", default=None, help="specify multiple telegram chat export directories")
    source.add_argument("--pickle", default=None, help="pickle file containing parsed messages")
    parser.add_argument("--write-pickle", default=None, help="specify a filename to write parsed messages to a pickle file")
    parser.add_argument("--report", default=False, action="store_true", help="print report")
    parser.add_argument("--not_before", default=None, type=int, help="unix timestamp of earliest desired message")
    parser.add_argument("--not_after", default=None, type=int, help="unix timestamp of latest desired message")
    parser.add_argument("--dump", default=False, action="store_true", help="dump all messages to console")
    parser.add_argument("--search", default=None, help="search regex for message dump")
    parser.add_argument("--wc", default=None, help="generate wordcloud and store in this PNG filename")
    parser.add_argument("--wc-mask", default=None, help="file containing image mask for wordcloud")
    parser.add_argument("--wc-exclude", default=None, help="file containing words to exclude from wordcloud, one per line")
    parser.add_argument("--wc-num", default=1000, type=int, help="number of words to include in wordcloud")
    return parser.parse_args()

def main():
    args = parse_args()
    messages = {}
    if args.pickle:
        with open(args.pickle, "rb") as IMAPICKLEMORTY:
            messages = pickle.load(IMAPICKLEMORTY)
    elif args.json:
        messages.update(TgJsonParser(args.json).parse())
    else:
        if args.directories:
            directories = args.directories
        else:
            directories = [args.directory]

        for directory in directories:
            messages.update(TgDumpParser(directory=directory).parse())

    if args.write_pickle:
        with open(args.write_pickle, "wb") as IMAPICKLEMORTY:
            pickle.dump(messages, IMAPICKLEMORTY)

    if not messages:
        print("No messages")
        sys.exit(1)

    if args.not_before or args.not_after:
        def indaterange(msg):
            if args.not_before and messages[msg]["timestamp"] < args.not_before:
                return False
            if args.not_after and messages[msg]["timestamp"] > args.not_after:
                return False
            return True
        messages = dict((k, v) for (k, v) in messages.items() if indaterange(k))

    if args.dump:
        ids = list(messages.keys())
        ids.sort(key = lambda id: int(id))
        if args.search is not None:
            search_re = re.compile(args.search)
            for id in ids:
                _str = str(messages[id])
                if search_re.search(_str):
                    print(_str)
        else:
            for id in ids:
                print(messages[id])

    if args.report:
        tg_report(messages)

    if args.wc:
        tg_word_cloud(messages, args)

if __name__ == "__main__":
    main()


