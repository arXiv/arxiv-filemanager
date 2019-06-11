from typing import List

from ...domain import IChecker
from .file_extensions import FixFileExtensions
from .file_type import InferFileType
from .invalid_types import FlagInvalidSourceTypes, FlagInvalidFileTypes
from .hidden_files import RemoveMacOSXHiddenFiles, RemoveFilesWithLeadingDot
from .processed import WarnAboutProcessedDirectory
from .source_types import InferSourceType
from .unpack import UnpackCompressedTarFiles, UnpackCompressedZIPFiles
from .file_names import FixWindowsFileNames, WarnAboutTeXBackupFiles, \
    ReplaceIllegalCharacters, ReplaceLeadingHyphen, PanicOnIllegalCharacters
from .errata import RemoveHyperlinkStyleFiles, RemoveDisallowedFiles, \
    RemoveMetaFiles, RemoveExtraneousRevTeXFiles, RemoveDiagramsPackage, \
    RemoveAADemoFile, RemoveMissingFontFile, RemoveSyncTeXFiles, \
    FixTGZFileName, RemoveDOCFiles, CheckForBibFile
from .tex_generated import RemoveTeXGeneratedFiles, DisallowDVIFiles
from .cleanup import UnMacify, CleanupPostScript, RepairDOSEPSFiles
from .tex_format import CheckTeXForm
from .images import CheckForUnacceptableImages
from .uuencoded import CheckForUUEncodedFiles
from .ancillary import AncillaryFileChecker
from .zero_length_files import ZeroLengthFileChecker


CHECKS = [
    # These go first, since they remove files and directories.
    RemoveMacOSXHiddenFiles,
    RemoveFilesWithLeadingDot,
    ZeroLengthFileChecker,

    WarnAboutProcessedDirectory,      # Just warns.

    # Fix up malformed filenames.
    FixWindowsFileNames,
    AncillaryFileChecker,

    WarnAboutTeXBackupFiles,         # Just warns.

    # Fix up malformed filenames.
    ReplaceIllegalCharacters,
    ReplaceLeadingHyphen,
    RemoveHyperlinkStyleFiles,
    RemoveDisallowedFiles,
    RemoveMetaFiles,

    CheckForBibFile,
    RemoveExtraneousRevTeXFiles,
    RemoveDiagramsPackage,
    RemoveAADemoFile,
    RemoveMissingFontFile,
    RemoveSyncTeXFiles,
    PanicOnIllegalCharacters,
    RemoveTeXGeneratedFiles,
    FixTGZFileName,
    RemoveDOCFiles,

    InferFileType,
    DisallowDVIFiles,
    FixFileExtensions,
    UnMacify,
    CleanupPostScript,
    CheckTeXForm,
    CheckForUnacceptableImages,
    CheckForUUEncodedFiles,
    RepairDOSEPSFiles,
    FlagInvalidFileTypes,
    InferSourceType,
    FlagInvalidSourceTypes,

    UnpackCompressedTarFiles,
    UnpackCompressedZIPFiles,
]


def get_default_checkers() -> List[IChecker]:
    return [check() for check in CHECKS]
