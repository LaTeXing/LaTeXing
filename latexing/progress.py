import sublime
import sublime_plugin

import functools
import threading


class ThreadThread(threading.Thread):

    def __init__(self, function):
        self.function = function if isinstance(function, list) else [function]
        threading.Thread.__init__(self)

    def run(self):
        for function in self.function:
            function()


def progress_function(function, message, message_done, callback):
    t = ThreadThread(function)
    t.start()
    Progress(t, message, message_done, callback)


class Progress():

    def __init__(self, thread, message, message_done, callback):
        self.thread = thread
        self.message = message
        self.message_done = message_done
        self.callback = callback
        self.add = 1
        self.size = 8
        sublime.set_timeout(lambda: self.run(0), 100)

    def run(self, i):
        if not self.thread.is_alive():
            sublime.status_message(self.message_done)
            sublime.set_timeout(functools.partial(self.callback), 0)
            return

        before = i % self.size
        after = self.size - (before + 1)

        if not after:
            self.add = -1
        elif not before:
            self.add = 1

        sublime.status_message('%s [%s=%s]' % (self.message, ' ' * before, ' ' * after))
        sublime.set_timeout(lambda: self.run(i + self.add), 100)
