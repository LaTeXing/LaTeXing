import sublime
import sublime_plugin

import json
import os.path

from . import cache
from . import tools


class LtxOpenPhrasesDictionaryCommand(sublime_plugin.WindowCommand):

    def is_enabled(self):
        return True if tools.list_dir(os.path.join(sublime.packages_path(), "User"), ["*.latexing-phrases"]) else False

    def run(self, **args):
        items = tools.list_dir(os.path.join(sublime.packages_path(), "User"), ["*.latexing-phrases"])
        message = [[item["file_name"], os.path.join("User", item["rel_path"])] for item in items]

        def on_done(i):
            if i >= 0:
                if not os.path.exists(items[i]["full_path"]):
                    sublime.error_message("Unable to open %s" % items[i]["full_path"])
                else:
                    self.window.open_file(items[i]["full_path"])
                    sublime.status_message("Open %s" % items[i]["full_path"])

        self.window.show_quick_panel(message, on_done)


class LtxSavePhrasesCommand(sublime_plugin.TextCommand):

    def choose_dictionary(self, items, words):
        def on_done(i):
            if i >= 0:
                self.fill_dictionary(items[i], words)
        self.view.window().show_quick_panel(items, on_done)

    def fill_dictionary(self, file_name, words):
        try:
            with open(os.path.join(sublime.packages_path(), "User", file_name), 'r', encoding='utf-8') as f:
                dic_data = json.load(f)
        except:
            dic_data = []

        words = [word for word in words if word not in dic_data]
        dic_data += [word for word in words]

        if words:
            sublime.status_message("Added [%s] in %s" % (",".join(words), file_name))
        else:
            sublime.status_message("All words already exist in %s" % file_name)

        with open(os.path.join(sublime.packages_path(), "User", file_name), 'w', encoding='utf-8') as f:
            json.dump(dic_data, f, ensure_ascii=False)

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):

        tex_file = cache.TeXFile(self.view.file_name())
        tex_file.run()

        user_phrases = tex_file.get_option("phrases")
        if not user_phrases:
            sublime.status_message("No dictionary sepecified!")
            return

        words = []
        for sel in self.view.sel():
            word = self.view.substr(sublime.Region(sel.a, sel.b)).strip()
            if len(word) > 0 and word not in words:
                words += [word]

        if not words:
            return

        items = ["%s.latexing-phrases" % item.strip() for item in user_phrases.split(",")]

        if len(items) > 1:
            self.choose_dictionary(items, words)
        else:
            self.fill_dictionary(items[0], words)
