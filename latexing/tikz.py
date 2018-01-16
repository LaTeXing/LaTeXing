import sublime
import sublime_plugin


class LtxTikzLivePreviewCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        return self.view.match_selector(0, "text.tex.latex.tikz")

    def run(self, edit):
        settings = self.view.settings()
        value = settings.get("ltx_live_preview", False)
        settings.set("ltx_live_preview", not value)

        # Save settings to view
        sublime.status_message("Live Preview mode is now " + "enabled." if not value else "disabled.")
