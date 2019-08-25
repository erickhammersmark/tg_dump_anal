#!/usr/bin/env python3

import argparse
import os
import numpy
import pickle
import re
import sys

from collections import defaultdict
from PIL import Image
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator

class TgDumpParser(object):
    div_re = re.compile(r'(\w+)="(.*?)"')
    message_link_re = re.compile(r'onclick="return GoToMessage\((.*)\)"')
    mention_re = re.compile(r'ShowMentionName\(\)">(.*)</a>')

    def __init__(self, directory=None):
        self.dump_dir = directory

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
                elif div["class"] == "media_wrap clearfix":
                    target = "media"
                elif div["class"] == "reply_to details":
                    target = "reply_to"
            elif target is not None:
                if target == "from_name":
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

def tg_report(messages):
    '''
    Takes a dict of tg messages (key is the message id as a string,
    value is a dict of the message).
    Prints some analysis of those messages.
    '''

    if not messages:
        return

    print("Total messages: {}".format(len(messages)))


    ##### Top talkers #####

    print()
    print("Top talkers:")

    talkers = defaultdict(int)

    for msg in messages.values():
        talkers[msg["from_name"]] += 1

    for talker in top_n(talkers, 10):
        print("{}\t{}".format(talker[1], talker[0]))


    ##### Top repliers #####

    print()
    print("Top repliers to messages:")

    repliers = defaultdict(int)
    for msg in messages.values():
        if msg["reply_to"]:
            repliers[msg["from_name"]] += 1

    for replier in top_n(repliers, 10):
        repliees = top_n(find_replied_to(messages, replier[0]), 10)
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

    for replyee in top_n(replied_to, 10):
        print("{}\t{}".format(replyee[1], replyee[0]))

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
            word = word.strip(punctuation)
            if word.lower() not in excluded_words:
                words.append(word)

    text = ' '.join(words)

    wc = WordCloud(max_words=args.wc_num, mask=mask, background_color="white").generate(text)
    wc.to_file(args.wc)

def parse_args():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--directory", default=".", help="directory containing message*.html")
    source.add_argument("--pickle", default=None, help="pickle file containing parsed messages")
    parser.add_argument("--write-pickle", default=None, help="specify a filename to write parsed messages to a pickle file")
    parser.add_argument("--report", default=False, action="store_true", help="print report")
    parser.add_argument("--dump", default=False, action="store_true", help="dump all messages to console")
    parser.add_argument("--wc", default=None, help="generate wordcloud and store in this PNG filename")
    parser.add_argument("--wc-mask", default=None, help="file containing image mask for wordcloud")
    parser.add_argument("--wc-exclude", default=None, help="file containing words to exclude from wordcloud, one per line")
    parser.add_argument("--wc-num", default=1000, type=int, help="number of words to include in wordcloud")
    return parser.parse_args()

def main():
    args = parse_args()
    messages = None
    if args.pickle:
        with open(args.pickle, "rb") as IMAPICKLEMORTY:
            messages = pickle.load(IMAPICKLEMORTY)
    else:
        parser = TgDumpParser(directory=args.directory)
        messages = parser.parse()
    if args.write_pickle:
        with open(args.write_pickle, "wb") as IMAPICKLEMORTY:
            pickle.dump(messages, IMAPICKLEMORTY)

    if not messages:
        print("No messages")
        sys.exit(1)

    if args.dump:
        ids = list(messages.keys())
        ids.sort(key = lambda id: int(id))
        for id in ids:
            print(messages[id])

    if args.report:
        tg_report(messages)

    if args.wc:
        tg_word_cloud(messages, args)

if __name__ == "__main__":
    main()


