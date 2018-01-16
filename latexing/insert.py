import sublime
import sublime_plugin

import os.path
import re
import webbrowser

from . import logger
from . import tools

log = logger.getLogger(__name__)


class LtxInsertSpecialSymbolsCommand(sublime_plugin.TextCommand):

    def run(self, edit, braket_source=False):
        log.debug("%s" % braket_source)

        view = self.view
        if view.is_dirty():
            view.settings().set("save_is_dirty", True)
            view.run_command('save')

        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        lineLeft = view.substr(sublime.Region(view.full_line(point).a, point))[::-1]
        lineRight = view.substr(sublime.Region(point, view.full_line(point).b))

        rexLeft = re.compile(r"^(?P<word>[%#&{}_<>\-=\.*\w\(\)\[\]\|]*)(?P<bs>\\+)?")
        rexRight = re.compile(r"^(?P<word>[%#&{}_<>\-=\.*\w]*)")

        exprLeft = rexLeft.search(lineLeft)
        exprRight = rexRight.search(lineRight)

        if braket_source:
            left = lineLeft[0] if lineLeft else ""
            right = lineRight[0] if lineRight else ""
        else:
            left = (re.sub(r"^\\\\", "", exprLeft.group("bs")) if exprLeft.group("bs") else "") + (exprLeft.group("word")[::-1] if exprLeft.group("word") else "")
            right = exprRight.group() if exprRight and braket_source else ""
            right = exprRight.group() if exprRight else ""

        point_left = point - len(left)
        point_right = point + len(right)

        word = left + right
        # print(left, right)
        # print(word)

        matched = {}
        for file_path in sorted(tools.find_resources("*.sublime-completions") + tools.find_resources("*.latexing-completions"), reverse=True):

            resource = tools.load_resource(file_path, scope=[], completions=[])
            score_selector = view.score_selector(point, resource["scope"])
            if score_selector or resource["scope"] == "string.other.math":
                for completion in resource["completions"]:
                    if "trigger" in completion:
                        if completion["trigger"] not in matched or matched[completion["trigger"]]["score"] < score_selector:
                            matched[completion["trigger"]] = {"score": score_selector, "scope": resource["scope"], "contents": completion["contents"]}

        values = [value["contents"] for key, value in matched.items()]
        values = sorted(values, key=len, reverse=True)
        rex = re.compile("|".join([re.escape(value) for value in values]))
        braket_pairs = {")": "(", "}": "{", ">": "<", "]": "["}

        # for key, value in matched.items():
        # 	print(key, value)
        #
        # print(word)

        # Check if whole word exist in lookup table
        if word in matched:
            match = matched[word]
            if match["scope"] == "string.other.math" and not view.score_selector(point, match["scope"]):
                match["contents"] = "$" + match["contents"] + "$0$"
            view.run_command("ltx_replace_region", {"region": (point_left, point_right), "string": match["contents"]})
        else:
            if word not in values:
                # If word cannot match completely and the source is not a breaket, we are just looking for everything on the left side
                if not braket_source:
                    word = left
                    point_right = point
                # Split by alrady transformed values
                word = rex.split(word)[-1]

                # Tranform the new word if available
                if word in matched:
                    match = matched[word]
                    if match["scope"] == "string.other.math" and not view.score_selector(point, match["scope"]):
                        match["contents"] = "$" + match["contents"] + "$0$"
                    view.run_command("ltx_replace_region", {"region": (point_right - len(word), point_right), "string": match["contents"]})

                # Search backwards over the word for replacing the first match
                else:
                    for i in range(1, len(word) + 1):
                        if word[-i:] in matched:
                            sub = word[-i:]
                            sub_prefix = word[-i - 1]
                            match = matched[sub]

                            if sub in braket_pairs and sub_prefix is braket_pairs[sub]:
                                match["contents"] = matched[word[-i - 1]]["contents"] + "$0" + match["contents"]
                                i += 1

                            if match["scope"] == "string.other.math" and not view.score_selector(point, match["scope"]):
                                match["contents"] = "$" + match["contents"] + "$0$"

                            view.run_command("ltx_replace_region", {"region": (point_right - i, point_right), "string": match["contents"]})
                            break


class LtxInsertTexSymbolCommand(sublime_plugin.TextCommand):

    def show_resources(self, resources, show_categories):
        if (show_categories):
            message = sorted(resources.keys())

            def on_done_quick_panel(i):
                if i >= 0:
                    key = message[i]
                    items = [[key] + item for item in resources[key]]
                    self.show_items(items)
            sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done_quick_panel), 0)
        else:
            items = []
            for key, value in resources.items():
                items += [[key] + item for item in value]
            self.show_items(items)

    def show_items(self, items):
        hotkey = "§" if sublime.platform() == "osx" else "`"
        items = sorted(items, key=lambda item: item[1].lower())
        message = [[item, "%s, Available Shortcut: %s%s" % (name, trigger, hotkey) if trigger else "%s, No Shortcut" % name] for name, item, trigger in items]

        # Insert hotkey at the very first position
        items = [[hotkey, hotkey, False]] + items
        message = [[hotkey, "Insert the hotkey %s" % hotkey]] + message

        def on_done_quick_panel(i):
            if i >= 0:
                self.view.run_command("ltx_insert_text", {"point": self.point, "string": items[i][1]})

        sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done_quick_panel), 0)

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit, hotkey_source=False):
        log.debug("%s" % hotkey_source)

        view = self.view
        if view.is_dirty():
            view.settings().set("save_is_dirty", True)
            view.run_command('save')

        settings = tools.load_settings("LaTeXing", symbols_in_category=True)
        self.point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        resources = {}
        for file_path in sorted(tools.find_resources("*.sublime-completions") + tools.find_resources("*.latexing-completions"), reverse=True):
            file_dir, file_name = os.path.split(file_path)
            file_name_root, file_name_ext = os.path.splitext(file_name)
            file_name_root = file_name_root[6:] if file_name_root.startswith("LaTeX ") else file_name_root

            resource = tools.load_resource(file_path, scope=[], completions=[])
            if self.view.match_selector(self.point, resource["scope"]):
                resources[file_name_root] = []
                for completion in resource["completions"]:
                    if "trigger" in completion:
                        resources[file_name_root] += [[completion["contents"], completion["trigger"]]]
                    else:
                        resources[file_name_root] += [[completion, None]]

        if not resources:
            sublime.status_message("No symbol available at the current scope.")
            return

        self.show_resources(resources, settings["symbols_in_category"] and len(resources) > 1)


class LtxLookupTexSymbolCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        webbrowser.open("http://detexify.kirelabs.org/classify.html")


class LtxMove(sublime_plugin.TextCommand):

    def run(self, edit, by, kind):
        point = self.view.sel()[0].a if self.view.sel()[0].a < self.view.sel()[0].b else self.view.sel()[0].b
        line = self.view.substr(sublime.Region(point, self.view.line(point).b))

        if by == "environment":
            expr = re.search(r"%s" % kind, line, re.IGNORECASE)
            if expr:
                self.view.sel().clear()
                self.view.sel().add(sublime.Region(point + expr.end()))
                self.view.show(point + expr.end())
