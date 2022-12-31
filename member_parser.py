#!/usr/bin/env python3

import sys
from html.parser import HTMLParser

class MemberParser(HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.members = {}
        self.member = {}

    def handle_starttag(self, tag, attrs):
        try:
            _attrs = dict(attrs)        
        except:
            _attrs = {}
            for item in attrs:
                if len(item) == 2:
                    _attrs[item[0]] = item[1]

        print("start", tag, _attrs)

    def handle_endtag(self, tag):
        print("end", tag)
        pass

    def handle_data(self, data):
        print("data", data)
        pass

parser = MemberParser()

with open(sys.argv[1], "r") as MBR:
  while parser.feed(MBR.read()):
    pass




"""
start ul [('class', 'chatlist')]
start a [('class', 'chatlist-chat'), ('data-peer-id', '755154397')]
start avatar-element [('class', 'dialog-avatar avatar-48 avatar-relative'), ('data-peer-id', '755154397'), ('dir', 'auto'), ('data-color', '')]
start img [('class', 'avatar-photo'), ('src', 'blob:https://web.telegram.org/b4af3c41-f741-42b5-8b6f-981a4127dc78')]
end avatar-element
start div [('class', 'user-caption')]
start p [('class', 'dialog-title')]
start span [('class', 'user-title tgico')]
start span [('class', 'peer-title'), ('dir', 'auto'), ('data-peer-id', '755154397'), ('data-from-name', '0'), ('data-dialog', '0'), ('data-only-first-name', '0'), ('data-plain-text', '0'), ('data-with-icons', '1')]
data Diar Sanakov
end span
end span
start span [('class', 'dialog-title-details')]
start span [('class', 'message-status sending-status')]
end span
start span [('class', 'message-time')]
end span
end span
end p
start p [('class', 'dialog-subtitle')]
start span [('class', 'user-last-message'), ('dir', 'auto')]
start span [('class', 'i18n')]
data online
end span
end span
end p
end div
end a
start a [('class', 'chatlist-chat'), ('data-peer-id', '129417192')]
start avatar-element [('class', 'dialog-avatar avatar-48 avatar-relative'), ('data-peer-id', '129417192'), ('dir', 'auto'), ('data-color', '')]
start img [('class', 'avatar-photo'), ('src', 'blob:https://web.telegram.org/0fa2834e-2498-4d78-b5a9-60d747bfe3a4')]
end avatar-element
start div [('class', 'user-caption')]
start p [('class', 'dialog-title')]
start span [('class', 'user-title tgico')]
start span [('class', 'peer-title with-icons'), ('dir', 'auto'), ('data-peer-id', '129417192'), ('data-from-name', '0'), ('data-dialog', '0'), ('data-only-first-name', '0'), ('data-plain-text', '0'), ('data-with-icons', '1')]
start span [('class', 'peer-title-inner'), ('dir', 'auto')]
data Kay Fox
start img [('src', 'assets/img/emoji/1f3f3-200d-1f308.png'), ('class', 'emoji'), ('alt', '🏳️\u200d🌈')]
end span
start span [('class', 'premium-icon tgico-star')]
end span
end span
end span
start span [('class', 'dialog-title-details')]
start span [('class', 'message-status sending-status')]
end span
start span [('class', 'message-time')]
end span
end span
end p
start p [('class', 'dialog-subtitle')]
start span [('class', 'user-last-message'), ('dir', 'auto')]
start span [('class', 'i18n')]
data online
end span
end span
end p
end div
end a
start a [('class', 'chatlist-chat'), ('data-peer-id', '5482705203')]
"""
