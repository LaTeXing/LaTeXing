import sublime
import sublime_plugin

from .latexing import *
from .latexing.startup import ltx_plugin_loaded


def plugin_loaded():
    sublime.set_timeout(lambda: ltx_plugin_loaded(), 100)
