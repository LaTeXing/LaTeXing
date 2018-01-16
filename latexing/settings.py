import sublime
import sublime_plugin

from . import tools


class LtxExtendedPreferencesCommand(sublime_plugin.WindowCommand):

    def run(self, user=False):
        # Add sublime-build file
        items = [["LaTeXing/LaTeX.sublime-build", "User/LaTeX.sublime-build"]]
        items += [["LaTeXing/LaTeX (TikZ).sublime-build", "User/LaTeX (TikZ).sublime-build"]]

        # Add sublime-keymap files
        items += [["LaTeXing/Default.sublime-keymap", "User/Default.sublime-keymap"]]
        if sublime.platform() == "windows":
            items += [["LaTeXing/Default (Windows).sublime-keymap", "User/Default (Windows).sublime-keymap"]]
        elif sublime.platform() == "osx":
            items += [["LaTeXing/Default (OSX).sublime-keymap", "User/Default (OSX).sublime-keymap"]]
        elif sublime.platform() == "linux":
            items += [["LaTeXing/Default (Linux).sublime-keymap", "User/Default (Linux).sublime-keymap"]]

        # Add map files for bibsonomy, citeulike, mendeley, zotero
        items += [["LaTeXing/latexing/api/bibsonomy.map", "User/LaTeXing/bibsonomy.map"]]
        items += [["LaTeXing/latexing/api/citeulike.map", "User/LaTeXing/citeulike.map"]]
        items += [["LaTeXing/latexing/api/mendeley.map", "User/LaTeXing/mendeley.map"]]
        items += [["LaTeXing/latexing/api/zotero.map", "User/LaTeXing/zotero.map"]]

        message = ["Open %s" % item[1 if user else 0] for item in items]

        def on_done(i):
            if i >= 0:
                self.window.run_command("open_file", {"file": "${packages}/%s" % items[i][1 if user else 0]})

        if sublime.ok_cancel_dialog("You are trying to access the extened settings, be sure that you know what you are doing. In case of a problem please reset the files and try it again before reporting any problem."):
            self.window.show_quick_panel(message, on_done)


class LtxTogglePreferencesCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        src_content = sublime.load_resource("Packages/LaTeXing/LaTeXing.sublime-settings")
        src_json = sublime.decode_value(src_content)

        items = [{"key": key, "value": value} for key, value in sorted(src_json.items(), key=lambda x: src_content.find(x[0])) if isinstance(value, bool)]
        settings = tools.load_settings("LaTeXing", **dict([item["key"], item["value"]] for item in items))
        message = [["%s %s" % ("Enable" if not settings[item["key"]] else "Disable", item["key"])] for item in items]

        def on_done(i):
            if i >= 0:
                # Read/save preferences
                tools.save_settings("LaTeXing", **{items[i]["key"]: not settings[items[i]["key"]]})
                sublime.status_message("%s is now %s" % (items[i]["key"], "disabled" if settings[items[i]["key"]] else "enabled"))

        self.view.window().show_quick_panel(message, on_done)
