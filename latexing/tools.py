import sublime
import sublime_plugin

import fnmatch
import json
import os
import re
import string
import unicodedata

from . import logger

log = logger.getLogger(__name__)


class LtxSettings(object):

    __shared = {}
    __settings = {}

    def __new__(cls, *args, **kwargs):
        inst = object.__new__(cls)
        inst.__dict__ = cls.__shared
        return inst

    def get(self, key, fallback=None):
        return self.__settings[key] if key in self.__settings else fallback

    def set(self, key, value):
        self.__settings[key] = value


def line_number_of_tag(file_path, tag, offset=0):
    src_lines = read_file_lines(file_path, None)
    rex = re.compile(re.escape(tag))
    for line in src_lines[offset:]:
        offset += 1
        if rex.search(line):
            return offset
    return offset


def list_dir(path, files_to_include, files_to_ignore=[], dirs_to_ignore=[], walk=True, include_by_default=False):
    files = []
    # Appand sep to the end of required
    path = path + os.sep if not path.endswith(os.sep) else path
    for root, dir_names, file_names in os.walk(path):
        # Just proceed if walk is enabled or root path is the search path
        if walk or root is path:
            for name in file_names:
                # Build full path and skip directories
                full_path = os.path.join(root, name)
                if os.path.isdir(full_path):
                    continue
                rel_path = full_path.replace(path, "") if full_path.startswith(path) else full_path

                if file_match(rel_path, dirs_to_ignore):
                    continue

                if include_by_default:
                    # Switched the pattern for include and ignore to realise the include_by_default function
                    if file_match(rel_path, files_to_ignore, files_to_include):
                        continue
                else:
                    if not file_match(rel_path, files_to_include, files_to_ignore):
                        continue

                files += [{"file_name": name, "rel_path": rel_path.replace(os.sep, "/"), "full_path": full_path.replace(os.sep, "/")}]
    return files


def file_match(rel_path, files_to_include, files_to_ignore=[]):
    for p in files_to_include:
        if fnmatch.fnmatch(rel_path.lower(), p.lower()):
            for p in files_to_ignore:
                if fnmatch.fnmatch(rel_path.lower(), p.lower()):
                    return False
            return True
    return False


def read_file_content(file_path, commentChar=r"%", preceding_Text=r"[^\\]", encoding=None, raw=False):
    if raw:
        with open(file_path, 'r', encoding='utf_8' if encoding else detect_encoding(), errors="ignore") as f:
            return f.read()
    else:
        return "\n".join(read_file_lines(file_path, commentChar, preceding_Text, encoding, lines=False)[0])


def read_file_lines(file_path, commentChar=r"%", preceding_Text=r"[^\\]", encoding=None, lines=True):
    log.trace("%s %s %s %s" % (file_path, commentChar, preceding_Text, encoding), level=3)

    rex = re.compile(r'(?<=%s)%s.*' % (preceding_Text, commentChar))
    rex = re.compile(r'(^%s.*)|((?<=%s)%s.*)' % (commentChar, preceding_Text, commentChar))
    src_lines = []
    option_lines = []
    try:
        with open(file_path, 'r', encoding='utf_8' if encoding else detect_encoding(), errors="ignore") as f:
            line_number = 0
            point = [0, 0]
            # Save content and remove lines with %
            for line in f.readlines():
                # Calculate line_number and point of line
                line_number += 1
                point = [point[1], point[1] + len(line)]

                # Stip line
                line = line.strip()

                # Tex Options
                if line_number < 10 and line and line[0] == "%":
                    option_lines += [line]

                # Break if not line or comment char
                if not line or line[0] == commentChar:
                    continue

                # check for inline comment
                if commentChar:
                    line = rex.sub("", line)

                if line:
                    src_lines += [{"line_number": line_number, "range": point, "content": line}] if lines else [line]
    except:
        pass
    return src_lines, option_lines


def set_place_holders(string):
    dicCommand = split_command(string)
    if "name" in dicCommand:
        command = dicCommand["name"]
        for i in range(len(dicCommand["arguments"])):
            if dicCommand["arguments"][i]["pair"] == "{":
                command += "{${%i:%s}}" % (i + 1, dicCommand["arguments"][i]["content"])
            elif dicCommand["arguments"][i]["pair"] == "[":
                command += "[${%i:%s}]" % (i + 1, dicCommand["arguments"][i]["content"])
            elif dicCommand["arguments"][i]["pair"] == "(":
                command += "(${%i:%s})" % (i + 1, dicCommand["arguments"][i]["content"])
    else:
        command = string
    # log.trace("%s %s" % (string, command), level = 2)
    return command


def read_cwl_file(resource):
    log.trace(resource)

    try:
        content = sublime.load_resource(resource)
        rex = re.compile(r'(^#.*)|(#.*)')

        items = []
        for line in content.split('\n'):
            line = rex.sub("", line).strip()
            if len(line) and line.startswith("\\"):
                items += [line]
    except Exception as e:
        log.error(e)
        items = []

    return [{"file_name": remove_extension(os.path.basename(resource), ".cwl"), "command": item.strip()} for item in items if len(item) > 0]


def find_command_arguments(file_lines, cmd, single=False):
    # log.trace("%s" % cmd, level = 3)

    rex = re.compile(r'\\' + cmd + r'(?P<start>[\{\[\(])(?P<content>[^\}\]\)]+)[\}\]\)]') if single else re.compile(r'\\' + cmd + r'(?P<start>[\{\[\(])')
    open_expr = None

    args = []
    tags = []

    # Search line by line
    for line in file_lines:

        # If unclosed item available
        if open_expr:
            end = end_of_command(line["content"], 0, open_expr)
            if isinstance(end, int):
                # Save item, check tag existince
                tag = open_expr["line"] + line["content"][:end]
                command = split_command(tag)
                if tag not in tags:
                    tags += [tag]
                    args += [{"tag": tag, "line": open_expr["line_number"], "arguments": ["%s:%s" % (c["pair"], c["content"]) for c in command["arguments"]]}]
                open_expr = None
            elif end[0:8] == "Unclosed":
                open_expr = {"line": open_expr["line"] + line["content"], "line_number": open_expr["line_number"], "start": end[9], "balance": int(end[11:])}

        # Normal search
        for expr in rex.finditer(line["content"]):

            start = expr.start()
            end = expr.end() if single else end_of_command(line["content"], expr.start("start"))
            if isinstance(end, int):
                # Save item, check tag existince
                tag = line["content"][start:end]
                if tag not in tags:
                    tags += [tag]
                    if single:
                        args += [{"tag": tag, "line": line["line_number"], "arguments": ["%s:%s" % (expr.group("start"), expr.group("content"))]}]
                    else:
                        command = split_command(tag)
                        args += [{"tag": tag, "line": line["line_number"], "arguments": ["%s:%s" % (c["pair"], c["content"]) for c in command["arguments"]]}]
            elif end[0:8] == "Unclosed":
                open_expr = {"line": line["content"][start:], "line_number": line["line_number"], "start": end[9], "balance": int(end[11:])}

    return args


def add_extension(name, ext):
    log.trace("%s, %s", name, ext)
    return name if name.endswith(ext) else name + ext


def remove_extension(name, ext):
    log.trace("%s, %s", name, ext)
    return name if not name.endswith(ext) else name[:-len(ext)]


def validate_filename(name):
    log.trace("%s" % name)
    validChars = "_%s%s" % (string.ascii_letters, string.digits)
    return re.sub(r"\_+", "_", ''.join(char for char in re.sub(r"(?<=[^\\])\\\w+{([^}]+)}", r"_\1_", name).lower().replace(" ", "_") if char in validChars)).strip("_")


def validate_citekey(cite_key):
    log.trace("%s", cite_key)
    validChars = "%s%s?_" % (string.ascii_letters, string.digits)
    return "".join([char for char in unicodedata.normalize("NFKD", cite_key) if char in validChars])


def replace_ltx_values(i):
    table = {
        "1": "{",
        "2": "}"
    }
    return table[i]


def validate_field(field):
    if not field:
        return field

    # Clean tabs, multiple spaces, new lines
    field = re.sub(r"^[\"\{]+|(?<=[^\\])[\"\}]+$", "", re.sub(r"[\s\t\r\n]+", " ", field))
    # Replace LaTeX Commands
    field = re.sub(r"(?<=[^\\])\{", "\{", field)
    field = re.sub(r"(?<=[^\\])\}", "\}", field)
    field = re.sub(r"(?<=[^\\])\_", "\_", field)
    field = re.sub(r"(?<=[^\\])\&", "\&", field)
    field = re.sub(r"(?<=[^\\])\#", "\#", field)
    field = re.sub(r"(?<=[^\\])\%", "\%", field)
    field = re.sub(r"\|", "{\\textbar}", field)
    field = re.sub(r"<", "{\\textless}", field)
    field = re.sub(r">", "{\\textgreater}", field)
    field = re.sub(r"~", "{\\textasciitilde}", field)
    field = re.sub(r"\^", "{\\textasciicircum}", field)
    field = re.sub(r"\\\\", "{\\textbackslash}", field)

    # Replace different versions of an hypen
    field = re.sub(r"[\u00AD\u2010\u2011\u2012\u2013\u2014\u2015]", "-", field)

    field = re.sub(r"ltx:(\d+)", lambda expr: replace_ltx_values(expr.group(1)), field)
    return field


def tidy_accents(string):
    string = string.lower()
    string = re.sub(r"[ä]", "ae", string)
    string = re.sub(r"[ö]", "oe", string)
    string = re.sub(r"[ü]", "ue", string)
    string = re.sub(r"[àáâãå]", "a", string)
    string = re.sub(r"æ", "ae", string)
    string = re.sub(r"ç", "c", string)
    string = re.sub(r"[èéêë]", "e", string)
    string = re.sub(r"[ìíîï]", "i", string)
    string = re.sub(r"ñ", "n", string)
    string = re.sub(r"[òóôõ]", "o", string)
    string = re.sub(r"œ", "oe", string)
    string = re.sub(r"[ùúû]", "u", string)
    return re.sub(r"[ýÿ]", "y", string)


def split_file_path(file_path):
    file_dir, file_name = os.path.split(file_path)
    file_name_root, file_name_ext = os.path.splitext(file_name)
    return file_dir, file_name, file_name_root, file_name_ext


def find_section_range(view, point):
    log.trace("%s %s", view, point)

    a, b = 0, view.size()

    left = view.substr(sublime.Region(a, point))[::-1]
    right = view.substr(sublime.Region(point, b))

    exprOpen = re.search(r"\}[^\}]+\{(noitces|noitcesbus|noitcesbusbus)\\", left)
    if not exprOpen:
        return None

    # Search for next section of end document
    exprClose = re.search(r"[\t\n\r\s]*\\(" + exprOpen.group(1)[::-1] + "|end\{document\})", right)

    if exprClose:
        return {"point": point, "start": point - exprOpen.end(), "end": point + exprClose.start()}


def find_unclosed_environments(string):
    # Find unclosed begin blocks
    stack = []
    expBegin = re.compile(r"\\(begin|end)\{([^\}]+)\}")

    for expr in expBegin.finditer(re.sub(r"%.*", "", string)):
        if expr.group(1) == "begin":
            stack.append(expr.group(2))
        elif stack[-1] == expr.group(2):
            stack.pop()

    log.trace("%s" % stack)
    return stack


def find_environment_range(view, point, environment):
    log.trace("%s %s %s", view, point, environment)

    row, col = view.rowcol(point)
    a, b = view.text_point(row - 50, 0), view.text_point(row + 50, 0)

    left = view.substr(sublime.Region(a, point))[::-1]
    right = view.substr(sublime.Region(point, b))

    offset_left = start_environment(left, environment)
    offset_right = end_environment(right, environment)

    return {"point": point, "start": point - offset_left, "end": point + offset_right}


def start_environment(left, environment):
    # Set balance to 1 since the point should be in the environment
    balance = 1
    index = -1
    rex = re.compile(r"\}" + re.escape(environment[::-1]) + r"\{(nigeb|dne)\\")

    for expr in rex.finditer(left):
        index = expr.end()
        balance += -1 if expr.group(1) == "nigeb" else 1

        # Break if balance was even
        if balance <= 0:
            break

    if index < 0 and balance <= 0:
        return "NoMatch"
    elif balance > 0:
        return "Unopend:%d" % balance

    return index


def end_environment(right, environment):
    # Set balance to 1 since the point should be in the environment
    balance = 1
    index = -1
    rex = re.compile(r"\\(begin|end)\{" + re.escape(environment) + r"\}")

    for expr in rex.finditer(right):
        index = expr.end()
        balance += -1 if expr.group(1) == "end" else 1

        # Break if balance was even
        if balance <= 0:
            break

    if index < 0 and balance <= 0:
        return "NoMatch"
    elif balance > 0:
        return "Unclosed:%d" % balance

    return index


def document_class(file_lines):
    name, option = "", ""
    try:
        documentclass = find_command_arguments(file_lines, r"documentclass")
        for argument in documentclass[0]["arguments"]:
            if argument.split(":", 1)[0] == "{":
                name = argument.split(":", 1)[1]
            elif argument.split(":", 1)[0] == "[":
                option = argument.split(":", 1)[1]
    except:
        documentclass = None
        pass
    log.trace("%s, %s", documentclass, option)
    return name, option


def tex_options(option_lines):
    options = {}
    rex = re.compile(r"%\s*-\*-\s*(?P<key>\w+)\s*:\s*(?P<value>.+)(?=-\*-)", re.IGNORECASE)
    rex_textools = re.compile(r"%\s*!TEX\s+root\s*=\s*(?P<value>.*)\s*$", re.IGNORECASE)
    for line in option_lines:
        expr = rex.search(line)
        if expr and expr.group("key") in ["root", "program", "prefix", "phrases", "pdf", "tikz"]:
            options[expr.group("key")] = expr.group("value").strip()
            continue
        expr = rex_textools.search(line)
        if expr and "root" in ["root", "program", "prefix", "phrases", "pdf", "tikz"]:
            options["root"] = expr.group("value").strip()
    log.debug(options)
    return options


def find_resources(name):
    items_b = [resource[14:] for resource in sublime.find_resources(name) if resource.startswith("Packages/User/")]
    items_a = [resource[18:] for resource in sublime.find_resources(name) if resource.startswith("Packages/LaTeXing/")]
    return list(set(items_a + items_b))


def load_resource(name, **options):
    prefs = {}
    try:
        f = sublime.load_resource("Packages/User/%s" % name)
    except:
        f = sublime.load_resource("Packages/LaTeXing/%s" % name)

    s = json.loads(f)
    for key1, value1 in options.items():
        if key1 in s:
            if isinstance(value1, dict):
                prefs[key1] = {}
                for key2, value2 in value1.items():
                    prefs[key1][key2] = s[key1][key2] if key2 in s[key1] else value2
            else:
                prefs[key1] = s[key1]
        else:
            prefs[key1] = value1
    log.trace("%s" % prefs)
    return prefs


def load_project_setting(key, fallback=None):
    project_data = sublime.active_window().project_data()
    if not project_data:
        return fallback
    project_settings = project_data["options"] if "options" in project_data else {}
    if key in project_settings:
        if key == "root":
            project_dir = os.path.split(sublime.active_window().project_file_name())[0]
            file_name = project_settings["root"]

            # Append extension if non provided
            settings = load_settings("LaTeXing", default_tex_extension=".tex")
            if not os.path.splitext(file_name)[1]:
                file_name = add_extension(file_name, settings["default_tex_extension"])

            # Normalize path after joining project directory and defined filename
            file_path = os.path.normpath(os.path.join(project_dir, file_name))
            if os.path.isfile(file_path):
                return file_path
        else:
            return project_settings[key]
    return fallback


def load_license(name, **options):
    prefs = {}
    s = sublime.load_settings("%s.sublime-license" % name)
    for key, value in options.items():
        prefs[key] = s.get(key, value)

    return prefs


def load_settings(name, **options):
    prefs = {}
    s = sublime.load_settings("%s.sublime-settings" % name)
    for key, value in options.items():
        prefs[key] = s.get(key, value)
    # Do not print license infos
    if "license" not in prefs:
        log.trace("%s" % prefs)
    return prefs


def move_license(name):
    s = sublime.load_settings("%s.sublime-settings" % name)
    if s.get("username") or s.get("license"):
        save_license(name, **{'username': s.get("username"), 'license': s.get("license")})

        # remove old sublime-settings username/license
        s.erase("username")
        s.erase("license")
        sublime.save_settings("%s.sublime-settings" % name)


def save_license(name, **options):
    s = sublime.load_settings("%s.sublime-license" % name)
    for key, value in options.items():
        s.set(key, value)
    sublime.save_settings("%s.sublime-license" % name)


def save_settings(name, **options):
    s = sublime.load_settings("%s.sublime-settings" % name)
    for key, value in options.items():
        s.set(key, value)
    sublime.save_settings("%s.sublime-settings" % name)


def delete_files(files):
    log.debug("%s" % files)
    message = []
    for file_name in files:
        try:
            os.remove(file_name)
            message.append("Deleted %s" % file_name)
        except:
            message.append("Couldn't delete %s" % file_name)
    return message


def use_packages(file_lines):
    packages = []
    for item in find_command_arguments(file_lines, r"usepackage"):
        try:
            argument = item["arguments"][-1].split(":", 1)
            if argument[0] == "{":
                packages += [package.strip() for package in argument[1].split(",") if package.strip()]
        except Exception as e:
            log.error(e)
    log.debug("%s" % packages)
    return packages


def end_of_argument(string, offset, openPattern, closePattern, balance=0):
    log.trace("%s, %s, %s, %s, %s" % (string, offset, openPattern, closePattern, balance))

    reOpen = re.compile(openPattern)
    rePair = re.compile(r"^[%s%s]|(?<=[^\\])[%s%s]" % (openPattern, closePattern, openPattern, closePattern))
    index = -1

    brakets = rePair.finditer(string, offset)
    for braket in brakets:
        index = braket.end()
        balance += 1 if reOpen.match(braket.group()) else -1

        # Break of balance was even or less (probably a bib file misstake)
        if balance <= 0:
            break

    # Set index to the last index of string
    if index < 0 and balance <= 0:
        return "NoMatch"
    elif balance > 0:
        return "Unclosed:%d" % balance

    return index


def bracket_pairs(string, openPattern, closePattern, offset=0, singlePair=False):
    log.trace("%s, %s, %s, %s, %s" % (string, openPattern, closePattern, offset, singlePair))

    pairs = []
    reOpen = re.compile(r"^(?:[\n\r\t\s]*)([%s])" % "".join(openPattern))
    string = string[offset:]

    exOpen = reOpen.search(string)
    while exOpen:
        for i in range(len(openPattern)):
            if re.match(openPattern[i], exOpen.group(1)):
                start = exOpen.end() - len(exOpen.group(1))
                end = end_of_argument(string, start, openPattern[i], closePattern[i])
                if isinstance(end, int):
                    pairs += [{"pair": exOpen.group(1), "start": offset + start, "end": offset + end, "content": string[start:end]}]
                    offset += end
                else:
                    end = len(string)
                break

        if singlePair:
            break

        string = string[end:]
        exOpen = reOpen.search(string)

    return pairs


def argument_bounds(left, right):
    log.trace("%s %s" % (left, right))

    chars = [[r"\{", r"\}"], [r"\[", r"\]"], [r"\(", r"\)"], [r"<", r">"]]
    start = [end_of_argument(left, 0, cClose, cOpen, 1) for cOpen, cClose in chars]

    try:
        if not any([isinstance(s, int) for s in start]):
            return None
        for i in sorted([s for s in start if isinstance(s, int)]):
            _left = left[i:]
            if re.search(r"^(\**\w+\\)|^([\}\]\)])", _left):
                offset_left = i
                break
        end = end_of_argument(right, 0, chars[start.index(offset_left)][0], chars[start.index(offset_left)][1], 1)
        offset_right = end
    except Exception as e:
        log.error(e)
        end = "NoCommand"

    if start.count(start[0]) == len(start) or isinstance(end, str):
        return None

    return {"offset_left": offset_left, "offset_right": offset_right}


def start_of_command(left, offset_left):
    rex = re.compile(r"^([\}\]\)>])")
    # rex = re.compile(r"^(?:[\n\r\t\s]*)([\}\]])")
    left = left[offset_left:]
    expr = rex.search(left)
    while expr:
        if expr.group(1) == "}":
            end = end_of_argument(left, expr.end() - len(expr.group(1)), r"\}", r"\{")
        elif expr.group(1) == "]":
            end = end_of_argument(left, expr.end() - len(expr.group(1)), r"\]", r"\[")
        elif expr.group(1) == ")":
            end = end_of_argument(left, expr.end() - len(expr.group(1)), r"\)", r"\(")
        elif expr.group(1) == ">":
            end = end_of_argument(left, expr.end() - len(expr.group(1)), r">", r"<")
        if not isinstance(end, str):
            offset_left += end
            left = left[end:]
            expr = rex.search(left)
        else:
            break
    return offset_left


def end_of_command(line, offset=0, open_expr=None):
    # Search for unclosed argument
    if open_expr:
        if open_expr["start"] == "{":
            end = end_of_argument(line, offset, r"\{", r"\}", open_expr["balance"])
        elif open_expr["start"] == "[":
            end = end_of_argument(line, offset, r"\[", r"\]", open_expr["balance"])
        elif open_expr["start"] == "(":
            end = end_of_argument(line, offset, r"\(", r"\)", open_expr["balance"])
        if isinstance(end, int):
            offset = end
        elif end[0:8] == "Unclosed":
            return "Unclosed:%s:%s" % (open_expr["start"], end[9:])

        # Just to support ^ in regex
    line = line[offset:]

    rex = re.compile(r"^(?P<start>[\{\[\(])")
    expr = rex.search(line)

    # Search for command
    while expr:
        if expr.group("start") == "{":
            end = end_of_argument(line, expr.end("start"), r"\{", r"\}", 1)
        elif expr.group("start") == "[":
            end = end_of_argument(line, expr.end("start"), r"\[", r"\]", 1)
        elif expr.group("start") == "(":
            end = end_of_argument(line, expr.end("start"), r"\(", r"\)", 1)
        if isinstance(end, int):
            offset += end
            line = line[end:]
            expr = rex.search(line)
        elif end[0:8] == "Unclosed":
            return "Unclosed:%s:%s" % (expr.group("start"), end[9:])
        else:
            break
    return offset


def find_current_argument(arguments, i):
    log.trace("%s %s" % (arguments, i))
    pos = 0
    for argument in arguments:
        if i >= argument["start"] and i <= argument["end"]:
            return {"argument": argument, "pos": pos}
        pos += 1


def find_command_range(view, point):
    log.trace("%s %s" % (view, point))

    row, col = view.rowcol(point)
    a, b = view.text_point(row - 10, 0), view.text_point(row + 10, 0)

    left = view.substr(sublime.Region(a, point))[::-1]
    right = view.substr(sublime.Region(point, b))

    bounds = argument_bounds(left, right)
    if not bounds:
        return "NoBounds"

    offset_left = start_of_command(left, bounds["offset_left"])
    offset_right = end_of_command(right, bounds["offset_right"])

    rexCommand = re.compile(r"^\**\w+\\")
    left = left[offset_left:]
    expr = rexCommand.search(left)

    if not expr:
        return "NoCommand"

    offset_left += expr.end()

    return {"point": point, "start": point - offset_left, "end": point + offset_right}


def split_command(string, offset=0, strip=True):
    rexName = re.compile(r"(?<=\\)([^\{\[\(]+)")
    pattern = [["\\{", "\\[", "\\("], ["\\}", "\\]", "\\)"]]
    try:
        # Find command name
        expr = rexName.search(string)
        name = expr.group(0)
    except Exception as e:
        log.error(e)
        return "SplitError"

    items = bracket_pairs(string, pattern[0], pattern[1], expr.end())
    log.trace("name: %s, items: %s" % (name, items))
    if strip:
        arguments = [{"pair": item["pair"], "start": offset + item["start"] + len(item["pair"]), "end": offset + item["end"] - len(item["pair"]), "content": item["content"][len(item["pair"]):-len(item["pair"])]} for item in items]
    else:
        arguments = [{"pair": item["pair"], "start": offset + item["start"], "end": offset + item["end"], "content": item["content"]} for item in items]
    return {"name": name, "arguments": arguments}


def indention(s):
    rex = re.compile(r"[\t\s]*(?=[^\t\s])")
    expr = rex.search(s)
    return expr.group() if expr else ""


def list_words(file_lines):
    prefs = load_settings("LaTeXing", phrases_min_count=2, phrases_min_length=3, phrases_max_length=5, phrases_bounding_words=[])

    rex = re.compile(r"((?<=[^\\\w+])[\w ]+)+")
    word_groups = []
    for line in file_lines:
        for item in rex.finditer(line["content"]):
            word_group = item.group().strip(" ").split(" ")
            if len(word_group) >= prefs["phrases_min_length"]:
                word_groups += [word_group]

    items = {}
    for words in word_groups:
        for i in range(len(words)):
            for j in range(max(1, prefs["phrases_min_length"]), min(len(words) - i, prefs["phrases_max_length"]) + 1):
                if words[i + j - 1] in prefs["phrases_bounding_words"]:
                    break
                key = " ".join(words[i:i + j])
                items[key] = 1 if not key in items else items[key] + 1
    return ["%d:%s" % (count, item) for item, count in sorted(items.items(), key=lambda x:x[1], reverse=True) if count >= prefs["phrases_min_count"]]


def detect_encoding(fallback="utf_8"):

    settings = load_settings("LaTeXing", fallback_encoding=fallback)
    fallback = settings["fallback_encoding"]

    view = sublime.active_window().active_view()
    if not view or not view.match_selector(0, "text.tex.latex"):
        return fallback

    encoding = view.encoding()

    encodings = {}
    encodings["UTF-8"] = "utf_8"
    encodings["UTF-8 with BOM"] = "utf_8"
    encodings["UTF-16 LE"] = "utf_16_le"
    encodings["UTF-16 LE with BOM"] = "utf_16_le"
    encodings["UTF-16 BE"] = "utf_16_le"
    encodings["UTF-16 BE with BOM"] = "utf_16_be"
    encodings["Western (Windows 1252)"] = "cp1252"
    encodings["Western (ISO 8859-1)"] = "iso8859_1"
    encodings["Western (ISO 8859-3)"] = "iso8859_3"
    encodings["Western (ISO 8859-15)"] = "iso8859_15"
    encodings["Western (Mac Roman)"] = "mac_roman"
    encodings["DOS (CP 437)"] = "437"
    encodings["Arabic (Windows 1256)"] = "cp1256"
    encodings["Arabic (ISO 8859-6)"] = "iso8859_6"
    encodings["Baltic (Windows 1257)"] = "cp1257"
    encodings["Baltic (ISO 8859-4)"] = "iso8859_4"
    encodings["Celtic (ISO 8859-14)"] = "iso8859_14"
    encodings["Central European (Windows 1250)"] = "cp1250"
    encodings["Central European (ISO 8859-2)"] = "iso8859_2"
    encodings["Cyrillic (Windows 1251)"] = "cp1251"
    encodings["Cyrillic (Windows 866)"] = "cp886"
    encodings["Cyrillic (ISO 8859-5)"] = "iso8859_5"
    encodings["Cyrillic (KOI8-R)"] = "koi8_r"
    encodings["Cyrillic (KOI8-U)"] = "koi8_u"
    encodings["Estonian (ISO 8859-13)"] = "iso8859_13"
    encodings["Greek (Windows 1253)"] = "cp1253"
    encodings["Greek (ISO 8859-7)"] = "iso8859_7"
    encodings["Hebrew (Windows 1255)"] = "cp1255"
    encodings["Hebrew (ISO 8859-8)"] = "iso8859_8"
    encodings["Nordic (ISO 8859-10)"] = "iso8859_10"
    encodings["Romanian (ISO 8859-16)"] = "iso8859_16"
    encodings["Turkish (Windows 1254)"] = "cp1254"
    encodings["Turkish (ISO 8859-9)"] = "iso8859_9"
    encodings["Vietnamese (Windows 1258)"] = "cp1258"

    return encodings[encoding] if encoding in encodings else fallback


def size_of_string(s):
    num = len(s)
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1000.0:
            return "%3.1f %s" % (num, x)
        num /= 1000.0
    return "%3.1f %s" % (num, 'TB')


def replace_text_in_view(view, text, string):
    if view.is_loading():
        sublime.set_timeout(lambda: replace_text_in_view(view, text, string), 50)
    else:
        view.run_command("ltx_replace_text", {"text": text, "string": string})


def search_text_in_view(view, text):
    if view.is_loading():
        sublime.set_timeout(lambda: search_text_in_view(view, text), 50)
    else:
        view.run_command("ltx_select_text", {"text": text})
