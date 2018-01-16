import sublime
import sublime_plugin

import os
import tabulate
import threading

from . import LTX_VERSION
from . import logger
from . import progress
from . import terminal
from . import tools

log = logger.getLogger(__name__)


class CheckSystemThread(threading.Thread):

    def __init__(self, items):
        self.items = items
        threading.Thread.__init__(self)

    def run(self):
        # required
        for item in self.items["required"]:
            path = terminal.find_executable(item["name"], command_line_tool=True)

            item["path"] = path if path else ""
            item["status"] = "Found" if path else "Missing"

            if path:
                stdout, stderr = terminal.communicate([path] + ["--version"])

            item["stdout"] = stdout if path else ""
            item["stderr"] = stderr if path else ""

        # optional
        for item in self.items["optional"]:
            path = terminal.find_executable(item["name"], command_line_tool=True)

            item["path"] = path if path else ""
            item["status"] = "Found" if path else "Missing"

            if path:
                stdout, stderr = terminal.communicate([path] + ["--version"])

            item["stdout"] = stdout if path else ""
            item["stderr"] = stderr if path else ""

        # viewer
        for item in self.items["viewer"]:
            path = terminal.find_viewer(item["name"])

            item["path"] = path if path else ""
            item["status"] = "Found" if path else "Missing"

        print(self.items)


class LtxCheckSystemCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        # Load path for windows to detect miktex
        resource = tools.load_resource("LaTeX.sublime-build", osx={"path": ""}, windows={"path": ""}, linux={"path": ""})
        settings = tools.load_settings("LaTeXing", path=[], pdf_viewer_osx=[], pdf_viewer_windows=[], pdf_viewer_linux=[])

        items = {"optional": [], "required": [], "viewer": []}

        # If on windows and miktex in path
        miktex = sublime.platform() == "windows" and "miktex" in resource["windows"]["path"].lower()

        # Required are: perl, latexmk
        items["required"] += [{"name": "perl"}]
        items["required"] += [{"name": "latexmk"}]

        # Optional are: texcount, pdflatex, kpsewhich, texdoc/mthelp, sublime, rscript
        items["optional"] += [{"name": "texcount"}]
        items["optional"] += [{"name": "biber"}]
        items["optional"] += [{"name": "bibtex"}]
        items["optional"] += [{"name": "pdflatex"}]
        items["optional"] += [{"name": "xelatex"}]
        items["optional"] += [{"name": "lualatex"}]
        items["optional"] += [{"name": "kpsewhich"}]
        items["optional"] += [{"name": "mthelp" if miktex else "texdoc"}]
        items["optional"] += [{"name": "sublime"}]
        items["optional"] += [{"name": "rscript"}]

        # The viewer depends on the used platform
        for viewer in settings["pdf_viewer_%s" % sublime.platform()]:
            items['viewer'] += [{"name": viewer}]

        t = CheckSystemThread(items)
        t.start()

        def on_done():
            # Create new view and assign name
            view = sublime.active_window().new_file()
            view.set_scratch(True)
            view.settings().set('word_wrap', False)
            view.set_read_only(True)
            view.set_name("Check System")

            headers = ["Executable", "Type", "Status", "Path"]
            table = []
            for item in t.items["required"]:
                table += [[item["name"], "Required", item["status"], item["path"]]]

            for item in t.items["optional"]:
                table += [[item["name"], "Optional", item["status"], item["path"]]]

            for item in t.items["viewer"]:
                table += [[item["name"], "Viewer", item["status"], item["path"]]]

            view.run_command("ltx_append_text", {"string": tabulate.tabulate(table, headers, tablefmt="grid")})
            view.run_command("ltx_append_text", {"string": "\n** Checked with LaTeXing %s\n\n" % LTX_VERSION})

            # searched Path
            if sublime.platform() == "windows":
                items = (os.path.expandvars(resource["windows"]["path"]) + ";" + ";".join([path for path in settings["path"] if os.path.isdir(path)])).split(";")
            elif sublime.platform() == "osx":
                items = (os.path.expandvars(resource["osx"]["path"]) + ":" + ":".join([path for path in settings["path"] if os.path.isdir(path)])).split(":")
            elif sublime.platform() == "linux":
                items = (os.path.expandvars(resource["linux"]["path"]) + ":" + ":".join([path for path in settings["path"] if os.path.isdir(path)])).split(":")

            headers = ["Searched Path"]
            table = []
            for item in items:
                table += [[item]] if item else []

            view.run_command("ltx_append_text", {"string": tabulate.tabulate(table, headers, tablefmt="grid")})
            view.run_command("ltx_append_text", {"string": "\n\n"})

            # extra infos
            headers = ["Executable", "stdout/stderr"]
            table = []
            for item in t.items["required"]:
                table += [[item['name'], item['stdout'][0:item['stdout'].find('\n', 1)] if item['stdout'] else item['stderr'][0:item['stderr'].find('\n', 1)]]] if item['stdout'] or item['stderr'] else [[item['name'], "-"]]

            for item in t.items["optional"]:
                table += [[item['name'], item['stdout'][0:item['stdout'].find('\n', 1)] if item['stdout'] else item['stderr'][0:item['stderr'].find('\n', 1)]]] if item['stdout'] or item['stderr'] else [[item['name'], "-"]]

            view.run_command("ltx_append_text", {"string": tabulate.tabulate(table, headers, tablefmt="grid")})
            view.run_command("ltx_select_point", {"point": 0})

        message = ["Check System...", "Finished Check System"]
        progress.Progress(t, message[0], message[1], on_done)
