import sublime
import sublime_plugin

import os
import re

from . import cache
from . import cite
from . import commands
from . import logger
from . import tools

log = logger.getLogger(__name__)


class LtxFillAnywhereCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit):
        items = ["includegraphics", "input,include,subfile", "ref", "cite", "ac"]
        message = ["Fill %s anywhere" % item for item in items]

        def on_done(i):
            if i >= 0:
                self.view.run_command("ltx_fill", {"fill_anywhere": items[i].split(",")[0]})

        self.view.window().show_quick_panel(message, on_done)


class LtxFillCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex")

    def run(self, edit, **args):
        # Save current view
        view = self.view

        # Check if dirty and save prior using it
        if view.is_dirty():
            view.settings().set("save_is_dirty", True)
            view.run_command('save')

        # Load Settings
        settings = tools.load_settings("LaTeXing", auto_trigger_fill=True, bibname="Remote.bib", citeulike=False, bibsonomy=False, mendeley=False, zotero=False, global_bib_file=False, global_bib_file_path="", currfile_graphicspath=False, default_bib_extension=".bib", graphics_pattern=["*.jpg", "*.jpeg", "*.png", "*.eps", "*.pdf"], label_format="{type}:{prefix}:{name}", label_type={"table": "tbl", "figure": "fig", "part": "prt", "chapter": "cha", "section": "sec", "subsection": "ssec", "subsubsection": "sssec", "paragraph": "par", "subparagraph": "spar"}, output_directory=["Output"], remote_bibliography_in_category=False, tex_pattern=["*.tex", "*.ltx"])

        # Check if not auto_trigger_fill enabled if auto_trigger_source in args
        if not settings["auto_trigger_fill"] and "auto_trigger_source" in args:
            return

        point = view.sel()[0].a if view.sel()[0].a < view.sel()[0].b else view.sel()[0].b
        dicCommandRange = tools.find_command_range(view, int(point))
        if isinstance(dicCommandRange, str):
            dicCommand = {"name": None}
            argument = None
        else:
            dicCommand = tools.split_command(view.substr(sublime.Region(dicCommandRange["start"], dicCommandRange["end"])), dicCommandRange["start"])
            dicArgument = tools.find_current_argument(dicCommand["arguments"], dicCommandRange["point"])
            argument = dicArgument["argument"]

            log.debug("dicCommandRange: %s" % dicCommandRange)
            log.debug("dicCommand: %s" % dicCommand)
            log.debug("dicArgument: %s" % dicArgument)

        tex_pattern = settings["tex_pattern"]
        bibliography_pattern = ["*%s" % settings["default_bib_extension"]]
        graphics_patterns = settings["graphics_pattern"]

        rexAc = re.compile(r"\b[Ii]?ac[uplsf]?[suip]?(de)?\*?\b", re.IGNORECASE)
        rexBibliography = re.compile(r"\b(bibliography|addbibresource|addglobalbib|addsectionbib)\b", re.IGNORECASE)
        rexCaption = re.compile(r"\b\w*caption\b", re.IGNORECASE)
        rexChapter = re.compile(r"\b(part|chapter|(sub)?(sub)?section)|(sub)?paragraph\*?\b", re.IGNORECASE)
        rexCite = re.compile(r"\b\w*(cite|bibentry)\w*\*?\b", re.IGNORECASE)
        rexIncludegraphics = re.compile(r"\bincludegraphics.*\b", re.IGNORECASE)
        rexInput = re.compile(r"\b(input|include|subfile)\b", re.IGNORECASE)
        rexLabel = re.compile(r"\b(line)?label\b", re.IGNORECASE)
        rexRef = re.compile(r"\b\w*ref\b", re.IGNORECASE)
        rexUsepackage = re.compile(r"\b(bibliographystyle|documentclass|usepackage)\b", re.IGNORECASE)

        # to make sure nothing import will be replaced
        left = point
        right = point

        # For later use
        file_path = view.file_name()
        file_dir, file_name = os.path.split(file_path)

        tex_file = cache.TeXFile(file_path)
        tex_file.run()

        tex_path = tex_file.get_option("root")
        tex_dir, tex_name, tex_name_root, tex_name_ext = tools.split_file_path(tex_path)

        pdf_name_root = tex_file.get_option("pdf", tex_name_root)
        pdf_name_root = tools.remove_extension(pdf_name_root.replace(" ", "_"), ".pdf")

        output_dir = settings["output_directory"]

        log.info("file_path: %s" % file_path)
        log.info("file_dir: %s" % file_dir)
        log.info("file_name: %s" % file_name)
        log.info("tex_path: %s" % tex_path)
        log.info("tex_dir: %s" % tex_path)
        log.info("tex_name_root: %s" % tex_name_root)
        log.info("tex_name_ext: %s" % tex_name_ext)
        log.info("pdf_name_root: %s" % pdf_name_root)
        log.info("output_dir: %s" % output_dir)

        message = None
        commandType = None
        special_items = None

        if "fill_anywhere" in args:
            dicCommand["name"] = args["fill_anywhere"]
            # if not within a argument use curent point and simulate pair
            if not argument:
                argument = {"pair": "{", "start": point, "end": point}

        if not dicCommand["name"]:
            return

        elif rexIncludegraphics.match(dicCommand["name"]) and (argument["pair"] == "{" or "fill_anywhere" in args):
            log.debug("rexIncludegraphics matched")

            left = argument["start"]
            right = argument["end"]

            files = tools.list_dir(file_dir if settings["currfile_graphicspath"] else tex_dir, graphics_patterns, ["%s/*" % output_dir, "%s.*" % tex_name_root, "%s.*" % pdf_name_root])
            items = [item["rel_path"] for item in files]
            message = [[item["file_name"], item["rel_path"]] for item in files]

        elif rexInput.match(dicCommand["name"]) and (argument["pair"] == "{" or "fill_anywhere" in args):
            log.debug("rexInput matched")

            left = argument["start"]
            right = argument["end"]

            if dicCommand["name"] == "include":
                files = tools.list_dir(tex_dir, ["*.tex"], [tex_name, os.path.relpath(view.file_name(), tex_dir), "%s/*" % output_dir])
                items = [tools.remove_extension(item["rel_path"], ".tex") for item in files]
            else:
                files = tools.list_dir(tex_dir, tex_pattern, [tex_name, os.path.relpath(view.file_name(), tex_dir), "%s/*" % output_dir])
                items = [item["rel_path"] for item in files]
            message = [[item["file_name"], item["rel_path"]] for item in files]

        elif rexChapter.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexChapter matched")

            label = settings["label_format"]
            label_type = settings["label_type"]

            prefix = tools.validate_filename(tex_file.get_option("prefix", "", root=False))
            prefix = prefix if prefix else tools.validate_filename(os.path.splitext(tex_file.file_name)[0])

            name = tools.validate_filename(argument["content"])

            if tex_file.file_path == tex_path:
                label = re.sub(r"\{prefix\}[^\{]*(?=\{|$)", "", label)

            commandType = "noMessage"
            if dicCommand["name"].startswith("part"):
                expr = "\label{%s}" % label.format(type=label_type["part"] if "part" in label_type else "prt", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("chapter"):
                expr = "\label{%s}" % label.format(type=label_type["chapter"] if "chapter" in label_type else "cha", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("section"):
                expr = "\label{%s}" % label.format(type=label_type["section"] if "section" in label_type else "sec", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("subsection"):
                expr = "\label{%s}" % label.format(type=label_type["subsection"] if "subsection" in label_type else "ssec", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("subsubsection"):
                expr = "\label{%s}" % label.format(type=label_type["subsubsection"] if "subsubsection" in label_type else "sssec", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("paragraph"):
                expr = "\label{%s}" % label.format(type=label_type["paragraph"] if "paragraph" in label_type else "par", prefix=prefix, name=name)
            elif dicCommand["name"].startswith("subparagraph"):
                expr = "\label{%s}" % label.format(type=label_type["subparagraph"] if "subparagraph" in label_type else "spar", prefix=prefix, name=name)

            if expr and view.find(expr, point, sublime.LITERAL):
                view.run_command("ltx_select_point", {"point": view.find(expr, point, sublime.LITERAL).b})
            elif expr:
                expr = tools.indention(view.substr(view.full_line(point))) + expr
                view.run_command("ltx_insert_text", {"point": view.full_line(point).b, "string": expr, "new_line": True})
            else:
                sublime.status_message("Status: Cannot find any corresponding action")

        elif rexCaption.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexChapter matched")

            commandType = "noMessage"
            # Find unclosed begin blocks
            stack = tools.find_unclosed_environments(view.substr(sublime.Region(0, point)))

            expr = None
            for s in stack[::-1]:

                label = settings["label_format"]
                label_type = settings["label_type"]

                prefix = tools.validate_filename(tex_file.get_option("prefix", "", root=False))
                prefix = prefix if prefix else tools.validate_filename(os.path.splitext(tex_file.file_name)[0])

                name = tools.validate_filename(argument["content"])

                if tex_file.file_path == tex_path:
                    label = re.sub(r"\{prefix\}[^\{]*(?=\{|$)", "", label)

                if "table" in s:
                    expr = "\label{%s}" % label.format(type=label_type["table"] if "table" in label_type else "tbl", prefix=prefix, name=name)
                    break
                elif "figure" in s:
                    expr = "\label{%s}" % label.format(type=label_type["figure"] if "figure" in label_type else "fig", prefix=prefix, name=name)
                    break

            if expr and view.find(expr, point, sublime.LITERAL):
                view.run_command("ltx_select_point", {"point": view.find(expr, point, sublime.LITERAL).b})
            elif expr:
                expr = tools.indention(view.substr(view.full_line(point))) + expr
                view.run_command("ltx_insert_text", {"point": view.full_line(point).b, "string": expr, "new_line": True})
            else:
                sublime.status_message("Status: Cannot find any corresponding action")

        elif rexBibliography.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexBibliography matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            if dicCommand["name"] == "bibliography":
                files = tools.list_dir(tex_dir, bibliography_pattern, ["%s/*" % output_dir], walk=False)
                items = [tools.remove_extension(item["rel_path"], settings["default_bib_extension"]) for item in files]
            else:
                files = tools.list_dir(tex_dir, bibliography_pattern, ["%s/*" % output_dir], walk=False)
                items = [item["rel_path"] for item in files]
            message = [[item["file_name"], item["rel_path"]] for item in files]

        elif rexCite.match(dicCommand["name"]) and (argument["pair"] == "{" or "fill_anywhere" in args):
            log.debug("rexCite matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            commandType = "cite"

            items = []
            special_items = []
            message = []

            try:
                args = []
                args_bibliography = tex_file.bibliography()

                if args_bibliography:
                    for bib_path in args_bibliography:
                        bib_file = cache.BibFile(bib_path)
                        bib_file.run()
                        args += bib_file.cites()

                    if not settings["remote_bibliography_in_category"]:
                        args += cite.find_remote_cites(args)

                    args = sorted(args, key=lambda x: x[1].key.lower())
                    items = [post.key for file_pathg, post in args if args]
                    special_items = args
                    message = [post.string(panel_format=True) for file_path, post in args if items]
                else:
                    args_bibitem = tex_file.get("bibitem")
                    if args_bibitem:
                        args = [{"key": item["arguments"][0].split(":", 1)[1], "file_name": os.path.basename(file_path)} for file_path, item in args_bibitem]
                        items = [item["key"] for item in args if args]
                        message = [["%s" % item["key"], "Bibitem in \"%s\"" % item["file_name"]] for item in args if args]
                    else:
                        if not settings["remote_bibliography_in_category"]:
                            args = cite.find_remote_cites(args)
                        args = sorted(args, key=lambda x: x[1].key.lower())
                        items = [post.key for file_path, post in args if args]
                        special_items = args
                        message = [post.string(panel_format=True) for file_path, post in args if items]

            except Exception as e:
                log.error(e)
                items = []
                message = []

            if settings["remote_bibliography_in_category"] and (settings["bibsonomy"] or settings["citeulike"] or settings["mendeley"] or settings["zotero"] or settings["global_bib_file"]):
                items.insert(0, "")
                special_items.insert(0, "")
                message.insert(0, ["Remote Reference", "Import references from a remote library e.g. Bibsonomy.org or a Global Bibliography"])

        elif re.match(r"\b\w*hyperref\b", dicCommand["name"], re.IGNORECASE):
            log.debug("rexHref matched")

            if argument["pair"] != "[":
                return

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            args = tex_file.get("label")
            items = [item["arguments"][0].split(":", 1)[1] for file_path, item in args]
            message = [[item["arguments"][0].split(":", 1)[1], os.path.relpath(file_path, tex_dir)] for file_path, item in args]

        elif rexRef.match(dicCommand["name"]) and (argument["pair"] == "{" or "fill_anywhere" in args):
            log.debug("rexRef matched")

            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            args = tex_file.get("label")
            items = [item["arguments"][0].split(":", 1)[1] for file_path, item in args]
            message = [[item["arguments"][0].split(":", 1)[1], os.path.relpath(file_path, tex_dir)] for file_path, item in args]

        elif rexAc.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexAc matched")

            left = argument["start"]
            right = argument["end"]

            args = tex_file.get("ac")
            items = [item["arguments"][0].split(":", 1)[1] for file_path, item in args]
            message = ["%s (%s)" % (item["arguments"][-1].split(":", 1)[1], item["arguments"][0].split(":", 1)[1]) for file_path, item in args]

        elif rexUsepackage.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexUsepackage matched")

            commandType = "noMessage"
            commaLeft = view.substr(sublime.Region(argument["start"], point))[::-1].find(",")
            commaRight = view.substr(sublime.Region(point, argument["end"])).find(",")

            left = point - commaLeft if commaLeft >= 0 else argument["start"]
            right = point + commaRight if commaRight >= 0 else argument["end"]

            if dicCommand["name"] == "bibliographystyle":
                commands.KpsewhichCommand(self.view).run(left, right, "bst")
            elif dicCommand["name"] == "documentclass":
                commands.KpsewhichCommand(self.view).run(left, right, "cls")
            else:
                commands.KpsewhichCommand(self.view).run(left, right, "sty")

        elif rexLabel.match(dicCommand["name"]) and argument["pair"] == "{":
            log.debug("rexLabel matched")

            commandType = "noMessage"
            commands.LtxRenameLabelCommand(self.view).run(argument["content"])

        if commandType == "noMessage":
            pass
        elif not message:
            sublime.status_message("Status: Cannot find any corresponding items")
        else:
            def on_done(i):
                if i >= 0:
                    if commandType == "cite" and i == 0 and not items[0]:
                        view.run_command("ltx_cite_import", {"left": left, "right": right})
                    else:
                        view.run_command("ltx_replace_region", {"region": (left, right), "string": items[i]})
                        if special_items and commandType == "cite":
                            file_path, item = special_items[i]
                            if file_path in ["Citeulike.org", "Bibsonomy.org", "Mendeley.com", "Zotero.org", "Global Bibliography"]:
                                bib_path = os.path.join(tex_dir, settings["bibname"])
                                if not os.path.isfile(bib_path):
                                    if sublime.ok_cancel_dialog("%s do not exist. Would you like to create the file?" % settings["bibname"], "Create"):
                                        with open(bib_path, 'w+', encoding="utf-8", errors="ignore"):
                                            pass
                                    else:
                                        return
                                bib_file = cache.BibFile(bib_path, True)
                                bib_file.run()
                                bib_file.add_cite(item)
                                bib_file.save()
                                if not bib_file.error:
                                    sublime.status_message("Saved %s in %s." % (item.key, settings["bibname"]))
                                else:
                                    sublime.error_message("Error while saving %s in %s." % (item.key, settings["bibname"]))

            sublime.set_timeout(lambda: view.window().show_quick_panel(message, on_done), 0)
