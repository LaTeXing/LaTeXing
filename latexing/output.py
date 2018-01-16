import sublime

import functools
import os
import platform
import re

from . import logger
from . import tools

log = logger.getLogger(__name__)


class LogFilter:

    def __init__(self, tex_path, file_path):

        self.errors = []
        self.warnings = []
        self.badboxes = []

        self.tex_dir, self.tex_name = os.path.split(tex_path)
        self.file_path = file_path

        self.cookie = None
        self.partialFileName = ""
        self.stackFile = []

        self.outputline = 0

        self.currentItem_type = ""
        self.currentItem_sourceLine = 0
        self.currentItem_outputline = 0
        self.currentItem_message = ""

    def parse(self):
        spaceAtStart = re.compile("^\\s")
        spaceAtEnd = re.compile("\\s\\s$")

        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as src_file:
            for line in src_file.readlines():
                stripLine = (" " if spaceAtStart.search(line) else "") + line.strip() + (" " if spaceAtEnd.search(line) else "")
                # stripLine = line.strip()

                self.parseLine(stripLine)
                self.outputline += 1

        errors = [("E: %s:%s %s") % (file_name, line, error) for file_name, line, error in self.errors]
        warnings = [("W: %s:%s %s") % (file_name, line, warning) for file_name, line, warning in self.warnings]
        badboxes = [("B: %s:%s %s") % (file_name, line, badbox) for file_name, line, badbox in self.badboxes]

        return errors, warnings, badboxes

    def fileExists(self, file_path):
        if platform.system() == "Windows":
            file_path = os.path.normcase(file_path)

        if not os.path.isabs(file_path):
            file_path = os.path.join(self.tex_dir, file_path)

        return os.path.isfile(file_path)

    def appendCurrentItem(self):
        while self.stackFile and not self.fileExists(self.stackFile[len(self.stackFile) - 1][0]):
            self.stackFile.pop()

        file_path = self.stackFile[len(self.stackFile) - 1][0] if self.stackFile else os.path.join(".", self.tex_name)

        if not os.path.isabs(file_path):
            file_path = os.path.normpath(os.path.join(self.tex_dir, file_path))
            # file_path = os.path.normpath(os.path.join(self.tex_dir, os.path.relpath(file_path, self.tex_dir)))

        self.currentItem_message = re.sub("[ \t]+", " ", self.currentItem_message.strip())

        if self.currentItem_type == "Error":
            self.errors.append((file_path, self.currentItem_sourceLine, self.currentItem_message))

        elif self.currentItem_type == "Warning":
            self.warnings.append((file_path, self.currentItem_sourceLine, self.currentItem_message))

        elif self.currentItem_type == "BadBox":
            self.badboxes.append((file_path, self.currentItem_sourceLine, self.currentItem_message))

        self.currentItem_type = ""
        self.currentItem_message = ""
        self.currentItem_outputline = 0
        self.currentItem_sourceLine = 0

    def parseLine(self, line):
        if self.cookie == "Start":
            if not (self.detecterror(line) or self.detectWarning(line) or self.detectBadBox(line)):
                self.updateFileStack(line)

        elif self.cookie == "Warning":
            self.detectWarning(line)

        elif self.cookie == "Error" or self.cookie == "LineNumber":
            self.detecterror(line)

        elif self.cookie == "BadBox":
            self.detectBadBox(line)

        elif self.cookie == "FileName" or self.cookie == "FileNameHeuristic":
            self.updateFileStack(line)

        else:
            self.cookie = "Start"

    def updateFileStack(self, line):
        if self.cookie == "Start" or self.cookie == "FileNameHeuristic":
            if line.startswith(":<+ "):
                self.partialFileName = line[4:].strip()

                self.cookie = "FileName"

            elif line.startswith(":<- "):
                if self.stackFile:
                    self.stackFile.pop()

                self.cookie = "Start"

            else:
                self.updateFileStackHeuristic(line)

        elif self.cookie == "FileName":
            if line.startswith("(") or line.startswith("\\openout"):
                self.stackFile.append((self.partialFileName, True))

                self.partialFileName = ""
                self.cookie = "Start"

            elif line.startswith("!"):
                self.partialFileName = ""
                self.cookie = "Start"

                self.detecterror(line)

            elif line.startswith("No file"):
                self.partialFileName = ""
                self.cookie = "Start"

                self.detectWarning(line)

            else:
                self.partialFileName += line.strip()

    def updateFileStackHeuristic(self, line):
        ext = re.compile("\\.(tex|bib|bbl|aux)", re.IGNORECASE)
        expectFileName = self.cookie == "FileNameHeuristic"
        index = 0

        if expectFileName and len(line) and line.startswith(")"):
            self.stackFile.append((self.partialFileName, False))

            expectFileName = False
            self.cookie = "Start"

        for i in range(len(line)):
            isLastChar = i + 1 == len(line)
            nextIsTerminator = False if isLastChar else line[i + 1] == ")" or ext.search(line[i - 3:i + 1])

            if expectFileName and (isLastChar or nextIsTerminator):
                self.partialFileName += line[index:i + 1]

                if platform.system() == "Windows":
                    self.partialFileName = self.partialFileName.strip("\"")

                if not len(self.partialFileName):
                    continue

                if (isLastChar and i < 78) or nextIsTerminator or self.fileExists(self.partialFileName):
                    self.stackFile.append((self.partialFileName, False))

                    expectFileName = False
                    self.cookie = "Start"

                elif isLastChar:
                    if self.fileExists(self.partialFileName):
                        self.stackFile.append((self.partialFileName, False))

                        expectFileName = False
                        self.cookie = "Start"

                    else:
                        self.cookie = "FileNameHeuristic"

                else:
                    self.cookie = "Start"
                    self.partialFileName = ""
                    expectFileName = False

            elif line[i] == "(":
                self.cookie = "Start"
                self.partialFileName = ""
                expectFileName = True

                index = i + 1

            elif line[i] == ")":
                if self.stackFile and not self.stackFile[len(self.stackFile) - 1][1]:
                    self.stackFile.pop()

    def detecterror(self, line):
        exprLaTeXError = re.search("^! LaTeX Error: (.*)$", line, re.IGNORECASE)
        exprPDFLaTeXError = re.search("^Error: pdflatex (.*)$", line, re.IGNORECASE)
        exprTeXError = re.search("^! (.*)\\.$", line)
        exprPackageError = re.search("^! Package (.*) Error:(.*)$", line, re.IGNORECASE)

        exprLineNumber = re.search("^(\\.{3} )?l\\.([0-9]+)(.*)", line)

        found = None
        append = None

        if self.cookie == "Start":
            if exprLaTeXError:
                self.currentItem_message = exprLaTeXError.group(1)
                found = True

            elif exprPDFLaTeXError:
                self.currentItem_message = exprPDFLaTeXError.group(1)
                found = True

            elif exprTeXError:
                self.currentItem_message = exprTeXError.group(1)
                found = True

            elif exprPackageError:
                self.currentItem_message = exprPackageError.group(2)
                found = True

            if found:
                self.cookie = "LineNumber" if line.endswith(".") else "Error"
                self.currentItem_outputline = self.outputline

        elif self.cookie == "Error":
            if line.endswith("."):
                self.cookie = "LineNumber"
                self.currentItem_message += line

            elif self.outputline - self.currentItem_outputline > 3:
                log.error("BAILING OUT: error description spans more than three lines")

                self.cookie = "Start"
                append = True

        elif self.cookie == "LineNumber":
            if exprLineNumber:
                self.currentItem_sourceLine = int(exprLineNumber.group(2))
                self.currentItem_message += exprLineNumber.group(3)

                self.cookie = "Start"
                append = True

            elif self.outputline - self.currentItem_outputline > 10:
                log.error("BAILING OUT: did not detect a TeX line number for an error")

                self.currentItem_sourceLine = 0

                self.cookie = "Start"
                append = True

        if found:
            self.currentItem_type = "Error"
            self.currentItem_outputline = self.outputline

        if append:
            self.appendCurrentItem()

        return found

    def detectWarning(self, line):
        exprLaTeXWarning = re.search("^(((! )?(La|pdf)TeX)|Package|Class) .*Warning *:(.*)", line, re.IGNORECASE)
        exprNoFile = re.search("No file (.*)", line)
        exprNoAsyFile = re.search("File .* does not exist.", line)

        found = None
        append = None

        if self.cookie == "Start":
            if exprLaTeXWarning:
                found = True
                self.cookie = "Start"

                self.currentItem_outputline = self.outputline
                self.currentItem_message, append = self.detectLaTeXLineNumber(exprLaTeXWarning.group(5), len(line))

            elif exprNoFile:
                found = True
                append = True

                self.currentItem_sourceLine = 0
                self.currentItem_outputline = self.outputline
                self.currentItem_message = exprNoFile.group(0)

            elif exprNoAsyFile:
                found = True
                append = True

                self.currentItem_sourceLine = 0
                self.currentItem_outputline = self.outputline
                self.currentItem_message = exprNoAsyFile.group(0)

        elif self.cookie == "Warning":
            self.currentItem_message, append = self.detectLaTeXLineNumber(self.currentItem_message + line, len(line))

        if found:
            self.currentItem_type = "Warning"
            self.currentItem_outputline = self.outputline

        if append:
            self.appendCurrentItem()

        return found

    def detectLaTeXLineNumber(self, string, length):
        exprLaTeXLineNumber = re.search("(.*) on input line ([0-9]+)\\.$", string, re.IGNORECASE)
        # exprInternationalLaTeXLineNumber = re.search("(.*)([0-9]+)\\.$", string, re.IGNORECASE);

        if exprLaTeXLineNumber:
            self.currentItem_sourceLine = int(exprLaTeXLineNumber.group(2))
            string = exprLaTeXLineNumber.group(1)
            self.cookie = "Start"

            return string, True

        elif string.endswith("."):
            self.currentItem_sourceLine = 0
            self.cookie = "Start"

            return string, True

        elif self.outputline - self.currentItem_outputline > 5 or not length:
            self.currentItem_sourceLine = 0
            self.cookie = "Start"

            return string, True

        else:
            self.cookie = "Warning"
            return string, False

    def detectBadBox(self, line):
        exprBadBox = re.search("^(Over|Under)(full \\\\[hv]box .*)", line, re.IGNORECASE)

        found = None
        append = None

        if self.cookie == "Start":
            if exprBadBox:
                found = True
                self.cookie = "Start"

                self.currentItem_message, append = self.detectBadBoxLineNumber(line, len(line))

        elif self.cookie == "BadBox":
            self.currentItem_message, append = self.detectBadBoxLineNumber(self.currentItem_message + line, len(line))

        if found:
            self.currentItem_type = "BadBox"
            self.currentItem_outputline = self.outputline

        if append:
            self.appendCurrentItem()

        return found

    def detectBadBoxLineNumber(self, string, length):
        exprBadBoxLines = re.search("(.*) at lines ([0-9]+)--([0-9]+)", string, re.IGNORECASE)
        exprBadBoxLine = re.search("(.*) at line ([0-9]+)", string, re.IGNORECASE)
        exprBadBoxOutput = re.search("(.*)has occurred while \\output is active^", string, re.IGNORECASE)

        if exprBadBoxLines:
            self.cookie = "Start"
            string = exprBadBoxLines.group(1)

            i1 = int(exprBadBoxLines.group(2))
            i2 = int(exprBadBoxLines.group(3))
            self.currentItem_sourceLine = i1 if i1 < i2 else i2

            return string, True

        elif exprBadBoxLine:
            self.cookie = "Start"
            string = exprBadBoxLine.group(1)
            self.currentItem_sourceLine = int(exprBadBoxLine.group(2))

            return string, True

        elif exprBadBoxOutput:
            self.cookie = "Start"
            string = exprBadBoxOutput.group(1)
            self.currentItem_sourceLine = 0

            return string, True

        elif self.outputline - self.currentItem_outputline > 5 or not length:
            self.cookie = "Start"
            self.currentItem_sourceLine = 0

            return string, True

        else:
            self.cookie = "BadBox"
            return string, False


class Panel():

    def __init__(self, window, file_regex=None, show=True, clc=False):
        self.view = window.create_output_panel("exec")
        self.window = window

        settings = tools.load_settings("Preferences", color_scheme="")

        self.view.settings().set("color_scheme", settings['color_scheme'])
        self.view.settings().set("syntax", "Packages/LaTeXing/support/LaTeXing Log.hidden-tmLanguage")

        if file_regex:
            self.view.settings().set("result_file_regex", file_regex)

        self.view.set_read_only(True)

        if show:
            self.show()
        if clc:
            self.view.run_command("ltx_clear_view")

    def show(self):
        self.window.run_command("show_panel", {"panel": "output.exec"})

    def hide(self):
        self.window.run_command("hide_panel", {"panel": "output.exec"})

    def log(self, s):
        if not len(s):
            return
        # Join list to string and replace the different new line characters
        s = s + "\n" if not isinstance(s, list) else "\n".join(s) + "\n"
        s = s.replace('\r\n', '\n').replace('\r', '\n')

        sublime.set_timeout(functools.partial(self.do_log, s), 0)

    def do_log(self, s):
        self.view.run_command("ltx_append_text", {"string": s})

    def finish(self):
        self.view.run_command("ltx_select_point", {"point": 0})
