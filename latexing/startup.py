import sublime
import sublime_plugin

import os
import shutil

from .cache import cache
from .listener import LtxTexListener
from .progress import progress_function
from .tools import move_license


def ltx_plugin_loaded():
    # move username/license from sublime-settings to sublime-license
    move_license("LaTeXing")

    message = ["Caching Information...", "Finished Caching"]
    progress_function([cache, clean], message[0], message[1], on_load)


def clean():
    dir_path = os.path.join(sublime.packages_path(), "LaTeXing3")
    if os.path.isdir(dir_path):
        sublime.message_dialog("Please remove your old LaTeXing installation. Close Sublime Text and delete the following directory: %s!" % dir_path)

    file_path = os.path.join(sublime.installed_packages_path(), "LaTeXing3.sublime-package")
    if os.path.isfile(file_path):
        sublime.message_dialog("Please remove your old LaTeXing installation. Close Sublime Text and delete the following file: %s!" % file_path)

    dir_path = os.path.join(sublime.cache_path(), "LaTeXing3")
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)

    dir_path = os.path.join(sublime.cache_path(), "LaTeXing ST3")
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)


def on_load():
    LtxTexListener.on_load(None, sublime.active_window().active_view())
