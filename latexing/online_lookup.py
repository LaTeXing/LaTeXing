import sublime
import sublime_plugin

import urllib
import webbrowser

from . import tools


class LtxOnlineLookupCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def show_quick_panel(self, argument):
        if argument:
            message = [["Enter Different Lookup Phrase", "Use the sublime inpout panel to enter a different lookup phrase"]]
            message += [[item["title"], item["url"] % argument if "%s" in item["url"] else item["url"].format(query=argument)] for item in self.settings["online_lookup"]]
        else:
            message = None
            sublime.status_message("No word selected! Asking for lookup phrase.")
            self.show_input_panel()

        def on_done_quick_panel(i):
            if i == 0:
                self.show_input_panel()
            elif i > 0:
                tools.LtxSettings().set("ltx_online_lookup", message[i][0])
                webbrowser.open(message[i][1])

        last_title = tools.LtxSettings().get("ltx_online_lookup", None)
        selected_index = [item[0] for item in message].index(last_title) if last_title else 0

        if message:
            self.view.window().show_quick_panel(message, on_done_quick_panel, 0, selected_index)

    def show_input_panel(self):
        def on_done_input_panel(s):
            self.show_quick_panel(urllib.parse.quote(s))
        self.view.window().show_input_panel("Lookup Argument:", "", on_done_input_panel, None, None)

    def run(self, edit):
        view = self.view

        a = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b
        b = view.sel()[0].b if view.sel()[0].a < view.sel()[0].b else view.sel()[0].a

        # no argument while beeing in the border of a word
        if a == b and (a == view.word(a).a or b == view.word(b).b):
            argument = None
        else:
            argument = view.substr(sublime.Region(view.word(a).a, view.word(b).b)).strip(" ,{}()[]\n\t\r")
            argument = urllib.parse.quote(argument)

        self.settings = tools.load_settings("LaTeXing", online_lookup={})
        self.show_quick_panel(argument)
