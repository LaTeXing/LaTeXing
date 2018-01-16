import sublime
import sublime_plugin

import datetime
import hashlib
import os
import re
import shutil
import sys
import webbrowser

from . import cache
from . import check_source
from . import cite
from . import logger
from . import output
from . import progress
from . import terminal
from . import tools

log = logger.getLogger(__name__)


class LtxQuickBuildCompilerCommand(sublime_plugin.WindowCommand):

    def run(self, cmd="", cmd_qb=[], file_regex="", path="", primary_qb=False):
        resource = tools.load_resource("LaTeX.sublime-build", osx={"cmd": [], "cmd_qb": {}, "file_regex": ""}, windows={"cmd": [], "cmd_qb": {}, "file_regex": ""}, linux={"cmd": [], "cmd_qb": {}, "file_regex": ""})
        settings = tools.load_settings("LaTeXing", quick_build=[{"name": "latexmk", "desciption": "Run latexmk", "primary": True, "cmds": ["latexmk"]}])

        cmd = resource[sublime.platform()]["cmd"]
        cmd_qb = resource[sublime.platform()]["cmd_qb"]
        file_regex = resource[sublime.platform()]["file_regex"]

        if primary_qb:
            items = [item for item in settings["quick_build"] if "primary" in item and item["primary"]]
            self.window.run_command("ltx_default_compiler", {"cmd": cmd, "cmds": [cmd_qb[item] for item in items[0]["cmds"]], "file_regex": file_regex})
        else:
            # Build items
            items = sorted([["Single Quick Build: %s" % key, [key]] for key, value in cmd_qb.items()] + [[item["name"], item["cmds"]] for item in settings["quick_build"]], key=lambda x: x[0])

            def on_done(i):
                if i >= 0:
                    self.window.run_command("ltx_default_compiler", {"cmd": cmd, "cmds": [cmd_qb[item] for item in items[i][1]], "file_regex": file_regex})

            # Select a quick build
            self.window.show_quick_panel([[key, ", ".join(value)] for key, value in items], on_done)


class LtxDefaultCompilerCommand(sublime_plugin.WindowCommand):

    def run(self, cmd="", cmd_qb={}, cmds=[], file_regex="", path=""):
        message = ["Compiling...", "Finished Compiling"]
        progress.progress_function(lambda: self.on_run(cmds if cmds else [cmd], file_regex), message[0], message[1], lambda: None)

    def on_run(self, cmds=[], file_regex=""):
        # Check if executable can be found
        for cmd in cmds:
            cmd[0] = terminal.find_executable(cmd[0], command_line_tool=True, error=True)
            if not cmd[0]:
                return

        # Load Settings
        settings = tools.load_settings("LaTeXing", builder={"latexmk": ["latexmk"]}, knitr=False, partial_build=False, show_log_panel_on=["errors", "warnings", "badboxes", "infos"], tikz=False)

        # Init and clear output_view
        self.log_panel = output.Panel(self.window, file_regex=file_regex, show="infos" in settings["show_log_panel_on"])
        show_log_panel_on = settings["show_log_panel_on"]

        # Check if already running
        if hasattr(self, 'isRunning') and self.isRunning:
            if hasattr(self, "ts") and self.ts.terminate():
                self.log_panel.show()
                self.log_panel.log("### Running process!! Terminated the old one. Please start the new process. ###\n")
            else:
                self.log_panel.show()
                self.log_panel.log("### Running process!! Cannot initiate a new one!!! Please wait or terminate the old one. ###\n")
                return

        # Set isRunning to block further starts
        self.isRunning = True

        # Save view if dirty
        view = self.window.active_view()
        if view.is_dirty():
            view.settings().set("save_is_dirty", True)
            view.run_command('save')

        # Parse tex file
        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        # Parse root file
        root_file = tex_file.root_file()
        root_file.run()

        # Very important since we do need to change the working directory
        os.chdir(root_file.file_dir)

        # Save time for later use of compile duration
        t1 = datetime.datetime.today()

        # ptex, knitr, Tikz, partial, default typeset
        if tex_file.file_name_ext.lower() in [".ptex"]:
            sublime.message_dialog("This file was created by LaTeXing, you can not compile this file. Any changes made to this file will get lost during the next build.")
            self.isRunning = False
            return
        elif settings["knitr"] and tex_file.file_name_ext.lower() in [".rnw", ".snw", ".rtex"]:
            self.log_panel.log("[Compile %s]\n" % tex_file.file_path.replace(os.path.expanduser('~'), '~'))
            self.ts = Knitr(tex_file, root_file)

        elif settings["tikz"] and tex_file.file_name_ext.lower() in [".tikz"]:
            self.log_panel.log("[Compile %s]\n" % tex_file.file_path.replace(os.path.expanduser('~'), '~'))
            self.ts = Tikz(tex_file, root_file)

        elif settings["partial_build"] and tex_file.file_path != root_file.file_path:
            self.log_panel.log("[Compile %s Partial]\n" % root_file.file_path.replace(os.path.expanduser('~'), '~'))
            self.ts = Partial(tex_file, root_file)
        else:
            self.log_panel.log("[Compile %s]\n" % root_file.file_path.replace(os.path.expanduser('~'), '~'))
            self.ts = Default(tex_file, root_file)

        # Typeset the current document and check if terminated
        if self.ts.run(cmds):
            return

        # Start parse and display the log file
        errors = self.ts.errors
        warnings = self.ts.warnings
        badboxes = []

        if not errors:
            try:
                log_file = output.LogFilter(self.ts.file_path, self.ts.log_path)
                log_errors, log_warnings, log_badboxes = log_file.parse()

                # Adjust log messages
                if hasattr(self.ts, "on_post_log_parse"):
                    log_errors, log_warnings, log_badboxes = self.ts.on_post_log_parse(log_errors, log_warnings, log_badboxes)

                errors.extend(log_errors)
                warnings.extend(log_warnings)
                badboxes.extend(log_badboxes)
            except IOError as e:
                log.error(e)
                errors.append("Could not open log file, please check your system. Be sure you are using the latest version of your LaTeX distribution.")
            except Exception as e:
                log.error(e)
                errors.append("Unexpected error in log file!")

        content = []
        content.extend(errors + [""] if errors else [])
        content.extend(warnings + [""] if warnings else [])
        content.extend(badboxes + [""] if badboxes else [])

        self.log_panel.log(content)
        self.log_panel.log(("1 error, " if len(errors) == 1 else "%s errors, " % len(errors)) + ("1 warning, " if len(warnings) == 1 else "%s warnings, " % len(warnings)) + ("1 badbox" if len(badboxes) == 1 else "%s badboxes" % len(badboxes)))

        t2 = datetime.datetime.today()
        # Confirm the end of the current process
        self.log_panel.log("\n[Finished in %.2fs]\n" % (t2 - t1).total_seconds())

        if errors and "errors" in show_log_panel_on:
            self.log_panel.show()

        if warnings and "warnings" in show_log_panel_on:
            self.log_panel.show()

        if badboxes and "badboxes" in show_log_panel_on:
            self.log_panel.show()

        if (not errors or "errors" not in show_log_panel_on) and (not warnings or "warnings" not in show_log_panel_on) and (not badboxes or "badboxes" not in show_log_panel_on) and "infos" not in show_log_panel_on:
            self.log_panel.hide()

        # Return with a success to show the pdf file now
        error = len(errors) > 0

        # Clean source folder if output dir is selected
        if hasattr(self.ts, "clean_file_paths") and self.ts.clean_file_paths:
            tools.delete_files(self.ts.clean_file_paths)

        # Move pdf and synctex file to source file if available
        try:
            if self.ts.src_synctex_path and self.ts.dst_synctex_path and self.ts.src_synctex_path != self.ts.dst_synctex_path and os.path.exists(self.ts.src_synctex_path):
                shutil.copyfile(self.ts.src_synctex_path, self.ts.dst_synctex_path)

            if os.path.exists(self.ts.src_pdf_path) and self.ts.src_pdf_path != self.ts.dst_pdf_path:
                shutil.copyfile(self.ts.src_pdf_path, self.ts.dst_pdf_path)

            if not error:
                self.window.run_command("ltx_open_pdf")

        except Exception as e:
            log.error(e)
            sublime.error_message("Could not move the pdf or synctex file. Close the pdf viewer to reset the file access or other permission problems.")

        # Call on post run actions
        if hasattr(self.ts, "on_post_run"):
            self.ts.on_post_run()

        self.isRunning = False
        self.log_panel.finish()


class LtxTikzCompilerCommand(LtxDefaultCompilerCommand):

    def run(self, cmd="", file_regex="", path=""):
        message = ["Compiling...", "Finished Compiling"]
        progress.progress_function(lambda: self.on_run([cmd], file_regex), message[0], message[1], lambda: None)


class Default():

    def __init__(self, tex_file, root_file):
        # Save tex and root file
        self.tex_file = tex_file
        self.root_file = root_file

        self.terminated = False

        self.errors = []
        self.warnings = []

    def terminate(self):
        return False

    def run(self, cmds):
        settings = tools.load_settings("LaTeXing", build_arguments=[], forward_sync=False, log=False, reverse_sync=False)

        # Save file path
        self.file_path = self.root_file.file_path

        # Get pdf_name_root for the jobname
        pdf_name = self.root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get output_directory
        output_directory = self.root_file.output_directory()

        # Set self.log_path to check later for errors
        self.log_path = tools.add_extension(os.path.join(output_directory, pdf_name_root), ".log")

        # Remove the fls file is a bug from windows and the synctex file is just required if synctex is enabled
        self.clean_file_paths = [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".fls")] if self.root_file.file_dir != output_directory else []
        self.clean_file_paths += [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".synctex.gz")] if not (settings['forward_sync'] or settings['reverse_sync']) else []
        self.clean_file_paths += [os.path.join(self.root_file.file_dir, self.root_file.file_name_root + ".ptex")]

        # Update citations
        self.update_remote_bibliography()

        # Build path to copy generated pdf file
        self.src_pdf_path = os.path.join(output_directory, pdf_name)
        self.dst_pdf_path = os.path.join(self.root_file.file_dir, pdf_name)

        # Build path to copy generated synctex file
        synctex_name = tools.add_extension(pdf_name_root, ".synctex.gz")
        self.src_synctex_path = os.path.join(output_directory, synctex_name) if settings['forward_sync'] or settings['reverse_sync'] else None
        self.dst_synctex_path = os.path.join(self.root_file.file_dir, synctex_name) if settings['forward_sync'] or settings['reverse_sync'] else None

        # Debug
        log.info("tex_path: %s" % self.root_file.file_dir)
        log.info("output_directory: %s" % output_directory)
        log.info("pdf_name_root: %s" % pdf_name_root)

        # Own check, perhaps this needs to become more in the future
        self.errors = []
        self.warnings = check_source.check_remote_bibfile(self.file_path) + check_source.check_linked_bib_files(self.file_path)

        # Run different commands
        for cmd in cmds:
            # Debug output
            log.info("cmd: %s" % " ".join(cmd))

            # Adjust cmd line with file, outdir, synctex, pdfname
            replace = {"file": self.file_path, "filebase": os.path.join(output_directory, pdf_name_root), "pdfname": pdf_name_root, "outdir": output_directory, "synctex": "1" if settings['forward_sync'] or settings['reverse_sync'] else "0"}
            for key, value in replace.items():
                cmd = [s.replace("{%s}" % key, value) for s in cmd]

            if settings["build_arguments"]:
                cmd = [cmd[0]] + settings["build_arguments"] + cmd[1:]

            # Use lualatex or xelatex with latexmk if used
            if "latexmk" not in cmd[0]:
                pass
            elif self.tex_file.get_option("program") == "lualatex":
                cmd = [cmd[0]] + ["-pdflatex=lualatex"] + cmd[1:]
            elif self.tex_file.get_option("program") == "xelatex":
                cmd = [cmd[0]] + ["-pdflatex=xelatex"] + cmd[1:]

            # Typeset the file
            try:
                proc = terminal.popen(cmd)
                communicate = proc.communicate()

                # Save stdout
                if settings["log"] and communicate[0].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stdout.log"), "w") as f:
                        f.write(communicate[0].decode(sys.getfilesystemencoding()))

                # Save stderr
                if settings["log"] and communicate[1].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stderr.log"), "w") as f:
                        f.write(communicate[1].decode(sys.getfilesystemencoding()))

            except Exception as e:
                log.error(e)
                self.errors = ["COULD NOT COMPILE! \"%s\"" % " ".join(cmd)]
                break

        return self.terminated

    def on_post_log_parse(self, errors, warnings, badboxes):
        return errors, warnings, badboxes

    def update_remote_bibliography(self):
        settings = tools.load_settings("LaTeXing", bibname="Remote.bib", update_remote_bibliography=True)

        # Fetch all available remote citations
        remote_cites = {item.key: item for file_path, item in cite.find_remote_cites()}
        if settings["update_remote_bibliography"] and remote_cites:
            # Just search through the remote bib file, defined in the settings
            bib_path = os.path.join(os.path.dirname(self.tex_file.root_file_path()), settings["bibname"])

            bib_file = cache.BibFile(bib_path)
            bib_file.run()

            cites = []
            for key in bib_file.cite_keys():
                if key in remote_cites and remote_cites[key].string(plain=True) != bib_file.cite_source(key):
                    cites += [remote_cites[key]]
                    log.debug(key)
                    log.debug(bib_file.cite_source(key))
                    log.debug(remote_cites[key].string(plain=True))

            # save cites in bib file and update cache
            if cites and sublime.ok_cancel_dialog("%d Citation(s) in %s have been updated in your remote bibliography, update the item(s) prior the typeset?" % (len(cites), bib_file.file_name), "Update"):
                bib_file.update_cites(cites)
                bib_file.save()
                sublime.run_command("ltx_save_cache", {"mode": ["bib.cache"]})


class Partial(Default):

    def run(self, cmds):
        settings = tools.load_settings("LaTeXing", build_arguments=[], default_bib_extension=".bib", forward_sync=False, log=False, reverse_sync=False)

        # Save file path
        self.file_path = os.path.join(self.root_file.file_dir, self.root_file.file_name_root + ".ptex")

        # Check if partial mode for subfile class
        if self.tex_file.documentclass(root=False)[0] == "subfiles":
            include = "\\subfile{%s}" % os.path.relpath(self.tex_file.file_path, self.root_file.file_dir).replace(os.sep, "/")
        else:
            include = "\\input{%s}" % os.path.relpath(self.tex_file.file_path, self.root_file.file_dir).replace(os.sep, "/")

        # Check the used bibliography system, biblatex oder bibtex
        if "biblatex" in [item for file_path, item in self.root_file.get("packages")]:
            bibliography = "\n\\printbibliography" if self.tex_file.get("cite", root=False) else ""
        else:
            expr = self.root_file.get_source(r"\\bibliographystyle\{(?P<style>.+?)\}")
            bibliographystyle = expr.group("style") if expr else "plain"
            bibliography = "\n\\bibliographystyle{%s}\n\\bibliography{%s}" % (bibliographystyle, ",".join([os.path.relpath(tools.remove_extension(item, settings["default_bib_extension"]), self.root_file.file_dir).replace(os.sep, "/") for item in self.root_file.bibliography()])) if self.tex_file.get("cite", root=False) else ""

        root_content = self.root_file.read_file_content(raw=True)

        # Search for % (BEGIN PARTIAL) if not found look for begin document
        root_begin = re.sub(r"\%\s*\(PARTIAL\).*" if re.search(r"\%\s*\(PARTIAL\)", root_content) else r"(?<=\\begin\{document\}).*", "", root_content, 0, re.DOTALL).strip()
        root_end = re.sub(r".+(?=\\end\{document\})", "", root_content, 0, re.DOTALL).strip()

        # Append begin document if not available
        if "\\begin{document}" not in root_begin:
            root_begin += "\n\\begin{document}"

        partial_begin = root_begin + "\n"
        partial_end = "\n" + root_end

        temp_content = partial_begin + include + bibliography + partial_end

        # save the file for the partial build
        with open(self.file_path, "w", encoding=tools.detect_encoding()) as f:
            f.write(temp_content)

        # Get pdf_name_root for the jobname
        pdf_name = self.root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get output_directory
        output_directory = self.tex_file.output_directory(os.path.join("partial", self.tex_file.file_name_root))

        # Set self.log_path to check later for errors
        self.log_path = tools.add_extension(os.path.join(output_directory, pdf_name_root), ".log")
        # Remove the fls file is a bug from windows and the synctex file is just required if synctex is enabled
        self.clean_file_paths = [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".fls")] if self.root_file.file_dir != output_directory else []
        self.clean_file_paths += [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".synctex.gz")] if not (settings['forward_sync'] or settings['reverse_sync']) else []

        # Update citations
        self.update_remote_bibliography()

        # Build path to copy generated pdf file
        self.src_pdf_path = os.path.join(output_directory, pdf_name)
        self.dst_pdf_path = os.path.join(self.root_file.file_dir, pdf_name)

        # Build path to copy generated synctex file
        synctex_name = tools.add_extension(pdf_name_root, ".synctex.gz")
        self.src_synctex_path = os.path.join(output_directory, synctex_name) if settings['forward_sync'] or settings['reverse_sync'] else None
        self.dst_synctex_path = os.path.join(self.root_file.file_dir, synctex_name) if settings['forward_sync'] or settings['reverse_sync'] else None

        # Debug
        log.info("tex_path: %s" % self.root_file.file_dir)
        log.info("output_directory: %s" % output_directory)
        log.info("pdf_name_root: %s" % pdf_name_root)

        # Own check, perhaps this needs to become more in the future
        self.errors = []
        self.warnings = check_source.check_remote_bibfile(self.root_file.file_path) + check_source.check_linked_bib_files(self.root_file.file_path)

        # Run different commands
        for cmd in cmds:

            # Debug output
            log.info("cmd: %s" % " ".join(cmd))

            # Adjust cmd line with file, outdir, synctex, pdfname
            replace = {"file": self.file_path, "filebase": os.path.join(output_directory, pdf_name_root), "pdfname": pdf_name_root, "outdir": output_directory, "synctex": "1" if settings['forward_sync'] or settings['reverse_sync'] else "0"}
            for key, value in replace.items():
                cmd = [s.replace("{%s}" % key, value) for s in cmd]

            if settings["build_arguments"]:
                cmd = [cmd[0]] + settings["build_arguments"] + cmd[1:]

            # Use lualatex or xelatex if and latexmk in use
            if "latexmk" not in cmd[0]:
                pass
            elif self.tex_file.get_option("program") == "lualatex":
                cmd = [cmd[0]] + ["-pdflatex=lualatex"] + cmd[1:]
            elif self.tex_file.get_option("program") == "xelatex":
                cmd = [cmd[0]] + ["-pdflatex=xelatex"] + cmd[1:]

            # Typeset the file
            try:
                proc = terminal.popen(cmd)
                communicate = proc.communicate()

                # Save stdout
                if settings["log"] and communicate[0].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stdout.log"), "w") as f:
                        f.write(communicate[0].decode(sys.getfilesystemencoding()))

                # Save stderr
                if settings["log"] and communicate[1].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stderr.log"), "w") as f:
                        f.write(communicate[1].decode(sys.getfilesystemencoding()))

            except Exception as e:
                log.error(e)
                self.errors = ["COULD NOT COMPILE! \"%s\"" % " ".join(cmd)]
                break

        return self.terminated

    def on_post_log_parse(self, errors, warnings, badboxes):
        labels = [item["arguments"][0].split(":", 1)[1] for file_path, item in self.tex_file.get("label")]
        warnings = [item for item in warnings if not any([label in item for label in labels])]

        # Remove last warning of everything was fixed
        rex = re.compile(r"Reference\s.+?\sundefined")
        if not any([rex.search(warning) for warning in warnings]):
            warnings = [warning for warning in warnings if "There were undefined references." not in warning]

        return errors, warnings, badboxes


class Knitr(Default):

    def run(self, cmds):
        settings = tools.load_settings("LaTeXing", build_arguments=[], forward_sync=False, log=False, reverse_sync=False, knitr_command="Rscript -e \"library(knitr); knit('{file}')\"")

        # Save file path
        self.file_path = os.path.join(self.root_file.file_dir, self.root_file.file_name_root + ".tex")

        # rscript knitr command
        cmd = "{rscript} -e \"library(knitr); knit('{file}')\""

        replace = {"rscript": terminal.find_executable('rscript'), "file": self.root_file.file_name}
        for key, value in replace.items():
            cmd = cmd.replace("{%s}" % key, value)

        try:
            stdout, sterr = terminal.communicate(cmd, shell=True)
            self.errors = ["E: %s:0 %s" % (self.root_file.file_path, line.strip()) for line in sterr.split("\n") if line.strip()[0:5] == "Error"]
        except Exception as e:
            log.error(e)
            self.errors += ["COULD NOT COMPILE! \"%s\"" % cmd]

        # Break if errors
        if self.errors:
            return

        # Get pdf_name_root for the jobname
        pdf_name = self.root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get output_directory
        output_directory = self.tex_file.output_directory()

        # Set self.log_path to check later for errors
        self.log_path = tools.add_extension(os.path.join(output_directory, pdf_name_root), ".log")

        # Remove the fls file is a bug from windows and the synctex file is just required if synctex is enabled
        self.clean_file_paths = [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".fls")] if self.root_file.file_dir != output_directory else []
        self.clean_file_paths += [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".synctex.gz")] if not (settings['forward_sync'] or settings['reverse_sync']) else []
        self.clean_file_paths += [os.path.join(self.root_file.file_dir, self.root_file.file_name_root + ".ptex")]

        # Update citations
        self.update_remote_bibliography()

        # Build path to copy generated pdf file
        self.src_pdf_path = os.path.join(output_directory, pdf_name)
        self.dst_pdf_path = os.path.join(self.root_file.file_dir, pdf_name)

        # Build path to copy generated synctex file
        self.src_synctex_path = None
        self.dst_synctex_path = None

        # Debug
        log.info("tex_path: %s" % self.root_file.file_dir)
        log.info("output_directory: %s" % output_directory)
        log.info("pdf_name_root: %s" % pdf_name_root)

        # Own check, perhaps this needs to become more in the future
        self.errors = []
        self.warnings = check_source.check_remote_bibfile(self.root_file.file_path) + check_source.check_linked_bib_files(self.root_file.file_path)

        # Run different commands
        for cmd in cmds:

            # Debug output
            log.info("cmd: %s" % " ".join(cmd))

            # Adjust cmd line with file, outdir, synctex, pdfname
            replace = {"file": self.file_path, "filebase": os.path.join(output_directory, pdf_name_root), "pdfname": pdf_name_root, "outdir": output_directory, "synctex": "1" if settings['forward_sync'] or settings['reverse_sync'] else "0"}
            for key, value in replace.items():
                cmd = [s.replace("{%s}" % key, value) for s in cmd]

            if settings["build_arguments"]:
                cmd = [cmd[0]] + settings["build_arguments"] + cmd[1:]

            # Use lualatex or xelatex if and latexmk in use
            if "latexmk" not in cmd[0]:
                pass
            elif self.tex_file.get_option("program") == "lualatex":
                cmd = [cmd[0]] + ["-pdflatex=lualatex"] + cmd[1:]
            elif self.tex_file.get_option("program") == "xelatex":
                cmd = [cmd[0]] + ["-pdflatex=xelatex"] + cmd[1:]

            # Typeset the file
            try:
                proc = terminal.popen(cmd)
                communicate = proc.communicate()

                # Save stdout
                if settings["log"] and communicate[0].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stdout.log"), "w") as f:
                        f.write(communicate[0].decode(sys.getfilesystemencoding()))

                # Save stderr
                if settings["log"] and communicate[1].decode(sys.getfilesystemencoding()):
                    with open(os.path.join(output_directory, pdf_name_root + ".stderr.log"), "w") as f:
                        f.write(communicate[1].decode(sys.getfilesystemencoding()))

            except Exception as e:
                log.error(e)
                self.errors = ["COULD NOT COMPILE! \"%s\"" % " ".join(cmd)]
                break

        return self.terminated


class Tikz(Default):

    def terminate(self):
        try:
            self.proc.kill()
            self.terminated = True
        except:
            self.terminated = True
        return True

    def run(self, cmds):
        settings = tools.load_settings("LaTeXing", build_arguments=[])

        # Save file path
        self.file_path = os.path.join(self.root_file.file_dir, self.root_file.file_name_root + ".ptex")

        # Get pdf_name_root for the jobname
        pdf_name = self.root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get output_directory
        output_directory = self.tex_file.output_directory(os.path.join("tikz", self.tex_file.file_name_root))

        # Set self.log_path to check later for errors
        self.log_path = tools.add_extension(os.path.join(output_directory, pdf_name_root), ".log")

        # Include tkiz as input
        include = "\\input{%s}" % os.path.relpath(self.tex_file.file_path, self.root_file.file_dir).replace(os.sep, "/")
        include = self.tex_file.read_file_content(raw=True)

        # Get root contecnt as raw
        root_content = self.root_file.read_file_content(raw=True)

        root_begin = re.sub(r"\%\s*\(TIKZ\).*" if re.search(r"\%\s*\(TIKZ\)", root_content) else r"(?<=\\begin\{document\}).*", "", root_content, 0, re.DOTALL).strip()
        root_end = re.sub(r".+(?=\\end\{document\})", "", root_content, 0, re.DOTALL).strip()

        usepackage = "\\usepackage[graphics,active,tightpage]{preview}\n\setlength\PreviewBorder{2mm}\n\\PreviewEnvironment{tikzpicture}\n"

        # Append begin document if not available
        if "\\begin{document}" not in root_begin:
            root_begin += "\n\\begin{document}"

        # Add necessary use packages
        root_begin = root_begin.replace("\\begin{document}", usepackage + "\n\\begin{document}", 1)

        partial_begin = root_begin + "\n"
        partial_end = "\n" + root_end

        self.line_offset = partial_begin.count("\n")
        temp_content = partial_begin + include + partial_end

        # save the file for the partial build
        with open(self.file_path, "w", encoding=tools.detect_encoding()) as f:
            f.write(temp_content)

        # Remove the fls file is a bug from windows and the synctex file is just required if synctex is enabled
        self.clean_file_paths = [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".fls")] if self.root_file.file_dir != output_directory else []
        self.clean_file_paths += [tools.add_extension(os.path.join(self.root_file.file_dir, pdf_name_root), ".synctex.gz")]

        # Build path to copy generated pdf file
        self.src_pdf_path = os.path.join(output_directory, pdf_name)
        self.dst_pdf_path = os.path.join(self.root_file.file_dir, pdf_name)

        # Build path to copy generated synctex file
        self.src_synctex_path = None
        self.dst_synctex_path = None

        # Debug
        log.info("tex_path: %s" % self.root_file.file_dir)
        log.info("output_directory: %s" % output_directory)
        log.info("pdf_name_root: %s" % pdf_name_root)

        # Run first command
        cmd = cmds[0]

        # Adjust cmd line with file, outdir, synctex, pdfname
        replace = {"file": self.file_path, "pdfname": pdf_name_root, "outdir": output_directory}
        for key, value in replace.items():
            cmd = [s.replace("{%s}" % key, value) for s in cmd]

        if settings["build_arguments"]:
            cmd = [cmd[0]] + settings["build_arguments"] + cmd[1:]

        # Use lualatex or xelatex if and latexmk in use
        if "latexmk" not in cmd[0]:
            pass
        elif self.tex_file.get_option("program") == "lualatex":
            cmd = [cmd[0]] + ["-pdflatex=lualatex"] + cmd[1:]
        elif self.tex_file.get_option("program") == "xelatex":
            cmd = [cmd[0]] + ["-pdflatex=xelatex"] + cmd[1:]

        # Debug output
        log.info("cmd: %s" % " ".join(cmd))

        # Typeset the file
        try:
            self.proc = terminal.popen(cmd)
            self.proc.wait()
            return self.terminated
        except Exception as e:
            log.error(e)
            self.errors = ["COULD NOT COMPILE! \"%s\"" % " ".join(cmd)]

    def on_post_log_parse(self, errors, warnings, badboxes):
        # Fix line numbers
        errors = [re.sub(r"(?<=\w:\s)" + self.file_path.replace(os.sep, "/"), self.tex_file.file_path.replace(os.sep, "/"), item, 0, re.IGNORECASE) for item in errors]
        warnings = [re.sub(r"(?<=\w:\s)" + self.file_path.replace(os.sep, "/"), self.tex_file.file_path.replace(os.sep, "/"), item, 0, re.IGNORECASE) for item in warnings]
        badboxes = [re.sub(r"(?<=\w:\s)" + self.file_path.replace(os.sep, "/"), self.tex_file.file_path.replace(os.sep, "/"), item, 0, re.IGNORECASE) for item in badboxes]

        # Fix the line number
        errors = [re.sub(r"(?<=:)(\d+)", lambda m: str(int(m.group(1)) - self.line_offset), item) for item in errors]
        warnings = [re.sub(r"(?<=:)(\d+)", lambda m: str(int(m.group(1)) - self.line_offset), item) for item in warnings]
        badboxes = [re.sub(r"(?<=:)(\d+)", lambda m: str(int(m.group(1)) - self.line_offset), item) for item in badboxes]

        # Remove warning about missing aux
        warnings = [item for item in warnings if "No file %s.aux" % self.tex_file.file_name_root in item]

        return errors, warnings, badboxes

    def on_post_run(self):
        try:
            settings = tools.load_settings("LaTeXing", tikz_create_pdf=False)
            if settings["tikz_create_pdf"]:
                shutil.copyfile(self.dst_pdf_path, os.path.join(self.tex_file.file_dir, self.tex_file.file_name_root + ".pdf"))
        except Exception as e:
            print(e)
            sublime.error_message("Could not copy the generated pdf of your tikz picture. Close the pdf viewer to reset the file access or other permission problems.")
