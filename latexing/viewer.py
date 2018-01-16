import sublime
import sublime_plugin

import os.path
import time
import subprocess

from . import cache
from . import logger
from . import progress
from . import terminal
from . import tools

log = logger.getLogger(__name__)


class LtxJumpToPdfCommand(sublime_plugin.WindowCommand):

    def is_enabled(self):
        try:
            if not self.window.active_view().match_selector(0, "text.tex.latex"):
                return False
            # Parse tex file
            tex_file = cache.TeXFile(self.window.active_view().file_name())
            tex_file.run()

            # Parse root file
            root_file = tex_file.root_file()
            root_file.run()

            return os.path.exists(self.window.active_view().file_name())
        except:
            return False

    def run(self, **args):
        self.window.run_command("ltx_open_pdf", {"keep_focus": False})


class LtxOpenPdfCommand(sublime_plugin.WindowCommand):

    def is_enabled(self):
        try:
            if not self.window.active_view().match_selector(0, "text.tex.latex"):
                return False
            # Parse tex file
            tex_file = cache.TeXFile(self.window.active_view().file_name())
            tex_file.run()

            # Parse root file
            root_file = tex_file.root_file()
            root_file.run()

            return os.path.exists(self.window.active_view().file_name())
        except:
            return False

    def run(self, **args):
        message = ["Opening...", "Finished Opening"]
        progress.progress_function(lambda: self.__run(**args), message[0], message[1], lambda: None)

    def __run(self, **args):
        # Read settings
        settings = tools.load_settings("LaTeXing", forward_sync=True, reverse_sync=True, keep_focus=True, keep_focus_delay=0.2, pdf_viewer_order=["skim", "preview", "sumatra_pdf", "adobe_reader", "foxit_reader", "pdf_xchange_viewer", "evince", "okular"])

        # Check of force focuse pdf viewer
        settings["keep_focus"] = args["keep_focus"] if "keep_focus" in args else settings["keep_focus"]

        view = self.window.active_view()

        # Parse tex file
        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        # Parse root file
        root_file = tex_file.root_file()
        root_file.run()

        # Set required parameter
        file_path = tex_file.file_path
        pdf_path = root_file.pdf_file_path()
        line = view.rowcol(view.sel()[0].end())[0] + 1

        if not os.path.exists(pdf_path):
            if "on_load" not in args or not args["on_load"]:
                sublime.error_message("Cannot open %s. Please check if the pdf was correctly created." % pdf_path)
            return

        # find sublime bin and bin dictionary
        sublime_bin = terminal.find_executable("sublime")
        bin_dir = os.path.join(sublime.cache_path(), "LaTeXing", "bin")

        def switch_back():
            if sublime_bin:
                log.debug("Switched back to Sublime Text, if this wasn't working please increase keep_focus_delay.")
                time.sleep(settings["keep_focus_delay"])
                subprocess.Popen(sublime_bin)
            else:
                log.warning("Could not locate the sublime text executable, please adjust the settings or your path to support keep_focus.")

        for key in settings["pdf_viewer_order"]:

            viewer_path = terminal.find_viewer(key)
            if not viewer_path:
                continue

            # Handle Skim
            if key == "skim":
                # Build command
                cmd = ["%s/Contents/SharedSupport/displayline" % viewer_path, "-r", "-g"]
                cmd.append(str(line) if settings["forward_sync"] else "0")
                cmd.append(pdf_path)

                if settings["forward_sync"]:
                    cmd.append(file_path)

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                if not settings["keep_focus"]:
                    subprocess.Popen(["%s/activate_application" % bin_dir, "net.sourceforge.skim-app.skim"])
                break

            # Handle Preview
            elif key == "preview":
                # Build comand
                cmd = ["%s/preview" % bin_dir, pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                if settings["keep_focus"]:
                    subprocess.Popen(["%s/activate_application" % bin_dir, "com.sublimetext.3"])

                log.warning("Preview do not respect the forward_sync and reverse_sync option.")
                break

            # Handle Sumatra PDF
            elif key == "sumatra_pdf":
                # Build command
                cmd = [viewer_path, "-reuse-instance", pdf_path]

                if settings["forward_sync"]:
                    cmd = [viewer_path, "-reuse-instance", "-forward-search", file_path, str(line), pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                if settings["keep_focus"]:
                    switch_back()
                break

            # Handle Adobe Reader
            elif key == "adobe_reader":
                # Build command
                cmd = [viewer_path, pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                # warning
                log.warning("Adobe Reader do not respect the forward_sync and reverse_sync option.")

                if settings["keep_focus"]:
                    switch_back()
                break

            # Handle Foxit Reader
            elif key == "foxit_reader":
                # Build command
                cmd = [viewer_path, pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                # warning
                log.warning("Foxit Reader do not respect the forward_sync and reverse_sync option.")

                if settings["keep_focus"]:
                    switch_back()
                break

            # Handle PDF XChange Viewer
            elif key == "pdf_xchange_viewer":
                # Build command
                cmd = [viewer_path, pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                # warning
                log.warning("PDF XChange Viewer do not respect the forward_sync, reverse_sync option.")

                if settings["keep_focus"]:
                    switch_back()
                break

            # Handle Okular
            elif key == "okular":
                # Build command
                cmd = [viewer_path, "-unique"]
                cmd.append("file:%s" % pdf_path + ("#src:%s" % line if settings["forward_sync"] else "# ") + (file_path if settings["forward_sync"] or settings["reverse_sync"] else ""))

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                if settings["keep_focus"]:
                    switch_back()
                break

            # Handle Evince
            elif key == "evince":
                # Build command
                cmd = ["sh", "evince", viewer_path, pdf_path]

                if settings["reverse_sync"] and sublime_bin:
                    cmd.append(sublime_bin)

                # Check if evince is open
                def check_program(name):
                    return name in terminal.communicate(["ps", "wx"])[0]

                for i in range(5):
                    if check_program("evince"):
                        break
                    subprocess.Popen(cmd, cwd=bin_dir)
                    time.sleep(1.0)
                else:
                    sublime.error_message("Cannot launch evince. Make sure it is on your PATH.")

                if settings["forward_sync"]:
                    cmd = ["%s/evince_forward_sync" % bin_dir]
                    cmd.extend([pdf_path, str(line), file_path])
                else:
                    cmd = [viewer_path, pdf_path]

                log.debug("cmd: %s" % " ".join(cmd))
                subprocess.Popen(cmd)

                if settings["keep_focus"]:
                    switch_back()
                break
