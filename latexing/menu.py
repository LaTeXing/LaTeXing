import sublime
import sublime_plugin

import webbrowser

from . import LTX_VERSION
from . import tools


class LtxBuyLicenseCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        webbrowser.open("http://www.latexing.com/buy.html")


class LtxChangelogCommand(sublime_plugin.WindowCommand):

    def run(self):
        values = sublime.decode_value(sublime.load_resource("Packages/LaTeXing/messages.json"))
        items = sorted([key for key, value in values.items()], key=lambda x: (x != "install", x), reverse=True)

        def on_done(i):
            if i < 0:
                return
            view = sublime.active_window().new_file()
            view.set_scratch(True)
            view.settings().set('word_wrap', False)
            view.set_read_only(True)
            view.run_command("ltx_append_text", {"string": sublime.load_resource("Packages/LaTeXing/%s" % values[items[i]])})

        self.window.show_quick_panel(items, on_done)


class LtxOpenDocumentationCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        webbrowser.open("http://docs.latexing.com")


class LtxVersionCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        sublime.message_dialog('You have LaTeXing %s' % LTX_VERSION)


class LtxInstallLicenseCommand(sublime_plugin.WindowCommand):

    def show_email_panel(self, initial_email=""):
        def on_done(s):
            email = s.strip()
            if not email or "@" not in email:
                sublime.error_message("Are you sure \"%s\" a valid email?" % email)
                self.show_email_panel(email)
            else:
                self.email = email
                self.show_key_panel()

        self.window.show_input_panel("Email:", initial_email, on_done, None, None)

    def show_key_panel(self):
        def on_done(s):
            key = s.strip()
            if not key:
                sublime.error_message('Please provide a license key, or press escape to cancel.')
                self.show_key_panel()
            elif len(key) != 26:
                sublime.error_message("Invalid key format. Please double check the license key.")
                self.show_key_panel()
            else:
                tools.save_license("LaTeXing", username=self.email, license=key)
                sublime.status_message("LaTeXing is fully registered now, thank you for your support.")

        self.window.show_input_panel("License Key:", "", on_done, None, None)

    def run(self):
        settings = tools.load_license("LaTeXing", username="", license="")
        if settings["username"] and settings["license"]:
            if not sublime.ok_cancel_dialog("You already have a license installed. Do you which to replace it?\n\nEmail:\n  %s\nLicense key:\n  %s" % (settings["username"], settings["license"]), 'Overwrite'):
                return
        self.show_email_panel()


class LtxOfflineCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        ltx_offline = tools.LtxSettings().get("ltx_offline", False)
        tools.LtxSettings().set("ltx_offline", not ltx_offline)
        sublime.status_message("You switched to the %s mode!" % ("online" if ltx_offline else "offline"))
