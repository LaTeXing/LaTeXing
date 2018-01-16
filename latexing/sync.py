import sublime
import sublime_plugin

from . import bib
from . import cache
from . import logger
from . import progress
from . import tools

log = logger.getLogger(__name__)


class LtxSyncBibFileCommand(sublime_plugin.WindowCommand):

    def is_enabled(self):
        try:
            view = self.window.active_view()
            return view.match_selector(0, "text.tex.latex") or view.match_selector(0, "text.bibtex")
        except:
            return False

    def run(self):
        message = ["Synchronising Bibliography Files...", "Synchronised Bibliography Files"]
        progress.progress_function(self.__run, message[0], message[1], lambda: sublime.run_command("ltx_save_cache", {"mode": ["bib.cache"]}))

    def __run(self):
        settings = tools.load_settings("LaTeXing", bibsonomy=False, citeulike=False, global_bib_file=False, global_bib_file_path="", mendeley=False, zotero=False)
        remote_cites = {}

        if settings["bibsonomy"]:
            bibsonomy_file = cache.BibsonomyFile()
            bibsonomy_file.run()
            remote_cites.update({item["key"]: bib.BibItem(item["key"], file_path, item["type"], item["fields"]) for file_path, item in bibsonomy_file.get("cites") if item["key"] not in remote_cites})

        if settings["citeulike"]:
            citeulike_file = cache.CiteulikeFile()
            citeulike_file.run()
            remote_cites.update({item["key"]: bib.BibItem(item["key"], file_path, item["type"], item["fields"]) for file_path, item in citeulike_file.get("cites") if item["key"] not in remote_cites})

        if settings["mendeley"]:
            mendeley_file = cache.MendeleyFile()
            mendeley_file.run()
            remote_cites.update({item["key"]: bib.BibItem(item["key"], file_path, item["type"], item["fields"]) for file_path, item in mendeley_file.get("cites") if item["key"] not in remote_cites})

        if settings["zotero"]:
            zotero_file = cache.ZoteroFile()
            zotero_file.run()
            remote_cites.update({item["key"]: bib.BibItem(item["key"], file_path, item["type"], item["fields"]) for file_path, item in zotero_file.get("cites") if item["key"] not in remote_cites})

        if settings["global_bib_file"]:
            bib_file = cache.BibFile(settings["global_bib_file_path"])
            bib_file.run()
            remote_cites.update({item["key"]: bib.BibItem(item["key"], file_path, item["type"], item["fields"]) for file_path, item in bib_file.get("cites") if item["key"] not in remote_cites})

        if self.window.active_view().match_selector(0, "text.bibtex"):
            if self.window.active_view().is_dirty():
                self.window.active_view().settings().set("save_is_dirty", True)
                self.window.active_view().run_command('save')

            bib_file = cache.BibFile(self.window.active_view().file_name())
            bib_file.run()
            cites = []
            for key in bib_file.cite_keys():
                if key in remote_cites and remote_cites[key].string(plain=True) != bib_file.cite_source(key):
                    cites += [remote_cites[key]]
                    log.debug("%s" % key)
            if cites and sublime.ok_cancel_dialog("%d Citation(s) have been updated in your remote bibliography, update the item(s) now?" % len(cites), "Update"):
                bib_file.update_cites(cites)
                bib_file.save()
        else:
            tex_file = cache.TeXFile(self.window.active_view().file_name())
            tex_file.run()

            root_file = tex_file.root_file()
            root_file.run()

            for bib_path in root_file.bibliography():
                bib_file = cache.BibFile(bib_path)
                bib_file.run()
                keys = bib_file.cite_keys()

                cites = []
                for key in keys:
                    if key in remote_cites and remote_cites[key].string(plain=True) != bib_file.cite_source(key):
                        cites += [remote_cites[key]]
                        log.debug("%s" % key)
                if cites and sublime.ok_cancel_dialog("%d Citation(s) in %s have been updated in your remote bibliography, update the item(s) now?" % (len(cites), bib_file.file_name), "Update"):
                    bib_file.update_cites(cites)
                    bib_file.save()


class LtxSyncDataCommand(sublime_plugin.ApplicationCommand):

    def run(self, mode=["bibsonomy", "citeulike", "mendeley", "zotero"]):

        if tools.LtxSettings().get("ltx_offline", False):
            sublime.error_message("Your are working in the offline mode, synchronisation is not available.")
            return

        if tools.LtxSettings().get("ltx_sync_data", False):
            sublime.error_message("The synchronisation is already running, please wait!")
            return

        if tools.LtxSettings().get("ltx_rebuild_cache", False):
            sublime.error_message("The cache is rebuilding, please wait!")
            return

        tools.LtxSettings().set("ltx_sync_data", True)

        message = ["Synchronising Remote Data...", "Synchronised Remote Data"]
        progress.progress_function(lambda: self.__run(mode), message[0], message[1], lambda: sublime.run_command("ltx_save_cache", {"mode": ["bibsonomy.cache", "citeulike.cache", "mendeley.cache", "zotero.cache"]}))

    def __run(self, mode):

        error = False
        settings = tools.load_settings("LaTeXing", bibsonomy=False, citeulike=False, mendeley=False, zotero=False)

        if settings["bibsonomy"] and "bibsonomy" in mode:
            bibsonomy_file = cache.BibsonomyFile()
            bibsonomy_file.run(synchronise=True)

            error = bibsonomy_file.status != "Ok"

            if bibsonomy_file.status == "Error" and sublime.ok_cancel_dialog("Error while fetching data from Bibsonomy.org. Would like to switch to the offline mode?", "Yes"):
                tools.LtxSettings().set("ltx_offline", True)

        if settings["citeulike"]:
            citeulike_file = cache.CiteulikeFile()
            citeulike_file.run(synchronise=True)

            error = citeulike_file.status != "Ok"

            if citeulike_file.status == "Error" and sublime.ok_cancel_dialog("Error while fetching data from Citeulike.org. Would like to switch to the offline mode?", "Yes"):
                tools.LtxSettings().set("ltx_offline", True)

        if settings["mendeley"] and "mendeley" in mode:
            mendeley_file = cache.MendeleyFile()
            mendeley_file.run(synchronise=True)

            error = mendeley_file.status != "Ok"

            if mendeley_file.status == "Error" and sublime.ok_cancel_dialog("Error while fetching data from Mendeley.com. Would like to switch to the offline mode?", "Yes"):
                tools.LtxSettings().set("ltx_offline", True)

        if settings["zotero"] and "zotero" in mode:
            zotero_file = cache.ZoteroFile()
            zotero_file.run(synchronise=True)

            error = zotero_file.status != "Ok"

            if zotero_file.status == "Error" and sublime.ok_cancel_dialog("Error while fetching data from Zotero.org. Would like to switch to the offline mode?", "Yes"):
                tools.LtxSettings().set("ltx_offline", True)

        tools.LtxSettings().set("ltx_sync_data", False)

        if not error:
            try:
                sublime.set_timeout(sublime.active_window().run_command("ltx_sync_bib_file"), 0)
            except:
                pass
