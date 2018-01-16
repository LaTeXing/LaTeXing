import sublime
import sublime_plugin

import datetime
import os
import re
import stat
import threading

from . import LTX_TESTING
from . import LTX_TEMPDIR
from . import bib
from . import logger
from . import progress
from . import terminal
from . import tools
from .api import bibsonomy
from .api import citeulike
from .api import mendeley
from .api import zotero

log = logger.getLogger(__name__)


class LtxRebuildCacheCommand(sublime_plugin.WindowCommand):

    def run(self, soft=True):
        log.debug("%s", soft)

        if tools.LtxSettings().get("ltx_rebuild_cache", False):
            sublime.error_message("The cache is already rebuilding, please wait!")
            return

        if tools.LtxSettings().get("ltx_sync_data", False):
            sublime.error_message("The synchronisation is running, please wait!")
            return

        items = [key for key in CACHE_NAMES if key in CACHE.cache_data]

        if not items:
            return

        items = ["*.cache"] + items

        def on_done(i):
            if i < 0:
                return
            tools.LtxSettings().set("ltx_rebuild_cache", True)
            if i == 0:
                cache_items = items[1:]
            else:
                cache_items = [items[i]]

            for item in cache_items:
                CACHE.clear_cache(item, soft)

            # Clear the whole cache variable
            if i == 0 and not soft:
                CACHE.cache_data = {}

            message = ["Rebuilding Cache Information...", "Finished Caching"]
            progress.progress_function(lambda: cache(cache_items), message[0], message[1], lambda: tools.LtxSettings().set("ltx_rebuild_cache", False))

        sublime.set_timeout(lambda: self.window.show_quick_panel(items, on_done), 0)


class LtxSaveCacheCommand(sublime_plugin.ApplicationCommand):

    def run(self, skip_check=True, timeout=1000, mode=None):
        sublime.set_timeout_async(lambda: CACHE.save_cache(mode, skip_check), timeout)


class LtxShowCacheCommand(sublime_plugin.WindowCommand):

    def run(self):

        # Get items for list
        items = [key for key in CACHE.cache_data.keys()]

        def on_done(i):
            if i < 0:
                return
            key = items[i]
            value = CACHE.cache_data[key]
            view = self.window.new_file()
            view.set_name("temp::" + key)
            view.set_scratch(True)
            view.set_read_only(True)
            view.run_command("ltx_append_text", {"string": sublime.encode_value(value, True)})
            view.run_command("ltx_select_point", {"point": 0})

        sublime.set_timeout(lambda: self.window.show_quick_panel(items, on_done), 0)


class Cache(object):

    cache_data = {}
    timer = 0

    def read_cache(self, file_name):
        with open(os.path.join(sublime.cache_path(), "LaTeXing", file_name), 'r', encoding="utf-8") as f:
            log.trace("%s", f)
            str_json = f.read()
        log.info("%s (%s)" % (file_name, tools.size_of_string(str_json)))
        return str_json

    def get_cache(self, file_name):
        try:
            if file_name in self.cache_data:
                file_json = self.cache_data[file_name]
            else:
                file_json = sublime.decode_value(self.read_cache(file_name))
                if "data" not in file_json:
                    raise Exception
                self.cache_data[file_name] = file_json
        except Exception:
            file_json = {"rtime": "01.01.2000T00:00:00", "data": {}}
        return file_json

    def get_cache_data(self, file_name):
        file_json = self.get_cache(file_name)
        return file_json["data"]

    def save_cache(self, mode=None, skip_check=False):
        def save():
            for file_name in mode if mode else CACHE_NAMES:
                if file_name in self.cache_data:
                    str_json = sublime.encode_value(self.cache_data[file_name])
                    with open(os.path.join(sublime.cache_path(), "LaTeXing", file_name), 'w', encoding="utf-8") as f:
                        log.trace("%s", f)
                        f.write(str_json)
                    log.info("%s (%s)" % (file_name, tools.size_of_string(str_json)))
        if skip_check or LTX_TESTING:
            save()
        else:
            if not self.timer:
                self.timer = threading.Timer(300, save)
                self.timer.start()
            elif not self.timer.is_alive():
                self.timer = threading.Timer(300, save)
                self.timer.start()
            else:
                log.debug("Skipped Save")

    def set_cache(self, file_name, file_json, update_rtime=False):
        if update_rtime:
            file_json["rtime"] = datetime.datetime.today().strftime("%d.%m.%YT%H:%M:%S")
        self.cache_data[file_name] = file_json

    def set_cache_data(self, file_name, data, update_rtime=False):
        file_json = self.get_cache(file_name)
        file_json["data"] = data
        self.set_cache(file_name, file_json, update_rtime)

    def add_cache_data(self, file_name, data, update_rtime=False):
        file_json = self.get_cache(file_name)
        if isinstance(data, dict):
            file_json["data"].update(data)
        else:
            file_json["data"] += data
        self.set_cache(file_name, file_json, update_rtime)

    def clear_cache(self, file_name, soft):
        if soft and file_name in self.cache_data:
            file_json = self.get_cache(file_name)
            file_json["rtime"] = "01.01.2000T00:00:00"
            self.set_cache(file_name, file_json)
        else:
            file_path = os.path.join(sublime.cache_path(), "LaTeXing", file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
            if file_name in self.cache_data:
                self.cache_data.pop(file_name)
        log.info("%s (%s)" % (file_name, "soft" if soft else "hard"))

    def is_cache_outdated(self, file_name, t):
        file_json = self.get_cache(file_name)
        log.debug("%s %s" % (file_name, file_json["rtime"]))
        try:
            rtime = datetime.datetime.strptime(file_json["rtime"], "%d.%m.%YT%H:%M:%S")
            return (datetime.datetime.today() - rtime).total_seconds() > t * 3600
        except Exception:
            return True

CACHE = Cache()
CACHE_NAMES = ["doc.cache", "pkg.cache", "tex.cache", "bib.cache", "bibsonomy.cache", "citeulike.cache", "mendeley.cache", "zotero.cache"]


def cache(mode=["bin.cache"] + CACHE_NAMES):

    tools.LtxSettings().set("ltx_rebuild_cache", True)

    if "bin.cache" in mode:
        cache_bin()
    if "pkg.cache" in mode:
        cache_pkg()
    if "doc.cache" in mode:
        cache_doc()
    if "bibsonomy.cache" in mode:
        cache_bibsonomy()
    if "citeulike.cache" in mode:
        cache_citeulike()
    if "mendeley.cache" in mode:
        cache_mendeley()
    if "zotero.cache" in mode:
        cache_zotero()
    if "tex.cache" in mode:
        cache_tex()
    if "bib.cache" in mode:
        cache_bib()

    tools.LtxSettings().set("ltx_rebuild_cache", False)
    sublime.run_command("ltx_save_cache")


def cache_bin():
    dir_path = os.path.join(sublime.cache_path(), "LaTeXing", "bin")

    if os.path.isdir(dir_path):
        for item in os.listdir(dir_path):
            os.remove(os.path.join(dir_path, item))
    else:
        os.makedirs(dir_path)

    if sublime.platform() == "osx":
        items = ["activate_application", "preview"]
    elif sublime.platform() == "linux":
        items = ["evince", "evince_forward_sync", "evince_reverse_sync", "https_request"]
    else:
        items = []

    for item in items:
        content = sublime.load_binary_resource("Packages/LaTeXing/bin/%s" % item)
        with open(os.path.join(dir_path, item), 'wb') as f:
            f.write(content)
            os.chmod(f.name, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
            log.debug("bin/%s: up to date" % item)


def cache_doc():
    settings = tools.load_settings("LaTeXing", cache={"doc": 24})
    if not "doc" in settings["cache"] or not settings["cache"]["doc"]:
        return

    doc_data = CACHE.get_cache_data("doc.cache")
    pkg_data = CACHE.get_cache_data("pkg.cache")
    check_data = {}
    if CACHE.is_cache_outdated("doc.cache", settings["cache"]["doc"]):
        for key in doc_data.keys():
            if key in pkg_data:
                f = DocFile(key)
                f.run(cache=False, save=True)
                if len(f.data):
                    check_data[key] = f.data
        CACHE.set_cache_data("doc.cache", doc_data, True)
    else:
        log.debug("up to date")


def cache_pkg():
    settings = tools.load_settings("LaTeXing", cache={"pkg": 24})
    if not "pkg" in settings["cache"] or not settings["cache"]["pkg"]:
        return

    if CACHE.is_cache_outdated("pkg.cache", settings["cache"]["pkg"]):
        f = PkgFile()
        f.run(cache=False, save=True)
        data = f.data
        CACHE.set_cache_data("pkg.cache", data, True)
    else:
        log.debug("up to date")


def cache_bibsonomy():
    settings = tools.load_settings("LaTeXing", cache={"bibsonomy": 24}, bibsonomy=False)

    if not settings["bibsonomy"] or not "bibsonomy" in settings["cache"] or not settings["cache"]["bibsonomy"]:
        if os.path.exists(os.path.join(sublime.cache_path(), "LaTeXing", "bibsonomy.cache")):
            CACHE.clear_cache("bibsonomy.cache", False)
        return

    # Get BibsonomyFile
    f = BibsonomyFile()

    bibsonomy_data = CACHE.get_cache_data("bibsonomy.cache")
    if CACHE.is_cache_outdated("bibsonomy.cache", settings["cache"]["bibsonomy"]):
        f.run(cache=False, save=True)
        if f.status == "Error":
            log.error("error while caching")
            # CACHE.clear_cache("bibsonomy.cache", True)
        elif f.status == "Ok":
            bibsonomy_data = f.data
            CACHE.set_cache_data("bibsonomy.cache", bibsonomy_data, True)
    else:
        log.debug("up to date")

        # Rebuild Keys
        for item in bibsonomy_data["cites"]:
            item["cite_key"] = f.build_cite_key(item)

        # Set the new cache
        CACHE.set_cache_data("bibsonomy.cache", bibsonomy_data, True)


def cache_citeulike():
    settings = tools.load_settings("LaTeXing", cache={"citeulike": 24}, citeulike=False)

    if not settings["citeulike"] or not "citeulike" in settings["cache"] or not settings["cache"]["citeulike"]:
        if os.path.exists(os.path.join(sublime.cache_path(), "LaTeXing", "citeulike.cache")):
            CACHE.clear_cache("citeulike.cache", False)
        return

    # Get CiteulikeFile
    f = CiteulikeFile()

    citeulike_data = CACHE.get_cache_data("citeulike.cache")
    if CACHE.is_cache_outdated("citeulike.cache", settings["cache"]["citeulike"]):
        f.run(cache=False, save=True)
        if f.status == "Error":
            log.error("error while caching")
            # CACHE.clear_cache("citeulike.cache", True)
        elif f.status == "Ok":
            citeulike_data = f.data
            CACHE.set_cache_data("citeulike.cache", citeulike_data, True)
    else:
        log.debug("up to date")

        # Rebuild Keys
        for item in citeulike_data["cites"]:
            item["cite_key"] = f.build_cite_key(item)

        # Set the new cache
        CACHE.set_cache_data("citeulike.cache", citeulike_data, True)


def cache_mendeley():
    settings = tools.load_settings("LaTeXing", cache={"mendeley": 24}, mendeley=False)

    if not settings["mendeley"] or not "mendeley" in settings["cache"] or not settings["cache"]["mendeley"]:
        if os.path.exists(os.path.join(sublime.cache_path(), "LaTeXing", "mendeley.cache")):
            CACHE.clear_cache("mendeley.cache", False)
        return

    # Get MendeleyFile
    f = MendeleyFile()

    # Get Cache data an rebuild cahce if necessary
    mendeley_data = CACHE.get_cache_data("mendeley.cache")
    if CACHE.is_cache_outdated("mendeley.cache", settings["cache"]["mendeley"]):
        f = MendeleyFile()
        f.run(cache=False, save=True)
        if f.status == "Error":
            log.error("error while caching")
            # CACHE.clear_cache("mendeley.cache", True)
        elif f.status == "Ok":
            mendeley_data = f.data
            CACHE.set_cache_data("mendeley.cache", mendeley_data, True)
    else:
        log.debug("up to date")

        # Rebuild Keys
        for item in mendeley_data["cites"]:
            item["cite_key"] = f.build_cite_key(item)

        # Set the new cache
        CACHE.set_cache_data("mendeley.cache", mendeley_data, True)


def cache_zotero():
    settings = tools.load_settings("LaTeXing", cache={"zotero": 24}, zotero=False)

    if not settings["zotero"] or not "zotero" in settings["cache"] or not settings["cache"]["zotero"]:
        if os.path.exists(os.path.join(sublime.cache_path(), "LaTeXing", "zotero.cache")):
            CACHE.clear_cache("zotero.cache", False)
        return

    # Get ZoteroFile
    f = ZoteroFile()

    zotero_data = CACHE.get_cache_data("zotero.cache")
    if CACHE.is_cache_outdated("zotero.cache", settings["cache"]["zotero"]):
        f.run(cache=False, save=True)
        if f.status == "Error":
            log.error("error while caching")
            # CACHE.clear_cache("zotero.cache", True)
        elif f.status == "Ok":
            zotero_data = f.data
            CACHE.set_cache_data("zotero.cache", zotero_data, True)
    else:
        log.debug("rebuild cite_key")
        # Rebuild Keys
        for item in zotero_data["cites"]:
            item["cite_key"] = f.build_cite_key(item)

        # Set the new cache
        CACHE.set_cache_data("zotero.cache", zotero_data, True)


def cache_tex():
    settings = tools.load_settings("LaTeXing", cache={"tex": 24})
    if not "tex" in settings["cache"] or not settings["cache"]["tex"]:
        return

    tex_data = CACHE.get_cache_data("tex.cache")
    check_data = {}
    if CACHE.is_cache_outdated("tex.cache", settings["cache"]["tex"]):
        for file_path in tex_data.keys():
            if os.path.isfile(file_path):
                f = TeXFile(file_path)
                f.run(cache=False, save=True)
                check_data[file_path] = f.data
        tex_data = check_data
        CACHE.set_cache_data("tex.cache", tex_data, True)
    else:
        log.debug("tex cache: up to date")


def cache_bib():
    settings = tools.load_settings("LaTeXing", cache={"bib": 24})
    if not "bib" in settings["cache"] or not settings["cache"]["bib"]:
        return

    bib_data = CACHE.get_cache_data("bib.cache")
    check_data = {}
    if CACHE.is_cache_outdated("bib.cache", settings["cache"]["bib"]):
        for file_path in bib_data.keys():
            if os.path.isfile(file_path):
                f = BibFile(file_path)
                f.run(cache=False, save=True)
                check_data[file_path] = f.data
        bib_data = check_data
        CACHE.set_cache_data("bib.cache", bib_data, True)
    else:
        log.debug("bib cache: up to date")


class PkgFile():

    def __init__(self):
        self.data = []
        self.settings = tools.load_settings("LaTeXing", cache={"pkg": 24})

    def run(self, cache=True, save=False):

        cache_timeout = self.settings["cache"]["pkg"] if "pkg" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("pkg.cache")
        else:
            cached_data = {}

        if cached_data and not CACHE.is_cache_outdated("pkg.cache", cache_timeout):
            self.data = cached_data
        else:
            self.data = []

            c = terminal.KpsewhichCmd()
            c.run()
            self.data = c.items
            if cache and cache_timeout:
                CACHE.set_cache_data("pkg.cache", self.data, True)


class DocFile():

    def __init__(self, key):
        self.key = key
        self.data = {}
        self.resources = tools.load_resource("LaTeX.sublime-build", windows={"path": ""})
        self.settings = tools.load_settings("LaTeXing", cache={"doc": 24})

    def run(self, cache=True, save=False):

        cache_timeout = self.settings["cache"]["doc"] if "doc" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache("doc.cache")
        else:
            cached_data = {}

        if cached_data and (self.key in cached_data["data"]) and not CACHE.is_cache_outdated("doc.cache", cache_timeout):
            self.data = cached_data["data"][self.key]
        else:
            self.data = []

            if sublime.platform() == "windows":
                miktex = "miktex" in self.resources["windows"]["path"].lower()
            else:
                miktex = None

            if miktex:
                c = terminal.MthelpCmd(self.key)
            else:
                c = terminal.TexdocCmd(self.key)
            c.run()

            if len(c.items) and not c.error:
                self.data = c.items

                if cache and cache_timeout:
                    CACHE.add_cache_data("doc.cache", {self.key: self.data}, update_rtime=True)


class CacheFile(object):

    def __init__(self):
        self.data = {}
        self.error = False
        self.status = None

    def get(self, key):
        return [[self.file_path if hasattr(self, "file_path") else "None", d] for d in self.data[key]] if key in self.data else []

    def save(self):
        self.run(save=True)


class TeXFile(CacheFile):

    def __init__(self, file_path):
        self.file_path = os.path.normpath(file_path)
        self.file_dir, self.file_name, self.file_name_root, self.file_name_ext = tools.split_file_path(self.file_path)

        self.settings = tools.load_settings("LaTeXing", default_bib_extension=".bib", default_tex_extension=".tex", cache={"tex": 24}, output_directory=True, output_directory_mode=0, phrase_analyses=1, phrase_minimum_count=2, phrase_minimum_length=3, phrase_maximum_length=5, phrase_bounding_words=[])
        CacheFile.__init__(self)

    def run(self, cache=True, save=False):

        if not os.path.isfile(self.file_path):
            self.error = True
            return

        cache_timeout = self.settings["cache"]["tex"] if "tex" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("tex.cache")
        else:
            cached_data = {}

        if self.file_path in cached_data:
            self.data = cached_data[self.file_path]
        else:
            self.data = {}
            file_lines, option_lines = tools.read_file_lines(self.file_path)

            self.data["options"] = tools.tex_options(option_lines)
            name, option = tools.document_class(file_lines)
            if name:
                self.data["documentclass"] = {"name": name}
                if option:
                    self.data["documentclass"]["option"] = option

            data = {}
            data["ac"] = tools.find_command_arguments(file_lines, r"(new)?acro(def)?(indefinite|plural)?")
            data["bibitem"] = tools.find_command_arguments(file_lines, r"bibitem")
            data["bibliography"] = tools.find_command_arguments(file_lines, r"(bibliography|addbibresource|addglobalbib|addsectionbib)")
            data["cite"] = tools.find_command_arguments(file_lines, r"(no)?cite\w*", single=True)
            data["input"] = tools.find_command_arguments(file_lines, r"(input|include|subfile)\**", single=True)
            data["label"] = tools.find_command_arguments(file_lines, r"(line)?label", single=False)
            data["newcommand"] = tools.find_command_arguments(file_lines, r"(re)?newcommand")
            data["newenvironment"] = tools.find_command_arguments(file_lines, r"(re)?newenvironment")
            data["packages"] = tools.use_packages(file_lines)
            data["ref"] = tools.find_command_arguments(file_lines, r"\w*ref", single=True)

            if self.settings["phrase_analyses"] > 0:
                data["words"] = tools.list_words(file_lines)

            for key, value in data.items():
                if value:
                    self.data[key] = value

            if cache and cache_timeout:
                CACHE.add_cache_data("tex.cache", {self.file_path: self.data})

    def get(self, key, root=True, walk=True):
        data = []
        if not walk:
            data = [[self.file_path, d] for d in self.data[key]] if key in self.data else []
        else:
            if root:
                root_file = self.root_file()
                root_file.run()
            else:
                root_file = self
            # Save data for the current file
            data += [[root_file.file_path, d] for d in root_file.data[key]] if key in root_file.data else []
            # Search through the subfiles
            for item in root_file.data["input"] if "input" in root_file.data else []:
                # Check extention and build right file path
                file_name = item["arguments"][0].split(":", 1)[1]
                if not os.path.splitext(file_name)[1]:
                    file_name = tools.add_extension(file_name, self.settings["default_tex_extension"])
                file_path = os.path.normpath(os.path.join(os.path.dirname(root_file.root_file_path()), file_name))
                # Parse subfiles
                f = TeXFile(file_path)
                f.run()
                data += f.get(key, root=False, walk=True)
        return data

    def read_file_content(self, **args):
        return tools.read_file_content(self.file_path, **args)

    def get_option(self, key, fallback=None, root=True):
        options = self.data["options"] if "options" in self.data else {}

        # key == root return current root_file path
        if key == "root":
            return self.root_file_path()
        elif key in options:
            return tools.load_project_setting(key, options[key])
        elif root and self.root_file_path() != self.file_path:
            f = self.root_file()
            f.run()
            return f.get_option(key, fallback)
        return tools.load_project_setting(key, fallback)

    def get_source(self, rex):
        file_content = tools.read_file_content(self.file_path)
        return re.search(rex, file_content)

    def pdf_file_name(self):
        pdf_name_root = self.get_option("pdf", self.file_name_root)
        pdf_name_root = pdf_name_root.replace(" ", "_")

        pdf_name = tools.add_extension(pdf_name_root, ".pdf")
        return pdf_name

    def pdf_file_path(self):
        return os.path.join(self.file_dir, self.pdf_file_name())

    def output_directory(self, sub_directory=None):
        # Parse root file
        root_file = self.root_file()
        root_file.run()

        # If no output directory return root file dir
        if not self.settings["output_directory"]:
            return root_file.file_dir

        # Get pdf_name_root for the jobname
        pdf_name = root_file.pdf_file_name()
        pdf_name_root, pdf_name_ext = os.path.splitext(pdf_name)

        # Get temp dir and create outout directory
        if self.settings["output_directory_mode"] == 0:
            dir_path = os.path.join(root_file.file_dir, "Output")
        else:
            dir_path = os.path.join(LTX_TEMPDIR, pdf_name_root)

        # Add sub directory if available
        if sub_directory:
            dir_path = os.path.join(dir_path, sub_directory)

        # Try to create the output directory
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            return dir_path
        except:
            pass

        # Return root dir as fallback
        return root_file.file_dir

    def root_file_path(self):
        options = self.data["options"] if "options" in self.data else {}
        if "root" in options:
            file_dir = os.path.split(self.file_path)[0]
            file_name = self.data["options"]["root"]
            if not os.path.splitext(file_name)[1]:
                file_name = tools.add_extension(file_name, self.settings["default_tex_extension"])
            file_path = os.path.normpath(os.path.join(file_dir, file_name))
            if os.path.isfile(file_path):
                return tools.load_project_setting("root", file_path)
        name, option = self.documentclass(root=False)
        if name == "subfiles" and option:
            file_dir = os.path.split(self.file_path)[0]
            file_path = os.path.normpath(os.path.join(file_dir, option))
            if os.path.isfile(file_path):
                return tools.load_project_setting("root", file_path)
        return tools.load_project_setting("root", self.file_path)

    def root_file(self):
        return TeXFile(self.root_file_path())

    def bibliography(self, base_dir=None):
        data = []
        dir_path = base_dir if base_dir else os.path.dirname(self.root_file_path())
        for file_path, item in self.get("bibliography"):
            arguments = [argument for argument in item["arguments"] if argument.split(":", 1)[0] == "{"]
            if arguments:
                for file_name in arguments[0].split(":", 1)[1].split(","):
                    if not os.path.splitext(file_name)[1]:
                        file_name = tools.add_extension(file_name, self.settings["default_bib_extension"])
                    file_path = os.path.join(dir_path, file_name)
                    if file_path not in data:
                        f = BibFile(file_path)
                        f.run()
                        data += [file_path]
        return data

    def documentclass(self, root=True):
        if root:
            root_file = self.root_file()
            root_file.run()
        else:
            root_file = self
        if "documentclass" in root_file.data:
            return root_file.data["documentclass"]["name"] if "name" in root_file.data["documentclass"] else "", root_file.data["documentclass"]["option"] if "option" in root_file.data["documentclass"] else ""
        return "", ""

    def files(self, root=True):
        data = []
        if root:
            root_file = self.root_file()
            root_file.run()
        else:
            root_file = self

        # Save data for the current file
        data += [root_file.file_path]
        # Search through the subfiles
        for item in root_file.data["input"] if "input" in root_file.data else []:
            # Check extention and build right file path
            file_name = item["arguments"][0].split(":", 1)[1]
            if not os.path.splitext(file_name)[1]:
                file_name = tools.add_extension(file_name, self.settings["default_tex_extension"])
            file_path = os.path.normpath(os.path.join(os.path.dirname(root_file.root_file_path()), file_name))
            # Parse subfiles
            f = TeXFile(file_path)
            f.run()
            data += f.files(root=False)
        return data

    def words(self, walk=True):
        data = {}
        for file_path, item in self.get("words", walk=walk):
            parts = item.split(":", 1)
            count = int(parts[0])
            key = parts[1]
            data[key] = count if key not in data else data[key] + count
        return [[self.file_path, (value, key)] for key, value in sorted(data.items(), key=lambda x:x[1], reverse=True)]


class BibFile(CacheFile):

    def __init__(self, file_path, create_on=False):
        if file_path[0] == '~':
            file_path = file_path.replace('~', os.path.expanduser('~'))

        self.file_path = os.path.normpath(file_path)
        self.file_name = os.path.basename(file_path)
        self.create_on = create_on

        self.settings = tools.load_settings("LaTeXing", cache={"bib": 24})

        CacheFile.__init__(self)

    def run(self, cache=True, save=False):

        # Debug
        log.debug(self.file_path)

        if not os.path.isfile(self.file_path) and not self.create_on:
            self.error = True
            return

        cache_timeout = self.settings["cache"]["bib"] if "bib" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("bib.cache")
        else:
            cached_data = {}

        if self.file_path in cached_data:
            self.data = cached_data[self.file_path]
        else:
            file_lines = tools.read_file_lines(self.file_path, commentChar=False, lines=False)[0]

            self.data = {}
            try:
                self.data["cites"] = self.find_cites(file_lines)
            except Exception as e:
                log.error("%s" % e)
                self.data["cites"] = []

            if cache and cache_timeout:
                CACHE.add_cache_data("bib.cache", {self.file_path: self.data})

    def cites(self):
        cites = []
        for file_path, item in self.get("cites"):
            cites += [[file_path, bib.BibItem(item["key"], self.file_name, item["type"], item["fields"])]]
        return cites

    def cite(self, key):
        for file_path, item in self.get("cites"):
            if item["key"] == key:
                return bib.BibItem(item["key"], self.file_name, item["type"], item["fields"])
        return None

    def cite_source(self, key):
        if not hasattr(self, "file_content") or not self.file_content:
            self.file_content = tools.read_file_content(self.file_path)

        # Search for a valid key
        expr = re.search(r"@\b\w+\b{%s\b" % re.escape(key), self.file_content)
        if not expr:
            return None

        # Find start line with right key
        start = expr.start()
        end = tools.end_of_argument(self.file_content, start, r"\{", r"\}")
        return re.sub(r"[\t\n\s]*", "", self.file_content[start:end]) if isinstance(end, int) else None

    def cite_keys(self):
        return [item["key"] for file_path, item in self.get("cites")]

    def has_cite(self, key):
        for file_path, item in self.get("cites"):
            if item["key"] == key:
                return True
        return False

    def find_cites(self, file_lines):

        rexType = re.compile(r"(?P<type>[\w]+)\s*\{\s*(?P<key>.+)\s*,")
        # rexFields = re.compile(r"\b(?P<field>%s)\b\s*=\s*(?P<start>\{+|\"|\b)(?P<content>.+?)(?P<end>\}+|\"|\b)[\s,]*\Z" % "|".join(bib.FIELDS), re.IGNORECASE)
        rexFields = re.compile(r"\b(?P<field>\w+)\b\s*=\s*(?P<start>\{|\"|\b)(?P<content>.+?)(?P<end>\}|\"|\b)[\s,]*\Z", re.IGNORECASE)

        # copy of end_of_argument from tools.py, just for speed it up for huge bib files
        rexPair1 = re.compile(r"^[\{\}]|(?<=[^\\])[\{\}]")

        def end_of_argument(line, offset, balance=0):
            index = -1
            for braket in rexPair1.finditer(line, offset):
                index = braket.start()
                balance += 1 if braket.group() == "{" else -1

                # Break of balance was even or less (probably a bib file misstake)
                if balance <= 0:
                    break

            if index < 0 and balance == 0:
                return "NoMatch"
            elif balance > 0:
                return "Unclosed:%d" % balance
            return index

        # copy of end_of_argument_same_pattern from tools.py, just for speed it up for huge bib files
        rexPair2 = re.compile(r"(?<=%s)(?P<char>%s)" % (r"[^\\]", r"\""))

        def end_of_argument_same_pattern(string, offset):
            expr = rexPair2.search(string, offset)
            return expr.end('char') if expr else "Unclosed:1"

        items = []
        cite_type, cite_key, fields, open_expr = None, None, {}, None
        for line in file_lines:
            if line.lower()[0:8] == "@comment" or line.lower()[0:7] == "@string":
                continue
            if line[0] == "@":
                if cite_type:
                    items += [{"key": cite_key, "type": cite_type, "fields": fields}]
                try:
                    expr = rexType.search(line)
                    cite_type = expr.group('type').title()
                    cite_key = expr.group('key')
                    fields = {}
                except:
                    cite_type, cite_key, fields = None, None, {}

            elif open_expr:
                expr = open_expr["expr"]

                # Find items with {}
                if expr.group("start") == "{":
                    end = end_of_argument(line, 0, open_expr["balance"])
                # Find items with ""
                elif expr.group("start") == "\"":
                    end = end_of_argument_same_pattern(line, 0)

                # Save if end is int
                if isinstance(end, int):
                    fields[expr.group("field").lower()] = open_expr["line"] + line[:end]
                    open_expr = None
                elif end[0:8] == "Unclosed":
                    open_expr = {"expr": expr, "line": open_expr["line"] + line, "balance": int(end[9:])}

            elif cite_type:
                expr = rexFields.search(line)
                if expr:
                    start = expr.start("content")

                    # Find items with {}
                    if expr.group("start") and expr.group("start")[0] == "{":
                        if expr.group("end") and expr.group("end")[0] == "}":
                            end = expr.end("content")
                        else:
                            end = end_of_argument(line, start, 1)

                    # Find items with ""
                    elif expr.group("start") and expr.group("start")[0] == "\"":
                        if expr.group("end") and expr.group("end")[0] == "\"":
                            end = expr.end("content")
                        else:
                            end = end_of_argument_same_pattern(line, start)

                    # Find items starting with digit
                    elif expr.group("content").isdigit():
                        end = expr.end("content")

                    # Save if end is int
                    if isinstance(end, int):
                        fields[expr.group("field").lower()] = line[start:end]
                    elif end[0:8] == "Unclosed":
                        open_expr = {"expr": expr, "line": line[start:], "balance": int(end[9:])}

        if cite_type and not open_expr:
            items += [{"key": cite_key, "type": cite_type, "fields": fields}]

        return items

    def add_cite(self, new_cite):
        cites = [new_cite]
        if self.has_cite(new_cite.key):
            cites += [cite for file_path, cite in self.cites() if cite.key != new_cite.key]
            self.add_cites(cites)
        else:
            self.add_cites(cites, clear=False)

    def add_cites(self, cites, clear=True):
        if clear:
            with open(self.file_path, 'r+') as f:
                f.truncate()

        for cite in cites:
            with open(self.file_path, 'a+', encoding="utf-8", errors="ignore") as f:
                f.write(cite.string() if f.tell() else cite.string().lstrip())

    # Update cites, input array of bib items
    def update_cites(self, new_cites):
        new_cites = {cite.key: cite for cite in new_cites}

        cites = []
        for file_path, cite in self.cites():

            # Avoid double entries in remote bib
            if cite.key not in [cite["key"] for cite in cites]:
                cites += [{"key": cite.key, "cite": new_cites[cite.key]}] if cite.key in new_cites else [{"key": cite.key, "cite": cite}]

        self.add_cites([cite["cite"] for cite in cites])


class BibliographyFile(CacheFile):

    def __init__(self):
        self.cite_key_pattern = "{Author}{Year}"
        CacheFile.__init__(self)

    def build_cite_key(self, item):
        try:
            # Get author if required
            a = item["fields"]["author"] if "author" in item["fields"] else item["fields"]["editor"]
            if re.search(r"\{([^\}]+)\}", a):
                author = tools.tidy_accents(re.search(r"\{([^\}]+)\}", a).group(1))
            else:
                author = tools.tidy_accents(re.search(r"([\w\{\}]+)((\sand\s)|$|,)", a).group(1))

            # Get title, skip the word in cite_key_blacklist list
            title_words = [word for word in item["fields"]["title"].split(" ") if word.lower() not in self.settings["cite_key_blacklist"]] if "title" in item["fields"] else []

            # Build title
            title = tools.tidy_accents(title_words[0] if title_words else "None") if "title" in item["fields"] else "None"

            # Get year
            year = item["fields"]["year"] if "year" in item["fields"] and item["fields"]["year"] else "????"
            return tools.validate_citekey(self.cite_key_pattern.format(
                author=author,
                Author=author.title(),
                year=year,
                Year=year,
                title=title,
                Title=title.title()).replace(" ", ""))
        except Exception as e:
            log.debug("no %s", e)
            return None


class BibsonomyFile(BibliographyFile):

    def __init__(self):
        self.file_path = "Bibsonomy.org"
        self.settings = tools.load_settings("LaTeXing", cache={"bibsonomy": 24}, cite_key_blacklist=[], bibsonomy_internal_cite_key=False, bibsonomy_cite_key_pattern="{Author}{year}")
        BibliographyFile.__init__(self)

        # Set cite key pattern
        self.cite_key_pattern = self.settings["bibsonomy_cite_key_pattern"]

    def run(self, cache=True, save=False, synchronise=False, fill_source=False):

        cache_timeout = self.settings["cache"]["bibsonomy"] if "bibsonomy" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("bibsonomy.cache")
        else:
            cached_data = {}

        if cached_data and not synchronise and not CACHE.is_cache_outdated("bibsonomy.cache", cache_timeout):
            self.data = cached_data
        else:
            if fill_source:
                if not cache_timeout:
                    sublime.error_message("Bibsonomy.cache disabled! Please activate the cache to use this function.")
                elif not tools.LtxSettings().get("ltx_offline", False) and sublime.ok_cancel_dialog("Bibsonomy.cache outdated, would you like to synchronise the data now? The items are available for the next call!", "Synchronise"):
                    sublime.run_command("ltx_sync_data", {"mode": "bibsonomy"})
                else:
                    self.data = cached_data
            else:
                c = bibsonomy.Bibsonomy()
                c.run()

                self.status = c.status
                if self.status in ["Error", "Waiting"]:
                    return

                if self.status == "Ok":
                    # Build cite keys
                    for item in c.items:
                        item["cite_key"] = self.build_cite_key(item)

                    # Save items
                    self.data["cites"] = c.items
                    if cache and cache_timeout:
                        CACHE.set_cache_data("bibsonomy.cache", self.data, True)

    def get_cites(self):
        cites = []
        library_keys = []

        # Get all cites and build a list
        for file_path, item in self.get("cites"):
            # Build citation key
            cite_key = item["key"] if self.settings["bibsonomy_internal_cite_key"] else item["cite_key"]

            if cite_key:
                # Check for double keys
                key = cite_key
                if cite_key in library_keys:
                    cite_key += chr(96 + library_keys.count(cite_key))
                cites += [[file_path, bib.BibItem(cite_key, file_path, item["type"], item["fields"])]]

                # Add key to library key, to support keys like Name2011a
                library_keys += [key]
            else:
                log.info("Skip %s", item)
        return cites


class CiteulikeFile(BibliographyFile):

    def __init__(self):
        self.file_path = "Citeulike.org"
        self.settings = tools.load_settings("LaTeXing", cache={"citeulike": 24}, cite_key_blacklist=[], citeulike_internal_cite_key=False, citeulike_cite_key_pattern="{Author}{year}")
        BibliographyFile.__init__(self)

        # Set cite key pattern
        self.cite_key_pattern = self.settings["citeulike_cite_key_pattern"]

    def run(self, cache=True, save=False, synchronise=False, fill_source=False):

        cache_timeout = self.settings["cache"]["citeulike"] if "citeulike" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("citeulike.cache")
        else:
            cached_data = {}

        if cached_data and not synchronise and not CACHE.is_cache_outdated("citeulike.cache", cache_timeout):
            self.data = cached_data
        else:
            if fill_source:
                if not cache_timeout:
                    sublime.error_message("Citeulike.cache disabled! Please activate the cache to use this function.")
                elif not tools.LtxSettings().get("ltx_offline", False) and sublime.ok_cancel_dialog("Citeulike.cache outdated, would you like to synchronise the data now? The items are available for the next call!", "Synchronise"):
                    sublime.run_command("ltx_sync_data", {"mode": "citeulike"})
                else:
                    self.data = cached_data
            else:
                c = citeulike.Citeulike()
                c.run()

                self.status = c.status
                if self.status in ["Error", "Waiting"]:
                    return

                if self.status == "Ok":
                    # Build cite keys
                    for item in c.items:
                        item["cite_key"] = self.build_cite_key(item)

                    # Save items
                    self.data["cites"] = c.items
                    if cache and cache_timeout:
                        CACHE.set_cache_data("citeulike.cache", self.data, True)

    def get_cites(self):
        cites = []
        library_keys = []

        # Get all cites and build a list
        for file_path, item in self.get("cites"):
            # Build citation key
            cite_key = item["key"] if self.settings["citeulike_internal_cite_key"] else item["cite_key"]

            if cite_key:
                # Check for double keys
                key = cite_key
                if cite_key in library_keys:
                    cite_key += chr(96 + library_keys.count(cite_key))
                cites += [[file_path, bib.BibItem(cite_key, file_path, item["type"], item["fields"])]]

                # Add key to library key, to support keys like Name2011a
                library_keys += [key]
            else:
                log.info("Skip %s", item)
        return cites


class GlobalBibFile(BibFile):

    def __init__(self, file_path):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)

        self.settings = tools.load_settings("LaTeXing", default_bib_extension=".bib", cache={"global_bib": 24})

        CacheFile.__init__(self)

    def run(self, cache=True, save=False):

        # Debug
        log.debug(self.file_path)

        # skip if file missing
        if not os.path.isfile(self.file_path):
            return

        cache_timeout = self.settings["cache"]["global_bib"] if "global_bib" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("bib.cache")
        else:
            cached_data = {}

        if self.file_path in cached_data:
            self.data = cached_data[self.file_path]
        else:
            file_lines = tools.read_file_lines(self.file_path, commentChar=False, lines=False)[0]

            self.data = {}
            try:
                self.data["cites"] = self.find_cites(file_lines)
            except Exception as e:
                log.error("%s" % e)
                self.data["cites"] = []

            if cache and cache_timeout:
                CACHE.add_cache_data("bib.cache", {self.file_path: self.data})


class MendeleyFile(BibliographyFile):

    def __init__(self):
        self.file_path = "Mendeley.com"
        self.settings = tools.load_settings("LaTeXing", cache={"mendeley": 24}, cite_key_blacklist=[], mendeley_internal_cite_key=False, mendeley_cite_key_pattern="{Author}{year}")
        BibliographyFile.__init__(self)

        # Set cite key pattern
        self.cite_key_pattern = self.settings["mendeley_cite_key_pattern"]

    def run(self, cache=True, save=False, synchronise=False, fill_source=False):

        cache_timeout = self.settings["cache"]["mendeley"] if "mendeley" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("mendeley.cache")
        else:
            cached_data = {}

        if cached_data and not synchronise and not CACHE.is_cache_outdated("mendeley.cache", cache_timeout):
            self.data = cached_data
        else:
            if fill_source:
                if not cache_timeout:
                    sublime.error_message("Mendeley.cache disabled! Please activate the cache to use this function.")
                elif not tools.LtxSettings().get("ltx_offline", False) and sublime.ok_cancel_dialog("Mendeley.cache outdated, would you like to synchronise the data now? The items are available for the next call!", "Synchronise"):
                    sublime.run_command("ltx_sync_data", {"mode": "mendeley"})
                else:
                    self.data = cached_data
            else:
                c = mendeley.Mendeley()
                c.run({item["id"]: item for item in cached_data["cites"]} if "cites" in cached_data and synchronise else {}, cached_data["cites_no_key"] if "cites_no_key" in cached_data and synchronise else {})

                self.status = c.status
                if self.status in ["Error", "Waiting"]:
                    return

                if self.status == "Ok":
                    # Build cite keys
                    for item in c.items:
                        item["cite_key"] = self.build_cite_key(item)

                    # Save items
                    self.data["cites"] = c.items
                    self.data["cites_no_key"] = c.items_no_key
                    if cache and cache_timeout:
                        CACHE.set_cache_data("mendeley.cache", self.data, True)

    def get_cites(self):
        cites = []
        library_keys = []

        # Get all cites and build a list
        for file_path, item in self.get("cites"):
            # Build citation key
            cite_key = item["key"] if self.settings["mendeley_internal_cite_key"] else item["cite_key"]

            if cite_key:
                # Check for double keys
                key = cite_key
                if cite_key in library_keys:
                    cite_key += chr(96 + library_keys.count(cite_key))
                cites += [[file_path, bib.BibItem(cite_key, file_path, item["type"], item["fields"], item["tags"], item["folders"])]]

                # Add key to library key, to support keys like Name2011a
                library_keys += [key]
            else:
                log.info("Skip %s", item)
        return cites

    def get_cite(self, document_id=None, document_key=None):
        for file_path, item in self.get("cites"):
            if item["id"] == document_id:
                return item
            if item["key"] == document_key:
                return item


class ZoteroFile(BibliographyFile):

    def __init__(self):
        self.file_path = "Zotero.org"
        self.settings = tools.load_settings("LaTeXing", cache={"zotero": 24}, cite_key_blacklist=[], zotero_internal_cite_key=False, zotero_cite_key_pattern="{Author}{year}")
        BibliographyFile.__init__(self)

        # Set cite key pattern
        self.cite_key_pattern = self.settings["zotero_cite_key_pattern"]

    def run(self, cache=True, save=False, synchronise=False, fill_source=False):

        cache_timeout = self.settings["cache"]["zotero"] if "zotero" in self.settings["cache"] else 0
        if cache_timeout and not save:
            cached_data = CACHE.get_cache_data("zotero.cache")
        else:
            cached_data = {}

        if cached_data and not synchronise and not CACHE.is_cache_outdated("zotero.cache", cache_timeout):
            self.data = cached_data
        else:
            if fill_source:
                if not cache_timeout:
                    sublime.error_message("Zotero.cache disabled! Please activate the cache to use this function.")
                elif not tools.LtxSettings().get("ltx_offline", False) and sublime.ok_cancel_dialog("Zotero.cache outdated, would you like to synchronise the data now? The items are available for the next call!", "Synchronise"):
                    sublime.run_command("ltx_sync_data", {"mode": "zotero"})
                else:
                    self.data = cached_data
            else:
                c = zotero.Zotero()
                c.run({item["id"]: item for item in cached_data["cites"]} if "cites" in cached_data and synchronise else {}, cached_data["cites_no_key"] if "cites_no_key" in cached_data and synchronise else {})

                self.status = c.status
                if self.status in ["Error", "Waiting"]:
                    return

                if self.status == "Ok":
                    # Build cite keys
                    for item in c.items:
                        item["cite_key"] = self.build_cite_key(item)

                    # Save items
                    self.data["cites"] = c.items
                    self.data["cites_no_key"] = c.items_no_key
                    if cache and cache_timeout:
                        CACHE.set_cache_data("zotero.cache", self.data, True)

    def get_cites(self):
        cites = []
        library_keys = []

        # Get all cites and build a list
        for file_path, item in self.get("cites"):
            # Build citation key
            cite_key = item["key"] if self.settings["zotero_internal_cite_key"] else item["cite_key"]

            if cite_key:
                # Check for double keys
                key = cite_key
                if cite_key in library_keys:
                    cite_key += chr(96 + library_keys.count(cite_key))
                cites += [[file_path, bib.BibItem(cite_key, file_path, item["type"], item["fields"], item["tags"], item["folders"])]]

                # Add key to library key, to support keys like Name2011a
                library_keys += [key]
            else:
                log.info("Skip %s", item)
        return cites

    def get_cite(self, document_id=None, document_key=None):
        for file_path, item in self.get("cites"):
            if item["id"] == document_id:
                return item
            if item["key"] == document_key:
                return item
