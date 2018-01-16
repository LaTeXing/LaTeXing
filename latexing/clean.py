import sublime
import sublime_plugin

import os.path
import shutil

from . import LTX_TEMPDIR
from . import cache
from . import logger
from . import output
from . import tools

log = logger.getLogger(__name__)


class LtxCleanCommand(sublime_plugin.WindowCommand):

    def run(self, cmd="", cmd_qb=[], file_regex="", path=""):
        # Load Settings
        settings = tools.load_settings("LaTeXing", knitr=False, partial_build=False, tikz=False)

        # Init and clear output_view
        panel = output.Panel(self.window)

        view = self.window.active_view()

        patterns_ex = ["*.tex", "*.bib", "*.pdf"]
        patterns_in = [
            "*.aux",
            "*.bbl",
            "*.bcf",
            "*.blg",
            "*.d",
            "*.fdb_latexmk",
            "*.fls",
            "*.ilg",
            "*.ind",
            "*.lof",
            "*.log",
            "*.log",
            "*.lot",
            "*.make",
            "*.nav",
            "*.out",
            "*.pdfsync"
            "*.ptex",
            "*.run.cookie",
            "*.run.xml",
            "*.snm",
            "*.stderr.log",
            "*.stdout.log",
            "*.synctex",
            "*.synctex.gz",
            "*.tdo",
            "*.toc",
            "*.toc.make",
            "*.vrb"
        ]

        # Parse tex file
        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        # Parse root file
        root_file = tex_file.root_file()
        root_file.run()

        # Get pdf_name_root for the jobname
        pdf_name = root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get output_directory
        if settings["knitr"] and tex_file.file_name_ext.lower() in [".rnw", ".snw", ".rtex"]:
            output_directory = tex_file.output_directory(os.path.join("knitr", tex_file.file_name_root))

        elif settings["tikz"] and tex_file.file_name_ext.lower() in [".tikz"]:
            output_directory = tex_file.output_directory(os.path.join("tikz", tex_file.file_name_root))

        elif settings["partial_build"] and tex_file.file_path != root_file.file_path:
            output_directory = tex_file.output_directory(os.path.join("partial", tex_file.file_name_root))

        else:
            output_directory = tex_file.output_directory()

        panel.log(["[Start Cleanup %s]" % output_directory, ""])
        try:
            if not os.path.isdir(output_directory):
                raise IOError

            # List Fules in output_directoryectory by using patterns and delete files afterwards
            items = tools.list_dir(output_directory, patterns_in, patterns_ex, walk=False)
            files = [os.path.join(output_directory, item["file_name"]) for item in items]
            messages = tools.delete_files(files)

            if not messages:
                messages = "Nothing to clean!!"

            # Log and cleanup
            panel.log(messages)
            panel.log(["", "[Finished!]"])
        except Exception as e:
            log.error(e)
            panel.log("[Abort Clean!! Cannot find or access output directory %s]" % output_directory)


class LtxCleanTempCommand(sublime_plugin.WindowCommand):

    def run(self):
        if sublime.ok_cancel_dialog("Delete %s completely?" % LTX_TEMPDIR, "Delete"):
            shutil.rmtree(LTX_TEMPDIR, ignore_errors=True)
