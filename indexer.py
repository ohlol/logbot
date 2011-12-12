#!/usr/bin/env python
#
# Based on: https://gist.github.com/389875
#

import json, re
from redis import Redis

import fuzzy

dmeta = fuzzy.DMetaphone()

# get the Redis connection

r = Redis('localhost')

# Words which should not be indexed
STOP_WORDS = ('the', 'of', 'to', 'and', 'a', 'in', 'is', 'it', 'you', 'that')

# Do not index any words shorter than this
MIN_WORD_LENGTH = 3

# Consider these characters to be punctuation (they will be replaced with spaces prior to word extraction)
PUNCTUATION_CHARS = ".,;:!?@$%^&*()-<>[]{}\\|/`~'\""

# A redis key to store a list of metaphones present in this project
REDIS_KEY_METAPHONES = 'channel:%(channel_name)s:fulltext_search:metaphones'

# A redis key to store a list of message IDs which have the given metaphone within the given project
REDIS_KEY_METAPHONE = 'channel:%(channel_name)s:fulltext_search:metaphone:%(metaphone)s'

class FullTextIndex(object):
    """A class to provide full-text indexing functionality using Redis"""

    def __init__(self):
        self.punctuation_regex = re.compile(r"[%s]" % re.escape(PUNCTUATION_CHARS))
        super(FullTextIndex, self).__init__()

    def get_words_from_text(self, text):
        """Extract a list of words to index from the given text"""
        if not text:
            return []

        text = self.punctuation_regex.sub(' ', text)
        words = text.split()

        words = [word for word in text.split() if len(word) >= MIN_WORD_LENGTH and word.lower() not in STOP_WORDS]

        return words


    def index_message(self, message):
        """Extract content from the given message and add it to the index"""
        # TODO: Added message users to index
        words = self.get_words_from_text(message['body'])

        metaphones = self.get_metaphones(words)

        for metaphone in metaphones:
            self._link_message_and_metaphone(message, metaphone)


    def index_message_content(self, message, content):
        """Index a specific bit of message content"""
        words = self.get_words_from_text(content)
        metaphones = self.get_metaphones(words)

        for metaphone in metaphones:
            self._link_message_and_metaphone(message, metaphone)


    def _link_message_and_metaphone(self, message, metaphone):
        # Add the message to the metaphone key
        redis_key = REDIS_KEY_METAPHONE % {'channel_name': message['channel_name'], 'metaphone': metaphone}
        r.sadd(redis_key, message['message_id'])

        # Make sure we record that this project contains this metaphone
        redis_key = REDIS_KEY_METAPHONES % {'channel_name': message['channel_name']}
        r.sadd(redis_key, metaphone)

    def get_metaphones(self, words):
        """Get the metaphones for a given list of words"""
        metaphones = set()
        for word in words:
            try:
                metaphone = dmeta(word)
    
                if metaphone[0]:
                    metaphones.add(metaphone[0].strip())
                    if(metaphone[1]):
                        metaphones.add(metaphone[1].strip())
            except:
                pass
        return metaphones

    def reindex_channel(self, channel_name):
        """Reindex an entire channel, removing the existing index for the channel"""

        # Remove all the existing index data
        redis_key = REDIS_KEY_METAPHONES % {'channel_name': channel_name}
        channel_metaphones = r.smembers(redis_key)
        if channel_metaphones is None:
            channel_metaphones = []

        r.delete(redis_key)

        for channel_metaphone in channel_metaphones:
            r.delete(REDIS_KEY_METAPHONE % {'channel_name': channel_name, 'metaphone': channel_metaphone})

        # Now index each message
        messages = r.hgetall('channel:%s:messages' % channel_name)
        for message_id, message in messages.iteritems():
            message_data = json.loads(message)

            if 'message' in message_data.keys():
                formatted = {
                    'channel_name': channel_name,
                    'body': message_data['message'],
                    'message_id': message_id
                }
                self.index_message(formatted)

        return True

index = FullTextIndex()

for channel_name in r.smembers('channels'):
  index.reindex_channel(channel_name)
