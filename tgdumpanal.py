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
from datetime import datetime
from emoji import is_emoji
from functools import cache
from html2text import HTML2Text
from PIL import Image
from tgdump import TgDumpParser, TgDump
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

date_re = re.compile(r"[1-3][0-9]{3}-[0-9]{1,2}-[0-9]{1,2}")

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
    for msg in messages.allfrom(from_name):
        if msg["reply_to"]:
            for replied_to_msg in msg["reply_to"]:
                if replied_to_msg in messages:
                    replyee = messages[replied_to_msg]["from_name"]
                    replied_tos[replyee] += 1
                else:
                    replied_tos["Unknown"] += 1
    return replied_tos

def pretty_time(unixtime):
    return time.strftime('%d.%m.%Y %H:%M:%S UTC%z', time.gmtime(unixtime)),

def tg_time_range(messages):
    msgs = iter(messages.items())
    _id, first = next(msgs)
    earliest = first["timestamp"]
    latest = first["timestamp"]
    for _id, msg in msgs:
        earliest = min(earliest, msg["timestamp"])
        latest = max(latest, msg["timestamp"])
    return (
        earliest,
        latest,
    )


def tg_per_day(messages_dict):
    messages = list(messages_dict.values())
    messages.sort(key = lambda x: x["timestamp"])
    results = []
    earliest, latest = (messages[0]["timestamp"], messages[-1]["timestamp"])
    day = earliest - earliest % 86400 + 86400
    talkers = {}
    unique_talkers = set()
    for message in messages:
        if message["timestamp"] > day:
            results.append((day, talkers))
            day += 86400
            talkers = {}
        name = message["from_name"]
        unique_talkers.add(name)
        if name not in talkers:
            talkers[name] = 0
        talkers[name] += 1
    results.append((day, talkers))
    
    messages_total = 0
    daily_talkers_total = 0
    for idx, (day, talkers) in enumerate(results):
        messages_count = sum(talkers.values())
        messages_total += messages_count
        talkers_count = len(talkers)
        daily_talkers_total += talkers_count
        print(f"Day {idx}, {messages_count} messages from {talkers_count} talkers")

    print("Total messages: {}".format(len(messages)))
    print("Between {} and {}".format(pretty_time(earliest), pretty_time(latest)))
    print(f"Total unique talkers: {len(unique_talkers)}")
    print(f"Mean talkers per day: {daily_talkers_total / len(results):.1f}")
    print(f"Unique talkers: {unique_talkers}")


def tg_report(messages, args):
    '''
    Takes a dict of tg messages (key is the message id as a string,
    value is a dict of the message).
    Prints some analysis of those messages.
    '''

    if not messages:
        return

    print("Total messages: {}".format(len(messages)))
    print("Between {} and {}".format(*list(map(pretty_time, tg_time_range(messages)))))

    ##### Top talkers #####

    print()
    print("Top talkers:")

    talkers = defaultdict(int)
    shitposters = defaultdict(int)

    for msg in messages.values():
        if msg["from_name"] in [None, "None"]:
            continue
        talkers[msg["from_name"]] += 1
        if "media" in msg and msg["media"]:
            shitposters[msg["from_name"]] += 1

    for talker in top_n(talkers, args.topn):
        print("{}\t{}".format(talker[1], talker[0]))


    ##### Top repliers #####

    print()
    print("Top repliers to messages:")

    repliers = defaultdict(int)
    for msg in messages.values():
        if msg["reply_to"]:
            repliers[msg["from_name"]] += 1

    for replier in top_n(repliers, args.topn):
        repliees = top_n(find_replied_to(messages, replier[0]), args.topn)
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

    for replyee in top_n(replied_to, args.topn):
        print("{}\t{}".format(replyee[1], replyee[0]))


    ##### Top link poster #####

    print()
    print("Top link posters:")

    links = defaultdict(int)
    for _id, msg in messages.items():
        if messages.has_link(_id):
            links[msg["from_name"]] += 1

    for linkposter in top_n(links, args.topn):
        print("{}\t{}".format(linkposter[1], linkposter[0]))


    ##### Top media posters #####

    print()
    print("Top shitposters:")

    for shitposter in top_n(shitposters, args.topn):
        print("{}\t{}".format(shitposter[1], shitposter[0]))


def tg_word_cloud(messages, args, words=None):
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

    if not messages and not words:
        return

    if words:
        _words = []
        for word in words:
            word = word.strip(punctuation).replace('’', '\'')
            if word and word.lower() not in excluded_words and not is_emoji(word) and "://" not in word:
                _words.append(word)
        words = _words
    else:
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

    wc = WordCloud(max_words=args.wc_num, mask=mask, background_color=args.wc_background).generate(text)
    wc.to_file(args.wc)

def tg_nevertalkers(messages, actions):
    message_counts = defaultdict(int)
    for message in messages.values():
        if message["from_id"] is not None:
            message_counts[message["from_id"]] += 1
    joined_no_messages = []
    for action in actions:
        if action["action"] == "join_group_by_link" and action["actor_id"] not in message_counts:
            joined_no_messages.append({"actor": action["actor"], "actor_id": action["actor_id"], "date_unixtime": action["date_unixtime"]})
    for silent_joiner in joined_no_messages:
        print("Name: {}, ID: {}, last joined: {}".format(silent_joiner["actor"], silent_joiner["actor_id"], silent_joiner["date_unixtime"]))

def mk_epochtime(thedate):
    if date_re.match(thedate):
        return datetime.strptime(thedate, "%Y-%m-%d").timestamp()
    return int(thedate)

def parse_args():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--sources", default=[], nargs="+", help="One or more Telegram exports, either JSON results files or directories of HTML files")
    source.add_argument("--pickle", default=None, help="pickle file containing parsed messages")
    parser.add_argument("--write-pickle", default=None, help="specify a filename to write parsed messages to a pickle file")
    parser.add_argument("--report", default=False, action="store_true", help="print report")
    parser.add_argument("--perday", default=False, action="store_true", help="print data about talkers per day")
    parser.add_argument("--topn", default=20, type=int, help="Count of topN lists in report")
    parser.add_argument("--not_before", default=None, help="epoch timestamp of earliest desired message (or YYYY-MM-DD)", type=mk_epochtime)
    parser.add_argument("--not_after", default=None, help="epoch timestamp of latest desired message (or YYYY-MM-DD)", type=mk_epochtime)
    parser.add_argument("--dump", default=False, action="store_true", help="dump all messages to console")
    parser.add_argument("--dumpjson", default=False, action="store_true", help="dump messages in json format")
    parser.add_argument("--search", default=None, help="search regex for message dump")
    parser.add_argument("--wc", default=None, help="generate wordcloud and store in this PNG filename")
    parser.add_argument("--wc-mask", default=None, help="file containing image mask for wordcloud")
    parser.add_argument("--wc-exclude", default=None, help="file containing words to exclude from wordcloud, one per line")
    parser.add_argument("--wc-num", default=1000, type=int, help="number of words to include in wordcloud")
    parser.add_argument("--wc-background", default="white", help="wordcloud background color (default is white)")
    parser.add_argument("--words", default=[], nargs="*", help="Manually enter words for wordcloud")
    parser.add_argument("--relationship", default=[], nargs="*", help="Print a summary of the relationship between a set of users")
    parser.add_argument("--nevertalkers", default=False, action="store_true", help="Print a list of accounts that have never sent a message")
    return parser.parse_args()

def main():
    args = parse_args()
    dumps = []
    messages = TgDump()
    actions = []

    if not args.pickle and not args.sources:
        raise Exception("No data. Please specify one of: --pickle, --sources")

    if args.pickle:
        with open(args.pickle, "rb") as IMAPICKLEMORTY:
            messages = pickle.load(IMAPICKLEMORTY)
    else:
        for source in args.sources:
            _messages = None
            if os.path.isdir(source):
                if "result.json" in os.listdir(source):
                    _messages, _actions = TgDumpParser(os.path.join(source, "result.json"))()
                else:
                    _messages, _actions = TgDumpParser(source)()
            elif os.path.isfile(source):
                _messages, _actions = TgDumpParser(source)()
            if _messages:
                dumps.append(_messages)
                _actions.extend(_actions) # this is insufficient
            else:
                raise Exception(f"Invalid source: {source}")

    if not dumps:
        raise Exception(f"No usable sources in {args.sources}")

    dumps.sort(key=lambda x: str(dump.earliest) + str(dump.latest))

    for dump in dumps:
        messages.merge(dump)

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
        messages = TgDump((k, v) for (k, v) in messages.items() if indaterange(k))

    if args.nevertalkers:
        tg_nevertalkers(messages, actions)

    if args.dump:
        output = list(messages.values())
        output.sort(key = lambda msg: int(msg["id"]))
        if args.search is not None:
            search_re = re.compile(args.search)
            output = [msg for msg in output if search_re.search(str(msg))]
        if args.dumpjson:
            print(json.dumps(output))
        else:
            for msg in output:
                print(msg)

    if args.report:
        tg_report(messages, args)

    if args.perday:
        tg_per_day(messages)

    if args.wc:
        tg_word_cloud(messages, args, words=args.words)

    if args.relationship:
        tg_relationship(*args.relationship)

if __name__ == "__main__":
    main()


