import sublime
import sublime_plugin

import os.path

from . import bib
from . import cache
from . import logger
from . import output
from . import progress
from . import tools

log = logger.getLogger(__name__)

json_lang = {
    "bibsonomy": ["Bibsonomy.org", "Import References from Bibsonomy.org"],
    "citeulike": ["Citeulike.org", "Import References from Citeulike.org"],
    "mendeley": ["Mendeley.com", "Import References from Mendeley.com"],
    "zotero": ["Zotero.org", "Import References from Zotero.org"],
    "global_bib_file": ["Global Bibliography", "Import References from a global bibliography file."],
    "normal": ["Reference", "Import a reference, listed in alphabetic order"],
    "missing": ["Missing Reference", "Import multiple references, find by missing keys in tex file and listed in alphabetic order"],
    "tag": ["Reference ordered by a tag", "Import references ordered by their tag"],
    "folder": ["Reference ordered by a folder", "Import references ordered by a folder"]
}


def find_remote_cites(args=[]):
    settings = tools.load_settings("LaTeXing", bibsonomy=False, citeulike=False, mendeley=False, zotero=False, global_bib_file=False, global_bib_file_path=[])
    remote_args = []
    keys = [post.key for file_path, post in args]

    if settings["bibsonomy"]:
        bibsonomy_file = cache.BibsonomyFile()
        bibsonomy_file.run(fill_source=True)
        remote_args += [[file_path, item] for file_path, item in bibsonomy_file.get_cites() if item.key not in keys]
        keys += [post.key for file_path, post in remote_args]

    if settings["citeulike"]:
        cite_u_like_file = cache.CiteulikeFile()
        cite_u_like_file.run(fill_source=True)
        remote_args += [[file_path, item] for file_path, item in cite_u_like_file.get_cites() if item.key not in keys]
        keys += [post.key for file_path, post in remote_args]

    if settings["global_bib_file"]:
        bib_file = cache.GlobalBibFile(settings["global_bib_file_path"])
        bib_file.file_name = "Global Bibliography - %s" % os.path.basename(settings["global_bib_file_path"])
        bib_file.run()
        remote_args += [[bib_file.file_name, item] for file_path, item in bib_file.cites() if item.key not in keys]

    if settings["mendeley"]:
        mendeley_file = cache.MendeleyFile()
        mendeley_file.run(fill_source=True)
        remote_args += [[file_path, item] for file_path, item in mendeley_file.get_cites() if item.key not in keys]
        keys += [post.key for file_path, post in remote_args]

    if settings["zotero"]:
        zotero_file = cache.ZoteroFile()
        zotero_file.run(fill_source=True)
        remote_args += [[file_path, item] for file_path, item in zotero_file.get_cites() if item.key not in keys]
        keys += [post.key for file_path, post in remote_args]

    return remote_args


class LtxCiteImportCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        try:
            return self.view.file_name() is not None and (self.view.match_selector(0, "text.tex.latex") or self.view.match_selector(0, "text.bibtex"))
        except:
            return False

    def choose_source(self):
        def on_done(i):
            if i < 0:
                self.infos += ["No source selected"]
                self.log()
            else:
                if "infos" in self.settings["show_log_panel_on"]:
                    self.logPanel.show()
                self.fetch_cites(self.sources[i])

        if len(self.sources) == 1:
            sublime.status_message("Only one remote source available; using %s" % json_lang[self.sources[0]["id"]][0])
            on_done(0)
        else:
            message = [json_lang[source["id"]] for source in self.sources]
            sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done), 0)

    def fetch_cites(self, source):
        log.debug(source)

        source_file = None
        if source["id"] == "bibsonomy":
            source_file = cache.BibsonomyFile()
            self.logPanel.log("[Accessing Bibsonomy.org]\n")
            message = ["Searching on Bibsonomy...", "Finished Searching"]

            def on_done():
                items = source_file.get_cites()
                if source_file.status == "Error":
                    self.errors += ["Checked Bibsonomy access and access denied"]
                    self.log()
                elif not items:
                    self.errors += ["Checked Bibsonomy and no remote items available"]
                    self.log()
                else:
                    cites = []
                    for file_path, item in items:
                        cites += [item] if item.key not in self.keys else []
                    if not cites:
                        self.import_cites(cites)
                    else:
                        self.choose_mode(source, cites)

        elif source["id"] == "citeulike":
            source_file = cache.CiteulikeFile()
            self.logPanel.log("[Accessing Citeulike.org]\n")
            message = ["Searching on Citeulike...", "Finished Searching"]

            def on_done():
                items = source_file.get_cites()
                if source_file.status == "Error":
                    self.errors += ["Checked Citeulike access and access denied"]
                    self.log()
                elif not items:
                    self.errors += ["Checked Citeulike and no remote items available"]
                    self.log()
                else:
                    cites = []
                    for file_path, item in items:
                        cites += [item] if item.key not in self.keys else []
                    if not cites:
                        self.import_cites(cites)
                    else:
                        self.choose_mode(source, cites)

        elif source["id"] == "mendeley":
            source_file = cache.MendeleyFile()
            self.logPanel.log("[Accessing Mendeley.com]\n")
            message = ["Searching on Mendeley...", "Finished Searching"]

            def on_done():
                items = source_file.get_cites()
                if source_file.status == "Error":
                    self.errors += ["Checked Mendeley access and access denied"]
                    self.log()
                elif not items:
                    self.errors += ["Checked Mendeley and no remote items available"]
                    self.log()
                else:
                    cites = []
                    for file_path, item in items:
                        cites += [item] if item.key not in self.keys else []
                    if not cites:
                        self.import_cites(cites)
                    else:
                        self.choose_mode(source, cites)

        elif source["id"] == "zotero":
            source_file = cache.ZoteroFile()
            self.logPanel.log("[Accessing Zotero.com]\n")
            message = ["Searching on Zotero...", "Finished Searching"]

            def on_done():
                items = source_file.get_cites()
                if source_file.status == "Error":
                    self.errors += ["Checked Zotero access and access denied"]
                    self.log()
                elif not items:
                    self.errors += ["Checked Zotero and no remote items available"]
                    self.log()
                else:
                    cites = []
                    for file_path, item in items:
                        cites += [item] if item.key not in self.keys else []
                    if not cites:
                        self.import_cites(cites)
                    else:
                        self.choose_mode(source, cites)

        elif source["id"] == "global_bib_file":
            self.logPanel.log("[Accessing %s]\n" % os.path.basename(self.settings["global_bib_file_path"]))
            source_file = cache.BibFile(self.settings["global_bib_file_path"])
            message = ["Searching on %s..." % "Library.bib", "Finished Searching"]

            def on_done():
                items = source_file.get("cites")
                if source_file.error:
                    self.errors += ["Checked global bibliography and access denied"]
                    self.log()
                elif not items:
                    self.errors += ["Checked global bibliography and no items available"]
                    self.log()
                else:
                    cites = []
                    for file_path, item in items:
                        cites += [bib.BibItem(item["key"], os.path.basename(self.settings["global_bib_file_path"]), item["type"], item["fields"])] if item["key"] not in self.keys else []
                    if not cites:
                        self.import_cites(cites)
                    else:
                        self.choose_mode(source, cites)

        progress.progress_function(source_file.run, message[0], message[1], on_done)

    def choose_mode(self, source, cites):
        log.debug(source)

        message = [json_lang[mode] for mode in source["data"]]

        def on_done(i):
            if i < 0:
                self.infos += ["No mode selected"]
                self.log()
            else:
                self.get_cites(source["data"][i], cites)
        sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done), 0)

    def get_cites(self, mode, cites):
        if mode == "normal":
            self.choose_cites(sorted(cites, key=lambda x: x.key.lower(), reverse=False), import_all="Import all available references")
        elif mode == "tag":
            self.choose_tag(cites)
        elif mode == "folder":
            self.choose_folder(cites)
        elif mode == "missing":
            cites = [cite for cite in cites if cite.key in self.missing_keys]
            self.choose_cites(cites, import_all="Import all references by their missing key")

    def choose_tag(self, cites):
        tags = {}
        for cite in cites:
            for tag in cite.tags:
                tags[tag] = tags[tag] + 1 if tag in tags else 1
        items = sorted([[key, value] for key, value in tags.items()], key=lambda x: x[1], reverse=True)
        message = [["%s (%d)" % (key, value)] for key, value in items]

        def on_done(i):
            if i < 0:
                self.infos += ["No tag selected"]
                self.log()
            else:
                self.choose_cites([cite for cite in cites if items[i][0] in cite.tags], import_all="Import all references with the tag \"%s\"." % items[i][0])
        if tags:
            sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done), 0)
        else:
            self.warnings += ["No tags available"]
            self.log()

    def choose_folder(self, cites):
        folders = {}
        for cite in cites:
            for folder in cite.folders:
                folders[folder] = folders[folder] + 1 if folder in folders else 1
        items = sorted([[key, value] for key, value in folders.items()], key=lambda x: x[0].lower(), reverse=False)
        message = [["%s (%d)" % (key, value)] for key, value in items]

        def on_done(i):
            if i < 0:
                self.infos += ["No folder selected"]
                self.log()
            else:
                self.choose_cites([cite for cite in cites if items[i][0] in cite.folders], import_all="Import all references within the folder %s." % items[i][0])
        if folders:
            sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done), 0)
        else:
            self.warnings += ["No folders available"]
            self.log()

    def choose_cites(self, posts, import_all=None):
        message = [["All listed references", import_all]] if import_all else []
        message += [post.string(panel_format=True) for post in sorted(posts, key=lambda x: x.key.lower())]

        def on_done(i):
            if i < 0:
                self.infos += ["No post selected"]
                self.log()
            else:
                if i == 0 and import_all:
                    self.import_cites(posts)
                else:
                    post = posts[i - 1 if import_all else i]
                    if self.left and self.right:
                        self.view.run_command("ltx_replace_region", {"region": (self.left, self.right), "string": post.key})
                    self.import_cites([post])

        sublime.set_timeout(lambda: self.view.window().show_quick_panel(message, on_done), 0)

    def import_cites(self, cites):
        for cite in cites:
            self.bib_file.add_cite(cite)
            self.infos += ["Imported %s to \"%s\"" % (cite.key, self.bib_file.file_name)]
        if not cites:
            self.errors += ["Noting to import, all items are already available offline."]
        self.log()
        self.bib_file.save()

    def log(self):
        # Write infos to log panel
        self.logPanel.log(self.infos)
        self.logPanel.log(self.errors)
        self.logPanel.log(self.warnings)

        self.logPanel.log("\n[Done]")

        if self.errors and "errors" in self.settings["show_log_panel_on"]:
            self.logPanel.show()

        if self.warnings and "warnings" in self.settings["show_log_panel_on"]:
            self.logPanel.show()

        if not self.errors and not self.warnings and "infos" not in self.settings["show_log_panel_on"]:
            self.logPanel.hide()

    def run(self, edit, **args):
        # Init empty arrays
        self.infos = []
        self.errors = []
        self.warnings = []

        self.left = args["left"] if "left" in args else None
        self.right = args["right"] if "right" in args else None

        self.settings = tools.load_settings("LaTeXing", show_log_panel_on=["errors", "warnings", "infos"], bibname="RemoteBibliography.bib", bibsonomy=False, citeulike=False, mendeley=False, zotero=False, global_bib_file=False, global_bib_file_path="")

        self.sources = []
        if self.settings["bibsonomy"]:
            self.sources += [{"id": "bibsonomy", "data": ["normal", "tag", "missing", ]}]
        if self.settings["citeulike"]:
            self.sources += [{"id": "citeulike", "data": ["normal", "tag", "missing", ]}]
        if self.settings["mendeley"]:
            self.sources += [{"id": "mendeley", "data": ["normal", "tag", "folder", "missing", ]}]
        if self.settings["zotero"]:
            self.sources += [{"id": "zotero", "data": ["normal", "tag", "folder", "missing", ]}]
        if self.settings["global_bib_file"] and self.settings["global_bib_file_path"] and self.settings["global_bib_file_path"] != self.view.file_name():
            self.sources += [{"id": "global_bib_file", "data": ["normal", "missing", ]}]

        if not self.sources:
            sublime.error_message("No source for importing citations available, please check your settings.")
            return

        self.logPanel = output.Panel(self.view.window(), show=False)

        def clean_mode(source, tag):
            if tag in source["data"]:
                source["data"].remove(tag)
            return source

        if self.view.match_selector(0, "text.bibtex"):
            self.bib_file = cache.BibFile(self.view.file_name())
            self.bib_file.run()

            self.keys = self.bib_file.cite_keys()
            self.sources = [clean_mode(source, "missing") for source in self.sources]
        else:
            tex_file = cache.TeXFile(self.view.file_name())
            tex_file.run()

            root_file = tex_file.root_file()
            root_file.run()

            tex_dir, tex_name, tex_name_root, tex_name_ext = tools.split_file_path(root_file.file_path)

            bib_name = self.settings["bibname"]
            bib_path = os.path.join(tex_dir, bib_name)

            self.keys = []
            for file_path in root_file.bibliography():
                if file_path != bib_path:
                    bib_file = cache.BibFile(file_path)
                    bib_file.run()
                    self.keys += bib_file.cite_keys()

            if not os.path.isfile(bib_path):
                if sublime.ok_cancel_dialog("%s do not exist. Would you like to create the file?" % self.settings["bibname"], "Create"):
                    with open(bib_path, 'w+', encoding="utf-8", errors="ignore"):
                        pass
                else:
                    return

            self.bib_file = cache.BibFile(bib_path, True)
            self.bib_file.run()

            self.keys += self.bib_file.cite_keys()
            self.missing_keys = []

            for file_path, item in root_file.get("cite"):
                for argument in item["arguments"]:
                    for key in argument.split(":", 1)[1].split(","):
                        key = key.strip()
                        self.missing_keys += [key] if key not in self.keys else []

        self.choose_source()
