import sublime
import sublime_plugin

import os
import re
import shutil
import subprocess
import sys

from . import logger
from . import tools

log = logger.getLogger(__name__)


class KpsewhichCmd():

    def __init__(self):
        self.items = {"bst": [], "cls": [], "sty": []}
        self.cmd = ""
        self.error = False

    def run(self):
        # Find kpsewhich executable
        executable = find_executable("kpsewhich", command_line_tool=True)
        if not executable:
            self.error = True
            return

        cmd = [executable, "--expand-var", "$TEXMF"]
        self.cmd = " ".join(cmd)
        log.debug("cmd %s" % self.cmd)

        try:
            output = communicate(cmd)[0]
        except Exception as e:
            log.error(e)
            self.error = True
            return

        locations = [item.lstrip("!") for item in output.strip("{}\r\n").split(",")]
        for location in locations:
            self.items["bst"] += [tools.remove_extension(item["file_name"], ".bst") for item in tools.list_dir(location, ["*.bst"]) if not item["file_name"].startswith(".")]
            self.items["cls"] += [tools.remove_extension(item["file_name"], ".cls") for item in tools.list_dir(location, ["*.cls"]) if not item["file_name"].startswith(".")]
            self.items["sty"] += [tools.remove_extension(item["file_name"], ".sty") for item in tools.list_dir(location, ["*.sty"]) if not item["file_name"].startswith(".")]

        self.items["bst"] = sorted(list(set(self.items["bst"])))
        self.items["cls"] = sorted(list(set(self.items["cls"])))
        self.items["sty"] = sorted(list(set(self.items["sty"])))


class MthelpCmd():

    def __init__(self, argument):
        self.argument = argument
        self.cmd = ""
        self.error = False

    def run(self):
        # Find mthelp executable
        executable = find_executable("mthelp", command_line_tool=True)
        if not executable:
            self.error = True
            return

        cmd = [executable, "-l", self.argument]
        self.cmd = " ".join(cmd)
        log.debug("cmd %s" % self.cmd)

        try:
            output = communicate(cmd)[0]
        except Exception as e:
            log.error(e)
            self.error = True
            return

        self.items = [line for line in output.split("\r\n") if line]
        self.items = sorted(list(set(self.items)))


class TexdocCmd():

    def __init__(self, argument):
        self.argument = argument
        self.cmd = ""
        self.error = False

    def run(self):
        # Find texdoc executable
        executable = find_executable("texdoc", command_line_tool=True)
        if not executable:
            self.error = True
            return

        cmd = [executable, "--list", "--machine", self.argument]
        self.cmd = " ".join(cmd)
        log.debug("cmd %s" % self.cmd)

        try:
            output = communicate(cmd)[0]
        except Exception as e:
            log.error(e)
            self.error = True
            return

        self.items = [line.split("\t")[2] for line in output.split("\n") if line]
        self.items = sorted(list(set(self.items)))


class TexcountCmd():

    def __init__(self, tex_file):
        self.tex_file = tex_file
        self.items = []
        self.cmd = ""
        self.error = False

    def run(self):
        # Find texcount executable
        executable = find_executable("texcount", command_line_tool=True)
        if not executable:
            self.error = True
            return

        rex = re.compile("(\d+)\+(\d+)\+(\d+)")
        for file_path in self.tex_file.files():
            # Skip if file missing
            if not os.path.exists(file_path):
                continue

            # Skip files outside of the current project
            if not file_path.startswith(self.tex_file.file_dir):
                continue

            file_dir, file_name = os.path.split(file_path)

            cmd = [executable, "-0", file_path]
            self.cmd = " ".join(cmd)
            log.trace("cmd %s" % self.cmd)

            try:
                output = communicate(cmd)[0].strip()
            except Exception as e:
                log.error(e)
                self.error = True
                break

            log.trace("output %s" % output)

            try:
                expr = rex.search(output)
                words = expr.group(1)
                words_headers = expr.group(2)
                words_captions = expr.group(3)

                self.items += [{"file_path": os.path.relpath(file_path, self.tex_file.file_dir), "words": words, "words_headers": words_headers, "words_captions": words_captions, "words_total": str(int(words) + int(words_headers) + int(words_captions))}]
            except Exception as e:
                log.error(e)
                self.error = True
                break


def find_viewer(name):
    log.debug("%s" % name)

    # Load settings
    settings = tools.load_settings("LaTeXing", pdf_viewer_osx={}, pdf_viewer_windows={}, pdf_viewer_linux={})

    if sublime.platform() == "windows":
        # Check if key available
        if name in settings["pdf_viewer_windows"]:
            # Search all available locations
            for item in settings["pdf_viewer_windows"][name]:
                executable = command_executable([item], command_line_tool=False)
                if executable:
                    return executable

    elif sublime.platform() == "osx":
        # Check if key available
        if name in settings["pdf_viewer_osx"]:
            # Search all available locations
            for item in settings["pdf_viewer_osx"][name]:
                if os.path.exists(item):
                    return item

    elif sublime.platform() == "linux":
        # Check if key available
        if name in settings["pdf_viewer_linux"]:
            # Search all available locations
            for item in settings["pdf_viewer_linux"][name]:
                executable = command_executable([item], command_line_tool=False)
                if executable:
                    return executable

    return None


def find_executable(name, error=False, command_line_tool=True):
    log.debug("%s %s %s" % (name, error, command_line_tool))

    # Load settings
    settings = tools.load_settings("LaTeXing", executables={})

    if name == "sublime":

        for item in settings["executables"].get(name, ["subl", "sublime_text", "sublime_text.exe"]):
            executable = command_executable([item], False)

            # Return executable if a match was found
            if executable:
                return executable

        # Fallback search for the different platforms
        for item in settings["executables"].get(name, ["subl", "sublime_text", "sublime_text.exe"]):
            # Fallback search for windows
            if sublime.platform() == "windows":

                # Check in C:\Program Files\Sublime Text 3\
                if os.path.isfile("C:\\Program Files\\Sublime Text 3\\%s" % item):
                    return "C:\\Program Files\\Sublime Text 3\\%s" % item

                # Check in C:\Program Files (x86)\Sublime Text 3\
                if os.path.isfile("C:\\Program Files (x86)\\Sublime Text 3\\%s" % item):
                    return "C:\\Program Files (x86)\\Sublime Text 3\\%s" % item

            # Fallback search for windows
            elif sublime.platform() == "linux":

                # Check in /opt/sublime_text/
                if os.path.isfile("/opt/sublime_text/%s" % item):
                    return "/opt/sublime_text/%s" % item

    else:
        # Search through all options of latex_executables
        for item in settings["executables"].get(name, [name]):
            executable = command_executable([item], command_line_tool)
            log.debug("%s %s" % (item, executable))

            # Return executable if a match was found
            if executable:
                return executable

    # Show error if required
    if error:
        sublime.error_message("The command line tool \"%s\" is not available on your path. Please check your settings." % name)

    # Return None of no match at all
    return None


def command_executable(cmd, command_line_tool=True):
    log.debug("%s %s" % (cmd, command_line_tool))

    # Set environment path
    path_bak = set_envionpath()

    try:
        if not command_line_tool:
            status = shutil.which(cmd[0])
        else:
            version = ["$host.version"] if "powershell" in cmd[0] else ["--version"]
            if sublime.platform() == "windows":
                # Close consol on windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                proc = subprocess.Popen(cmd + version, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            elif sublime.platform() == "osx" or sublime.platform() == "linux":
                proc = subprocess.Popen(cmd + version, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            proc.wait()
            status = proc.returncode == 0

        if not status:
            raise Exception("%s not available" % cmd[0])

    except Exception as e:
        log.debug("%s %s" % (e, os.environ["PATH"]))

        # Always reset the path first
        reset_envionpath(path_bak)

        # Fallback search on PATH if full path is given, useful for different machines with the same setting file
        if os.path.basename(cmd[0]) != cmd[0]:
            cmd[0] = os.path.basename(cmd[0])
            return command_executable(cmd, command_line_tool)
        else:
            return None

    reset_envionpath(path_bak)
    return cmd[0]

# Deprecated, replaced by find_executable
# def command_available(cmd, show_error = False, gui = False):
# 	log.debug("%s" % cmd)

# Load build settings
# 	prefs = tools.load_resource("LaTeX.sublime-build", osx = {"path": ""}, windows = {"path": ""}, linux = {"path": ""})
# 	settings = tools.load_settings("LaTeXing", path = [])
# 	path_bak = os.environ["PATH"]

# 	try:
# 		if sublime.platform() == "windows":
# 			os.environ["PATH"] = os.path.expandvars(prefs[sublime.platform()]["path"]) + ";" + ";".join([path for path in settings["path"] if os.path.isdir(path)])
# 		else:
# 			os.environ["PATH"] = os.path.expandvars(prefs[sublime.platform()]["path"]) + ":" + ":".join([path for path in settings["path"] if os.path.isdir(path)])
# 		if gui:
# 			output = shutil.which(cmd)
# 		else:
# 			if sublime.platform() == "windows":
# Close consol on windows
# 				startupinfo = subprocess.STARTUPINFO()
# 				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
# 				output = subprocess.Popen(cmd, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].decode(sys.getfilesystemencoding())
# 			elif sublime.platform() == "osx":
# 				output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].decode(sys.getfilesystemencoding())
# 			elif sublime.platform() == "linux":
# 				output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].decode(sys.getfilesystemencoding())
# 		if not output:
# 			raise Exception("%s not available" % cmd)

# 	except Exception as e:
# 		log.error(e)
# 		log.error(os.environ["PATH"])
# 		os.environ["PATH"] = path_bak

# Show popup if required
# 		if show_error:
# 			sublime.error_message("The command line tool \"%s\" is not available on your path." % (cmd if isinstance(cmd, str) else cmd[0]))
# 		return False

# 	os.environ["PATH"] = path_bak
# 	return True


def set_envionpath():
    # Load path from sublime-build
    prefs = tools.load_resource("LaTeX.sublime-build", osx={"path": ""}, windows={"path": ""}, linux={"path": ""})
    settings = tools.load_settings("LaTeXing", path=[])
    path_bak = os.environ["PATH"]

    try:
        if sublime.platform() == "windows":
            os.environ["PATH"] = os.path.expandvars(prefs["windows"]["path"]) + ";" + ";".join([path for path in settings["path"] if os.path.isdir(path)])
        elif sublime.platform() == "osx":
            os.environ["PATH"] = os.path.expandvars(prefs["osx"]["path"]) + ":" + ":".join([path for path in settings["path"] if os.path.isdir(path)])
        elif sublime.platform() == "linux":
            os.environ["PATH"] = os.path.expandvars(prefs["linux"]["path"]) + ":" + ":".join([path for path in settings["path"] if os.path.isdir(path)])
    except:
        pass

    return path_bak


def reset_envionpath(path_bak):
    os.environ["PATH"] = path_bak


def communicate(cmd, **args):
    log.debug("%s" % cmd)

    proc = popen(cmd, **args)

    # Communicate and capture stdout, and stderr
    communicate = proc.communicate()
    stdout = communicate[0].decode(sys.getfilesystemencoding())
    stderr = communicate[1].decode(sys.getfilesystemencoding())

    return stdout, stderr


def popen(cmd, **args):
    log.debug("%s" % cmd)

    # Set environment path
    path_bak = set_envionpath()

    try:
        if sublime.platform() == "windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, env=os.environ, **args)
        elif sublime.platform() == "osx" or sublime.platform() == "linux":
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ, **args)

    except Exception as e:
        log.error(e)
        log.error(os.environ["PATH"])

        # Reset environment path
        reset_envionpath(path_bak)

    # Reset environment path
    reset_envionpath(path_bak)

    return proc
