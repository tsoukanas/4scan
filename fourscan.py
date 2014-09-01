#!/usr/bin/python
import gevent, gevent.monkey, gevent.lock
gevent.monkey.patch_all()

import os
import re
import yaml

import fourchan
from requests.exceptions import ConnectionError

class Scan(object):
    def __init__(self, config):
        self.load_config(config)

    def load_config(self, config):
        self.description = config.get("description")
        self.topics_only = config.get("topics_only", True)
        self.boards = set(config["boards"].strip().split())
        self.keyterms = [term.lower() for term in config.get("terms", [])]
        self.keywords = [word.lower() for word in config.get("words", [])]

        if self.keywords:
            self.keyword_search = re.compile(r"\b(%s)\b" % "|".join(self.keywords)).search
        else:
            self.keyword_search = lambda _: None

    def search_hit(self, msg):
        if not msg:
            return False
        msg = msg.lower()

        return (any(term in msg for term in self.keyterms)
                or self.keyword_search(msg))

    def match(self, board, thread):
        if board.name not in self.boards:
            return False

        posts = [thread.topic] if self.topics_only else thread.posts

        for post in posts:
            if self.search_hit(post.body):
                return post

        return None


class Scanner(object):
    def __init__(self, config=None, error_handler=None):
        if not config:
            path = os.path.abspath(os.path.dirname(__file__))
            config = path + "/config.yaml"

        self.error_handler = error_handler or (lambda *args, **kwargs: None)
        self.load_config(config)
        self.watched_threads = set()
        self.matched_threads = set()
        self.callback_lock = gevent.lock.BoundedSemaphore()

    @property
    def watch_count(self):
        return len(self.watched_threads)

    def load_config(self, path):
        with open(path) as f:
            config = yaml.load(f)

        self.conf = conf = {}

        # Check only topic OP instead of all thread posts.
        conf["TOPICS_ONLY"] = True

        # How long before re-checking boards, in minutes.
        conf["RECHECK_DELAY"] = config.get("recheck_delay", 3)

        # Replace HTML tags in post bodies with plaintext equivalents.
        conf["CLEAN_COMMENTS"] = config.get("clean_comments", True)

        conf["BOARDS"] = set()

        self.scans = []

        for scan_config in config.get("scans"):
            scan = Scan(scan_config)
            if not scan.topics_only:
                conf["TOPICS_ONLY"] = False
            conf["BOARDS"] |= scan.boards
            self.scans.append(scan)

    def get_thread_uid(self, thread):
        return "%s/%d" % (thread.board.name, thread.id)

    def watching_thread(self, thread):
        return self.get_thread_uid(thread) in self.watched_threads

    def watch_thread(self, thread):
        self.watched_threads.add(self.get_thread_uid(thread))

    def add_matched_thread(self, thread):
        self.matched_threads.add(self.get_thread_uid(thread))

    def already_matched(self, thread):
        return self.get_thread_uid(thread) in self.matched_threads

    def scan_match(self, board, thread):
        if self.already_matched(thread):
            return None

        for scan in self.scans:
            if scan.topics_only and self.watching_thread(thread):
                continue

            match = scan.match(board, thread)
            if match:
                self.add_matched_thread(thread)
                return match, scan

        return None

    def run_callback(self, callback, post, scan, async=True):
        """
        Set `async` to False to ensure only one callback ever runs at once.
        """
        if async:
            self.watch_thread(post.thread)
            gevent.spawn(callback, post, scan)

        else:
            with self.callback_lock:
                self.watch_thread(post.thread)
                callback(post, scan)

    def grab_threads(self, board):
        try:
            return board.get_all_threads(expand=not self.conf["TOPICS_ONLY"])
        except ConnectionError as e:
            self.error_handler(board=board, exception=e)
            return []

    def grab_board_threads(self, board, callback, async=True):
        while True:
            for thread in self.grab_threads(board):
                scan_match = self.scan_match(board, thread)
                if scan_match:
                    post, scan = scan_match
                    self.run_callback(callback, post, scan, async)

            gevent.sleep(self.conf["RECHECK_DELAY"] * 60)

    def find_threads(self, callback, async=True):
        boards = fourchan.get_boards(self.conf["BOARDS"], clean_comments=self.conf["CLEAN_COMMENTS"])
        for board in boards:
            gevent.spawn(self.grab_board_threads, board, callback, async)
            gevent.sleep(8) # So all the requests won't be sent at once

    def scan(self, callback, async=True):
        return gevent.spawn(self.find_threads, callback, async)

def scan(config=None, callback=None, error_handler=None, async=True):
    scanner = Scanner(config, error_handler)
    scanner.scan(callback, async)
    return scanner

def run_forever():
    gevent.wait()

def scan_forever(*args, **kwargs):
    scan(*args, **kwargs)
    run_forever()
