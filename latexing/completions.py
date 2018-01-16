import sublime
import sublime_plugin

import os.path
import re
import json

from . import cache
from . import logger
from . import tools

log = logger.getLogger(__name__)


class LtxCompletionsListener(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):

        if not view.match_selector(locations[0], "text.tex.latex"):
            return []

        point = locations[0] - len(prefix) - 1
        char = view.substr(sublime.Region(point, point + 1))

        if char != '\\':
            return []

        # Check if only single backslash to enable completion list
        line = view.substr(sublime.Region(view.line(point).a, point + 1))[::-1]
        rexLine = re.compile(r"^(\\+)")
        exprLine = rexLine.search(line)
        if exprLine and exprLine.end() % 2 == 0:
            if prefix:
                return []
            view.run_command("hide_auto_complete")
            return []

        # Find unclosed begin blocks
        stack = tools.find_unclosed_environments(view.substr(sublime.Region(0, point)))

        # Load Settings
        settings = tools.load_settings("LaTeXing",
                                       static_cwl=["tex.cwl", "latex-209.cwl", "latex-dev.cwl", "latex-document.cwl", "latex-l2tabu.cwl", "latex-mathsymbols.cwl"],
                                       dynamic_cwl=True)

        # Parse tex file
        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        # Parse root file
        root_file = tex_file.root_file()
        root_file.run()

        tex_path = root_file.file_path
        tex_dir, tex_name = os.path.split(tex_path)
        cwl_files = [tools.add_extension(cwl_file, ".cwl") for cwl_file in settings["static_cwl"]]

        if settings["dynamic_cwl"]:
            cwl_files.append("class-*%s*.cwl" % root_file.documentclass(root=False)[0])
            for file_path, item in root_file.get("packages", walk=False):
                cwl_files.append(tools.add_extension(item, ".cwl"))

        resources = []
        for cwl_file in cwl_files:
            for resource in sorted(sublime.find_resources(tools.add_extension(cwl_file, ".cwl")), reverse=True):
                if resource.startswith("Packages/User/cwl/"):
                    resources += [resource]
                    break
                elif resource.startswith("Packages/LaTeX-cwl/"):
                    resources += [resource]

        items = []
        for resource in resources:
            items.extend(tools.read_cwl_file(resource))

        for file_path, item in tex_file.get("newcommand", walk=False) + root_file.get("newcommand", walk=False):
            try:
                command = item["arguments"][0].split(":", 1)[1]
                if item["arguments"][1].split(":", 1)[0] == "[":
                    nargs = int(item["arguments"][1].split(":", 1)[1])
                    if len(item["arguments"]) > 2 and item["arguments"][2].split(":", 1)[0] == "[":
                        options = "[option]"
                        arguments = "".join(["{arg%d}" % (i + 1) for i in range(nargs - 1)])
                        items.append({"file_name": os.path.basename(file_path), "command": command + options + arguments})
                    else:
                        arguments = "".join(["{arg%d}" % (i + 1) for i in range(nargs)])
                        items.append({"file_name": os.path.basename(file_path), "command": command + arguments})
                else:
                    items.append({"file_name": os.path.basename(file_path), "command": command})
            except:
                log.debug("skip %s", item)
                pass

        for file_path, item in tex_file.get("newenvironment", walk=False) + root_file.get("newenvironment", walk=False):
            try:
                begin = "\\begin{%s}" % item["arguments"][0].split(":", 1)[1]
                end = "\\end{%s}" % item["arguments"][0].split(":", 1)[1]
                if item["arguments"][1].split(":", 1)[0] == "[":
                    nargs = int(item["arguments"][1].split(":", 1)[1])
                    if len(item["arguments"]) > 2 and item["arguments"][2].split(":", 1)[0] == "[":
                        options = "[option]"
                        arguments = "".join(["{arg%d}" % (i + 1) for i in range(nargs - 1)])
                        items.append({"file_name": os.path.basename(file_path), "command": begin + options + arguments})
                        items.append({"file_name": os.path.basename(file_path), "command": end})
                    else:
                        arguments = "".join(["{arg%d}" % (i + 1) for i in range(nargs)])
                        items.append({"file_name": os.path.basename(file_path), "command": begin + arguments})
                        items.append({"file_name": os.path.basename(file_path), "command": end})
                else:
                    items.append({"file_name": os.path.basename(file_path), "command": begin})
                    items.append({"file_name": os.path.basename(file_path), "command": end})
            except:
                log.debug("skip %s", item)
                pass

        return_items = [("%s\t%s" % (item["command"][1:], item["file_name"]), tools.set_place_holders(item["command"])) for item in sorted(items, key=lambda x:x["command"].lower())]

        # Add unclosed begin blocks to the top of the list
        if stack:
            return_items.insert(0, ("end{%s}\t%s" % (stack[-1], tex_name), "end{%s}" % stack[-1]))

        return return_items, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS


class LtxCompletionsUserPhrasesListener(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):

        if not view.match_selector(locations[0], "text.tex.latex"):
            return []

        if prefix == "TEX":
            return [], sublime.INHIBIT_WORD_COMPLETIONS

        point = locations[0] - len(prefix) - 1

        settings = tools.load_settings("LaTeXing", phrases=False, phrases_mode=1)

        if not settings["phrases"]:
            return []

        # Check if double backslash to enable completion list
        line = view.substr(sublime.Region(view.line(point).a, point + 1))[::-1]
        exprLine = re.search(r"^(\\+)", line)
        if exprLine and exprLine.end() % 2 != 0:
            return []

        tex_file = cache.TeXFile(view.file_name())
        tex_file.run()

        root_file = tex_file.root_file()
        root_file.run()

        user_phrases = tex_file.get_option("phrases")

        return_items = []
        if user_phrases:
            for dic in user_phrases.split(","):
                try:
                    with open(os.path.join(sublime.packages_path(), "User", "%s.latexing-phrases" % dic.strip()), 'r', encoding="utf_8") as f:
                        return_items += [[item.replace(" ", u"\u00A0"), item] for item in json.load(f)]
                except Exception as e:
                    log.error(e)

        if settings["phrases_mode"] > 0:
            used_phrases = tex_file.words(walk=settings["phrases_mode"] == 2)
            return_items += [[phrase[1].replace(" ", u"\u00A0") + "\t%s" % phrase[0], phrase[1]] for file_path, phrase in used_phrases]

        return return_items
