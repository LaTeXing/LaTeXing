import sublime
import sublime_plugin
import datetime

import hashlib
import os
import threading
import webbrowser

from . import cache
from . import tools


class LtxTexListener(sublime_plugin.EventListener):

    def on_activated(self, view):
        if not view or not view.file_name() or len(view.sel()) != 1 or not view.match_selector(0, "text.tex.latex") or view.is_scratch():
            return

    def on_modified(self, view):
        if not view or not view.file_name() or len(view.sel()) != 1 or not view.match_selector(0, "text.tex.latex") or view.is_scratch():
            return []

        # Get file name and split name and extension
        file_name = view.file_name()
        file_name_root, file_name_ext = os.path.splitext(file_name)

        # Show ptex warning, just once per view
        if file_name_ext in [".ptex"] and not view.settings().get("ltx_ptex_warning"):
            sublime.message_dialog("This file was created by LaTeXing, you can not compile this file. Any changes made to this file will get lost during the next build.")
            view.settings().set("ltx_ptex_warning", True)
            return

        settings = tools.load_settings("LaTeXing", type_scrolling=False)
        if settings["type_scrolling"]:
            view.show_at_center(view.sel()[0].end())

    def on_load(self, view):
        if not view or not view.file_name() or not view.match_selector(0, "text.tex.latex"):
            return []

        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        # Load beamer knitr highlighting and then check for beamer class
        if view.match_selector(0, "text.tex.latex.knitr"):
            if tex_file.documentclass()[0].lower() == "beamer":
                view.set_syntax_file("Packages/LaTeXing/support/LaTeX Beamer (Knitr).tmLanguage")
            else:
                view.set_syntax_file("Packages/LaTeXing/support/LaTeX (Knitr).tmLanguage")

        # Load beamer tikz highlighting
        elif view.match_selector(0, "text.tex.latex.tikz"):
            view.set_syntax_file("Packages/LaTeXing/support/LaTeX (TikZ).tmLanguage")

        # Load beamer syntax highlighting
        elif tex_file.documentclass()[0].lower() == "beamer":
            view.set_syntax_file("Packages/LaTeXing/support/LaTeX Beamer.tmLanguage")

        # Load default syntax highlighting
        else:
            view.set_syntax_file("Packages/LaTeXing/support/LaTeX.tmLanguage")

        # Load Settings
        settings = tools.load_settings("LaTeXing", open_pdf_on_load=True)

        if settings["open_pdf_on_load"] and sublime.active_window().active_view().file_name() == view.file_name() and view.window():
            view.window().run_command("ltx_open_pdf", {"keep_focus": True, "on_load": True})

    def on_post_save(self, view):

        if not view or not view.file_name() or not (view.match_selector(0, "text.tex.latex") or view.match_selector(0, "text.bibtex")):
            return []

        if view.match_selector(0, "text.bibtex"):
            # Cache Information if required
            bib_file = cache.BibFile(view.file_name())
            bib_file.save()

        else:
            # Cache Information if required
            tex_file = cache.TeXFile(view.file_name())
            tex_file.save()

            # Load beamer knitr highlighting and then check for beamer class
            if view.match_selector(0, "text.tex.latex.knitr"):
                if tex_file.documentclass()[0].lower() == "beamer":
                    view.set_syntax_file("Packages/LaTeXing/support/LaTeX Beamer (Knitr).tmLanguage")
                else:
                    view.set_syntax_file("Packages/LaTeXing/support/LaTeX (Knitr).tmLanguage")

            # Load beamer tikz highlighting
            elif view.match_selector(0, "text.tex.latex.tikz"):
                view.set_syntax_file("Packages/LaTeXing/support/LaTeX (TikZ).tmLanguage")

            # Load beamer syntax highlighting
            elif tex_file.documentclass()[0].lower() == "beamer":
                view.set_syntax_file("Packages/LaTeXing/support/LaTeX Beamer.tmLanguage")

            # Load default syntax highlighting
            else:
                view.set_syntax_file("Packages/LaTeXing/support/LaTeX.tmLanguage")

            # Load Settings
            settings = tools.load_settings("LaTeXing", typeset_on_save=False)

            if settings["typeset_on_save"] and not view.settings().get("save_is_dirty"):
                view.window().run_command('build')
            view.settings().erase("save_is_dirty")

        # Save cache
        sublime.run_command("ltx_save_cache", {"timeout": 5000, "skip_check": False})


class LtxTikzListener(sublime_plugin.EventListener):

    timer = None

    def on_modified(self, view):
        if view.match_selector(0, "text.tex.latex.tikz"):
            settings = view.settings()

            # Check if live preview is enabled
            if settings.get("ltx_live_preview", False):
                # Cancel timer if running
                if self.timer and self.timer.is_alive():
                    self.timer.cancel()

                # Start a new timer with the delay set from the settings
                self.timer = threading.Timer(0.5, self.post_on_modified)
                self.timer.start()

    def post_on_modified(self):
        resource = tools.load_resource("LaTeX (TikZ).sublime-build", osx={"cmd": [], "file_regex": ""}, windows={"cmd": [], "file_regex": ""}, linux={"cmd": [], "file_regex": ""})
        sublime.active_window().run_command("ltx_tikz_compiler", {"cmd": resource[sublime.platform()]["cmd"], "file_regex": resource[sublime.platform()]["file_regex"]})
