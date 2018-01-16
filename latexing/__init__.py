import datetime
import logging
import os
import tempfile

logging.getLogger().setLevel(logging.CRITICAL)

LTX_VERSION = "1.4.0"
LTX_TESTING = False

LTX_TEMPDIR = os.path.join(tempfile.gettempdir(), "latexing")

from .check_system import LtxCheckSystemCommand

from .cache import LtxRebuildCacheCommand
from .cache import LtxSaveCacheCommand
from .cache import LtxShowCacheCommand

from .clean import LtxCleanCommand
from .clean import LtxCleanTempCommand

from .cite import LtxCiteImportCommand

from .compiler import LtxDefaultCompilerCommand
from .compiler import LtxQuickBuildCompilerCommand
from .compiler import LtxTikzCompilerCommand

from .commands import LtxFoldEnvironmentCommand
from .commands import LtxFoldSectionCommand
from .commands import LtxInsertLatexEnvironmentCommand
from .commands import LtxLatexCommandCommand
from .commands import LtxLatexEnvironmentCommand
from .commands import LtxRenameLatexEnvironmentCommand
from .commands import LtxStarLatexEnvironmentCommand
from .commands import LtxTexcountCommand

from .completions import LtxCompletionsListener
from .completions import LtxCompletionsUserPhrasesListener

from .fill import LtxFillAnywhereCommand
from .fill import LtxFillCommand

from .insert import LtxInsertSpecialSymbolsCommand
from .insert import LtxMove
from .insert import LtxInsertTexSymbolCommand
from .insert import LtxLookupTexSymbolCommand

from .listener import LtxTexListener
from .listener import LtxTikzListener

from .menu import LtxBuyLicenseCommand
from .menu import LtxChangelogCommand
from .menu import LtxInstallLicenseCommand
from .menu import LtxOpenDocumentationCommand
from .menu import LtxVersionCommand
from .menu import LtxOfflineCommand

from .online_lookup import LtxOnlineLookupCommand

from .open import LtxOpenAnywhereCommand
from .open import LtxOpenCommand

from .settings import LtxExtendedPreferencesCommand
from .settings import LtxTogglePreferencesCommand

from .startup import ltx_plugin_loaded

from .sync import LtxSyncDataCommand

from .tikz import LtxTikzLivePreviewCommand

from .phrases import LtxOpenPhrasesDictionaryCommand
from .phrases import LtxSavePhrasesCommand

from .view import LtxClearCommand
from .view import LtxSelectPointCommand
from .view import LtxSelectRowColCommand
from .view import LtxSelectLineCommand
from .view import LtxSelectTextCommand
from .view import LtxAppendTextCommand
from .view import LtxInsertTextCommand
from .view import LtxReplaceTextCommand
from .view import LtxReplaceRegionCommand

from .viewer import LtxJumpToPdfCommand
from .viewer import LtxOpenPdfCommand
