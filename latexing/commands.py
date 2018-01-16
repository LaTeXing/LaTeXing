import sublime
import sublime_plugin

import os
import re
import subprocess
import webbrowser

from . import LTX_VERSION
from . import cache
from . import logger
from . import progress
from . import terminal
from . import tools

log = logger.getLogger(__name__)


class LtxFoldEnvironmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        settings = tools.load_settings("LaTeXing", foldable_environments=["table", "figure", "equation"])

        environment = None
        stack = tools.find_unclosed_environments(view.substr(sublime.Region(0, point)))
        for s in stack[::-1]:
            if s in settings["foldable_environments"]:
                environment = s
                break

        if environment:
            dicEnvironment = tools.find_environment_range(view, point, environment)
            view.fold(sublime.Region(view.line(dicEnvironment["start"]).b, view.line(dicEnvironment["end"]).a - 1))
            view.sel().clear()
            view.sel().add(view.line(dicEnvironment["end"]).b)
        else:
            view.run_command("fold")


class LtxFoldSectionCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):

        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        dicEnvironment = tools.find_section_range(view, point)
        if dicEnvironment:
            view.fold(sublime.Region(view.line(dicEnvironment["start"]).b, dicEnvironment["end"]))
            view.sel().clear()
            view.sel().add(view.line(dicEnvironment["end"]).b + 1)


class LtxInsertLatexEnvironmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        log.debug(self)

        view = self.view
        view.run_command("insert_snippet", {"name": "Packages/LaTeXing/snippets/wrapper/environment.sublime-snippet"})


class LtxLatexCommandCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        log.debug(self)

        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        # Find word on the left
        left = view.substr(sublime.Region(view.line(point).a, point))[::-1]
        right = view.substr(sublime.Region(point, view.line(point).b))

        offset_left = re.search(r"([^\s\{]*)\s?\{?", left).end(1) if re.search(r"([^\s\{]*)\s?\{?", left) else 0
        offset_right = re.search(r"([^\s\{]*)", right).end(1) if re.search(r"([^\s\{]*)", right) else 0

        command_region = sublime.Region(point - offset_left, point + offset_right)
        command = view.substr(command_region)

        # Delete old word
        view.erase(edit, command_region)

        snippet = "\\\\" + command + "{$1} $0"
        view.run_command("insert_snippet", {'contents': snippet})


class LtxLatexEnvironmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        log.debug(self)

        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        # Find word on the left
        left = view.substr(sublime.Region(view.line(point).a, point))[::-1]
        right = view.substr(sublime.Region(point, view.line(point).b))

        offset_left = re.search(r"([^\s\{]*)\s?\{?", left).end(1) if re.search(r"([^\s\{]*)\s?\{?", left) else 0
        offset_right = re.search(r"([^\s\{]*)", right).end(1) if re.search(r"([^\s\{]*)", right) else 0

        environment_region = sublime.Region(point - offset_left, point + offset_right)
        environment = view.substr(environment_region)

        # Delete old word
        view.erase(edit, environment_region)

        snippet = "\\\\begin{" + environment + "}\n$1\n\\\\end{" + environment + "}$0"
        view.run_command("insert_snippet", {'contents': snippet})


class LtxRenameLatexEnvironmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        environment = None
        stack = tools.find_unclosed_environments(view.substr(sublime.Region(0, point)))
        for s in stack[::-1]:
            environment = s
            break

        if environment:
            dicEnvironment = tools.find_environment_range(view, point, environment)

            view.sel().clear()
            view.sel().add(sublime.Region(dicEnvironment["start"] + 7, dicEnvironment["start"] + 7 + len(environment)))
            view.sel().add(sublime.Region(dicEnvironment["end"] - 1 - len(environment), dicEnvironment["end"] - 1))


class LtxRenameLabelCommand():

    def __init__(self, view):
        self.view = view

    def run(self, argument):
        log.debug(argument)

        if not argument:
            return

        tex_file = cache.TeXFile(self.view.file_name())
        tex_file.run()

        source_name = argument
        items = []
        for file_path, item in tex_file.get("ref"):
            if item["arguments"][0].split(":", 1)[1] == argument:
                items += [[file_path, item]]

        # Add label at last item to be selected at the end
        items += [[tex_file.file_path, {"tag": "\\label{%s}" % source_name}]]

        def on_done_input_panel(s):
            if s and s != source_name:
                for file_name, item in items:
                    view = self.view.window().open_file(file_name)
                    tools.replace_text_in_view(view, item["tag"], item["tag"].replace(source_name, s))

        self.view.window().show_input_panel("New Name:", source_name, on_done_input_panel, None, None)


class LtxStarLatexEnvironmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        view = self.view
        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b

        environment = None
        stack = tools.find_unclosed_environments(view.substr(sublime.Region(0, point)))
        for s in stack[::-1]:
            environment = s
            break

        if environment:
            dicEnvironment = tools.find_environment_range(view, point, environment)

            # Check if environment is already stared
            if environment[-1] == "*":
                view.erase(edit, sublime.Region(dicEnvironment["end"] - 2, dicEnvironment["end"] - 1))
                view.erase(edit, sublime.Region(dicEnvironment["start"] + 6 + len(environment), dicEnvironment["start"] + 7 + len(environment)))
                pass
            else:
                view.insert(edit, dicEnvironment["end"] - 1, "*")
                view.insert(edit, dicEnvironment["start"] + 7 + len(environment), "*")


class LtxTexcountCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        log.debug(self)

        executable = terminal.find_executable("texcount", command_line_tool=True, error=True)
        if not executable:
            return

        # Parse tex file
        tex_file = cache.TeXFile(self.view.file_name())
        tex_file.run()

        # Parse root file
        root_file = tex_file.root_file()
        root_file.run()

        c = terminal.TexcountCmd(root_file)

        def on_done():
            # Define columns
            cols = [["File", "file_path"], ["Words in Text", "words"], ["Words in Headers", "words_headers"], ["Words in Captions", "words_captions"], ["Total", "words_total"]]

            # Get the max col width
            cols_width = [max([len(item[key]) for item in c.items] + [len(cols[i][0])]) for i, key in enumerate([col[1] for col in cols])]

            # Create new view and assign name
            view = sublime.active_window().new_file()
            view.set_scratch(True)
            view.settings().set('word_wrap', False)
            view.set_read_only(True)
            view.set_name("Texcount %s" % root_file.file_name)

            # Print first line boarder
            string = "+"
            for i, col in enumerate(cols):
                string += "-" + "-" * cols_width[i] + "-+"
            string += "\n"

            # Print header
            string += "|"
            for i in range(len(cols)):
                string += " " + cols[i][0].ljust(cols_width[i], " ") + " |"
            string += "\n"

            # Print boarder before content
            string += "+"
            for i, col in enumerate(cols):
                string += "-" + "-" * cols_width[i] + "-+"
            string += "\n"

            # Print items
            for item in c.items:
                string += "|"
                for i, col in enumerate(cols):
                    string += " " + item[col[1]].ljust(cols_width[i], " ") + " |"
                string += "\n"

            # Print boarder after content
            string += "+"
            for i, col in enumerate(cols):
                string += "=" + "=" * cols_width[i] + "=+"
            string += "\n"

            # Print total count
            counts = {}
            counts["words"] = str(sum([int(item["words"]) for item in c.items]))
            counts["words_headers"] = str(sum([int(item["words_headers"]) for item in c.items]))
            counts["words_captions"] = str(sum([int(item["words_captions"]) for item in c.items]))
            counts["words_total"] = str(sum([int(item["words_total"]) for item in c.items]))

            string += "|"
            for i, col in enumerate(cols):
                if col[1] in counts:
                    string += " " + counts[col[1]].ljust(cols_width[i], " ") + " |"
                else:
                    string += " " + " " * cols_width[i] + " |"
            string += "\n"

            # Print last line boarder
            string += "+"
            for i, col in enumerate(cols):
                string += "-" + "-" * cols_width[i] + "-+"
            string += "\n"

            string += "** Generated with LaTeXing %s" % LTX_VERSION

            view.run_command("ltx_append_text", {"string": string})
            view.run_command("ltx_select_point", {"point": 0})

            if c.error:
                sublime.error_message("Error while executing:\n%s" % c.cmd)
            # else:
                # sublime.message_dialog("Word count for %s\n\nWords in text: %s\nWords in headers: %s\nWords in float captions: %s" % (tex_file.root_file_path().replace(os.path.expanduser('~'), '~'), counts["words"], counts["words_headers"], counts["words_captions"]))

        message = ["Counting...", "Finished Counting"]
        progress.progress_function(c.run, message[0], message[1], on_done)


class KpsewhichCommand():

    def __init__(self, view):
        self.view = view

    def run(self, left, right, mode="sty"):
        log.debug("%s, %s" % (left, right))

        pkg_file = cache.PkgFile()

        def on_done():
            data = pkg_file.data[mode]
            if data:
                def on_done_panel(i):
                    if i >= 0:
                        self.view.run_command("ltx_replace_region", {"region": (left, right), "string": data[i]})
                self.view.window().show_quick_panel(data, on_done_panel)
            else:
                sublime.error_message("Invalid cache data, please reset the cache!")

        message = ["Searching...", "Finished Searching"]
        progress.progress_function(pkg_file.run, message[0], message[1], on_done)


class TexdocCommand():

    def __init__(self, view):
        self.view = view

    def run(self, argument):
        log.debug("%s" % argument)

        if not argument:
            return

        doc_file = cache.DocFile(argument)

        def on_done():
            data = doc_file.data
            message = [["Open %s online http://www.ctan.org" % argument, "http://ctan.org/pkg/%s" % argument]]
            message += [["Search %s online http://www.ctan.org" % argument, "http://www.ctan.org/search?phrase=%s" % argument]]
            message += [["Search %s online on http://www.google.com " % argument, "http://www.google.com/search?q=latex package %s" % argument]]
            message += [["Open %s offline" % os.path.basename(item), item] for item in data]

            def on_done_panel(i):
                file_path = message[i][1]
                if i >= 0:
                    if file_path.startswith("http://"):
                        webbrowser.open(file_path)
                    else:
                        try:
                            if sublime.platform() == "windows":
                                os.startfile(file_path)
                            elif sublime.platform() == "osx":
                                subprocess.call(["open", file_path])
                            elif sublime.platform() == "linux":
                                subprocess.call(["xdg-open", file_path])
                        except:
                            sublime.error_message("Cannot open the selected filetype!")

            self.view.window().show_quick_panel(message, on_done_panel)

        message = ["Searching...", "Finished Searching"]
        progress.progress_function(doc_file.run, message[0], message[1], on_done)
