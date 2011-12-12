#!/usr/bin/env python
"""
   LogBot

   A minimal IRC log bot

   Written by Chris Oliver

   Includes python-irclib from http://python-irclib.sourceforge.net/

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA   02111-1307, USA.
"""


__author__ = "Chris Oliver <excid3@gmail.com>"
__version__ = "0.4.1"
__date__ = "08/11/2009"
__copyright__ = "Copyright (c) Chris Oliver"
__license__ = "GPL2"


import json, time
from redis import Redis

from ircbot import SingleServerIRCBot
from irclib import nm_to_n

### Configuration options
DEBUG = False
REDIS_SERVER = 'localhost'
SERVER = 'localhost'
PORT = 6667
SERVER_PASS = None
CHANNELS=['#hello']
NICK = 'Logbot'
NICK_PASS = ''

HELP_MESSAGE = 'Check out http://excid3.com'

redis = Redis(REDIS_SERVER)

default_format = {
    'help' : HELP_MESSAGE
}

class Logbot(SingleServerIRCBot):
    def __init__(self, server, port, server_pass=None, channels=[],
                 nick='timber', nick_pass=None, format=default_format):
        SingleServerIRCBot.__init__(self,
                                    [(server, port, server_pass)],
                                    nick,
                                    nick)

        self.chans = [x.lower() for x in channels]
        self.format = format
        self.nick_pass = nick_pass

        print 'Logbot %s' % __version__
        print 'Connecting to %s:%i...' % (server, port)
        print 'Press Ctrl-C to quit'

    def quit(self):
        self.connection.disconnect('Quitting...')

    def write_event(self, name, event, params={}):
        now = time.time()
        chans = event.target()

        msg = {
            'host': event.source(),
            'source': nm_to_n(event.source()),
            'time': now,
            'action': name
        }

        if event.arguments():
          msg['message'] = event.arguments()[0]

        if params:
          msg['params'] = params

        message_id = redis.incr('message_ids')

        # Quit goes across all channels
        if not chans or not chans.startswith('#'):
            chans = self.chans
        else:
            chans = [chans]

        for chan in chans:
            redis.sadd('channels', chan)
            redis.sadd('channel:%s:dates' % chan, time.strftime('%F', time.gmtime(now)));
            redis.hset('channel:%s:messages' % chan, message_id, json.dumps(msg))

    def on_all_raw_messages(self, c, e):
        """Display all IRC connections in terminal"""
        if DEBUG: print e.arguments()[0]

    def on_welcome(self, c, e):
        """Join channels after successful connection"""
        if self.nick_pass:
            c.privmsg('nickserv', 'identify %s' % self.nick_pass)

        for chan in self.chans:
            c.join(chan)

    def on_nicknameinuse(self, c, e):
        """Nickname in use"""
        c.nick(c.get_nickname() + '_')

    def on_invite(self, c, e):
        """Arbitrarily join any channel invited to"""
        c.join(e.arguments()[0])

    ### Loggable events

    def on_action(self, c, e):
        """Someone says /me"""
        self.write_event('action', e)

    def on_join(self, c, e):
        self.write_event('join', e)

    def on_kick(self, c, e):
        self.write_event('kick', e,
                         {'kicker': e.source(),
                          'channel': e.target(),
                          'user': e.arguments()[0],
                          'reason': e.arguments()[1],
                         })

    def on_mode(self, c, e):
        self.write_event('mode', e,
                         {'modes': e.arguments()[0],
                          'person': e.arguments()[1] if len(e.arguments()) > 1 else e.target(),
                          'giver': nm_to_n(e.source()),
                         })

    def on_nick(self, c, e):
        self.write_event('nick', e,
                         {'old': nm_to_n(e.source()),
                          'new': e.target(),
                         })

    def on_part(self, c, e):
        self.write_event('part', e)

    def on_pubmsg(self, c, e):
        if e.arguments()[0].startswith(NICK):
            c.privmsg(e.target(), self.format['help'])
        self.write_event('pubmsg', e)

    def on_pubnotice(self, c, e):
        self.write_event('pubnotice', e)

    def on_privmsg(self, c, e):
        c.privmsg(nm_to_n(e.source()), self.format['help'])

    def on_quit(self, c, e):
        self.write_event('quit', e)

    def on_topic(self, c, e):
        self.write_event('topic', e)

def main():
    # Start the bot
    bot = Logbot(SERVER, PORT, SERVER_PASS, CHANNELS, NICK, NICK_PASS)
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.quit()

if __name__ == '__main__':
    main()
