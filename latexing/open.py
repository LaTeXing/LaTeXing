import sublime
import sublime_plugin

import os
import re

from . import cache
from . import commands
from . import logger
from . import tools

log = logger.getLogger(__name__)


class LtxOpenAnywhereCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        self.view.run_command("ltx_open", {"open_anywhere": "input"})


class LtxOpenCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit, **args):
        # Save current view
        view = self.view

        # Load settings
        settings = tools.load_settings("LaTeXing", default_tex_extension=".tex", default_bib_extension=".bib")

        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b
        dicCommandRange = tools.find_command_range(view, int(point))
        if isinstance(dicCommandRange, str):
            dicCommand = {"name": None, "arguments": [{"content": None}]}
            argument = None
        else:
            dicCommand = tools.split_command(view.substr(sublime.Region(dicCommandRange["start"], dicCommandRange["end"])), dicCommandRange["start"])
            dicArgument = tools.find_current_argument(dicCommand["arguments"], dicCommandRange["point"])
            argument = dicArgument["argument"]

            log.debug("dicCommandRange: %s", dicCommandRange)
            log.debug("dicCommand: %s", dicCommand)
            log.debug("dicArgument: %s", dicArgument)

        # Check for command includegraphics, Input|Include|Subfile, Bibliography, ...
        rexRoot = re.compile(r"%\s*-\*-\s*root\s*:\s*(.+)(?=-\*-)", re.IGNORECASE)

        rexAc = re.compile(r"\b[Ii]?ac[uplsf]?[suip]?(de)?\*?\b")
        rexBibliography = re.compile(r"\b(bibliography|addbibresource|addglobalbib|addsectionbib)\b")
        rexCite = re.compile(r"\b\w*(cite|bibentry)\w*\*?\b")
        rexInput = re.compile(r"\b(input|include|subfile)\b")
        rexLabel = re.compile(r"\blinelabel\b")
        rexRef = re.compile(r"\b\w*ref\b")
        rexUsepackage = re.compile(r"\b(usepackage|documentclass)\b")

        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()
        tex_path = tex_file.file_path
        tex_dir, tex_name, tex_name_root, tex_name_ext = tools.split_file_path(tex_path)

        root_file = tex_file.root_file()
        root_file.run()
        root_path = root_file.file_path
        root_dir, root_name, root_name_root, root_name_ext = tools.split_file_path(root_path)

        file_names = []
        search = None
        commandType = None

        if "open_anywhere" in args:
            dicCommand["name"] = args["open_anywhere"]
            # if not within a argument use curent point and simulate pair
            if not argument:
                argument = {"pair": "{", "start": point, "end": point}

        if not dicCommand["name"]:
            return

        if rexRoot.search(view.substr(view.full_line(point))):
            file_names = [tex_path]

        elif not dicCommand["name"] or not dicCommand["arguments"][0]["content"]:
            pass

        elif rexInput.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexInput matched")

            if "open_anywhere" in args:
                files = tools.list_dir(root_dir, ["*%s.*" % os.path.basename(os.path.splitext(argument["content"])[0])])
                file_names = [item["rel_path"] for item in files]
            else:
                if not os.path.splitext(argument["content"])[1]:
                    file_names = [tools.add_extension(argument["content"], settings["default_tex_extension"])]
                else:
                    file_names = [argument["content"]]

        elif rexBibliography.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexBibliography matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            argument = view.substr(sublime.Region(left, right))

            file_names = [tools.add_extension(argument, settings["default_bib_extension"])]

        elif rexCite.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexCite matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            argument = view.substr(sublime.Region(left, right))

            try:
                for item in tex_file.bibliography():
                    bib_file = cache.BibFile(item)
                    bib_file.run()
                    if bib_file.has_cite(argument):
                        file_names = [bib_file.file_path]
                        search = r"@.+\{" + re.escape(argument)
                        break
                if not len(file_names):
                    for file_path, item in tex_file.get("bibitem"):
                        if item["arguments"][0].split(":", 1)[1] == argument:
                            file_names = [tex_file.file_path]
                            search = r"\\bibitem\{" + re.escape(argument) + r"\}"
                            break
                if not len(file_names):
                    raise OSError
            except:
                sublime.error_message("Unable to locate target reference \"%s\"!" % argument)

        elif re.match(r"\b\w*hyperref\b", dicCommand["name"], re.IGNORECASE):
            log.debug("hyperref matched")

            if argument["pair"] == "{":
                return

            try:
                for file_path, item in tex_file.get("label"):
                    print(file_path, item)
                    if item["arguments"][0].split(":", 1)[1] == argument["content"]:
                        file_names = [file_path]
                        search = r"\\(line)?label\{" + re.escape(argument["content"]) + r"\}"
                        break
                if not len(file_names):
                    raise OSError
            except:
                sublime.error_message("Unable to locate target label \"%s\"!" % argument["content"])

        elif rexRef.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexRef matched")

            try:
                for file_path, item in tex_file.get("label"):
                    print(file_path, item)
                    if item["arguments"][0].split(":", 1)[1] == argument["content"]:
                        file_names = [file_path]
                        search = r"\\(line)?label\{" + re.escape(argument["content"]) + r"\}"
                        break
                if not len(file_names):
                    raise OSError
            except:
                sublime.error_message("Unable to locate target label \"%s\"!" % argument["content"])

        elif rexAc.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexAc matched")

            try:
                for file_path, item in tex_file.get("ac"):
                    if item["arguments"][0].split(":", 1)[1] == argument["content"]:
                        file_names = [file_path]
                        search = r"\\(new)?acro(def)?(indefinite|plural)?\{" + argument["content"] + r"\}"
                        break
                if not len(file_names):
                    raise OSError
            except:
                sublime.error_message("Unable to locate target acronym \"%s\"!" % argument["content"])

        elif rexUsepackage.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexUsepackage matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            commandType = "noMessage"

            argument = view.substr(sublime.Region(left, right))
            commands.TexdocCommand(self.view).run(argument)

        elif rexLabel.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexLabel matched")

            commandType = "highlight"

            items = {}
            for file_path, item in tex_file.get("ref"):
                if item["arguments"][0].split(":", 1)[1] == argument["content"]:
                    file_names += ["%s:%d" % (file_path, item["line"])]

        # Check the file names
        items = []
        for file_name in file_names:
            line = None

            parts = re.split(r":(?=\d+)", file_name)
            if len(parts) == 2:
                file_name, line = parts

            if os.path.isabs(file_name):
                file_path = file_name
            elif file_name.startswith("./"):
                file_path = os.path.join(root_dir, file_name[2:])
            else:
                file_path = os.path.realpath(os.path.join(root_dir, file_name))
            items += [file_path + (":%s" % line if line else "")]
        file_names = items

        message = [item.replace(os.path.expanduser('~'), '~') for item in items]
        row, col = view.rowcol(point)

        def on_highlighted(i):
            file_name = file_names[i]
            view.window().open_file(file_name, sublime.ENCODED_POSITION | sublime.TRANSIENT)

        def on_done(i):
            if i < 0:
                view.window().focus_view(view)
                view.run_command("ltx_select_row_col", {"row": row, "col": col})
            else:
                file_name = file_names[i]
                log.debug("file_name %s", file_name)
                try:
                    if not os.path.exists(file_path):
                        raise OSError
                    # Open file
                    new_view = view.window().open_file(file_name, sublime.ENCODED_POSITION)
                    if search:
                        tools.search_text_in_view(new_view, search)
                    sublime.status_message("Open %s" % file_name)
                except:
                    sublime.error_message("Cannot find file! (%s)" % file_name)

        if commandType != "noMessage":
            if not file_names:
                sublime.status_message("Status: Cannot find anything to open")
            elif len(file_names) == 1 and commandType != "highlight":
                on_done(0)
            elif len(file_names) >= 1:
                sublime.set_timeout(lambda: view.window().show_quick_panel(message, on_done, 0, 0, on_highlighted if commandType == "highlight" else None), 0)
