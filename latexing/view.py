import sublime
import sublime_plugin

from . import logger

log = logger.getLogger(__name__)


class LtxClearCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        self.view.erase(edit, sublime.Region(0, self.view.size()))


class LtxSelectPointCommand(sublime_plugin.TextCommand):

    def run(self, edit, point):
        log.trace("%s", point)
        self.view.sel().clear()
        self.view.sel().add(point)
        self.view.show(point)


class LtxSelectRowColCommand(sublime_plugin.TextCommand):

    def run(self, edit, row, col):
        log.trace("%s %s", row, col)
        point = self.view.text_point(row, col)
        self.view.run_command("ltx_select_point", {"point": point})


class LtxSelectLineCommand(sublime_plugin.TextCommand):

    def run(self, edit, left, right):
        log.trace("%s %s", left, right)
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(left, right))
        self.view.show(left)


class LtxSelectTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, text):
        region = self.view.find(text, 0)
        self.view.run_command("ltx_select_point", {"point": region.a})


class LtxAppendTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, string):
        log.trace("%s", string)
        self.view.run_command("ltx_insert_text", {"point": self.view.size(), "string": string})


class LtxInsertTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, point, string, new_line=False):
        log.trace("%s %s %s", point, string, new_line)
        read_only = self.view.is_read_only()
        self.view.set_read_only(False)

        self.view.insert(edit, point, string + ("\n" if new_line else ""))

        self.view.sel().clear()
        self.view.sel().add(point + len(string))
        self.view.show(point + len(string))

        self.view.set_read_only(read_only)


class LtxReplaceTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, text, string):
        region = self.view.find(text, 0, sublime.LITERAL)
        self.view.run_command("ltx_replace_region", {"region": [region.a, region.b], "string": string})


class LtxReplaceRegionCommand(sublime_plugin.TextCommand):

    def run(self, edit, region, string):
        log.trace("%s %s %s", region[0], region[1], string)
        read_only = self.view.is_read_only()
        self.view.set_read_only(False)

        i = string.find("$0") if string.find("$0") >= 0 else len(string)
        self.view.replace(edit, sublime.Region(region[0], region[1]), string.replace("$0", ""))

        self.view.sel().clear()
        self.view.sel().add(region[0] + i)
        self.view.show(region[0] + i)

        self.view.set_read_only(read_only)
