from unittest import TestCase
from filemanager.domain import FileType

import os.path

# type_tests.append(['', ''])

name_tests = []


class TestFileTypes(TestCase):
    """Test file type identification logic"""

    def test_get_type_name(self):
        """Test human readable type name lookup."""
        self.assertEqual(FileType.LATEX.name, 'LaTeX', 'Lookup type name')
        self.assertEqual(FileType.TAR.name, 'TAR archive', 'Lookup type name')
        self.assertEqual(FileType.UNKNOWN.name, 'Unknown',
                         'Lookup name for non existent type')


    def test_is_tex_type(self):
        """Test that TeX file types are identified correctly."""
        self.assertTrue(FileType.LATEX.is_tex_type, 'Expected TeX file type')
        self.assertTrue(FileType.TEX.is_tex_type, 'Expected TeX file type')
        self.assertTrue(FileType.TEX_priority2.is_tex_type,
                        'Expected TeX file type')
        self.assertFalse(FileType.HTML.is_tex_type,
                         'Expected non-TeX file type')

    def test_type_priority(self):
        """Spot check type priorities."""
        self.assertEqual(FileType.UNKNOWN.priority, 0,
                         'Unknown type should return lowest priority=0')
        self.assertLess(FileType.BIBTEX.priority, FileType.TEX.priority,
                        'TeX source higher priority than BibTeX')
        self.assertLess(FileType.TEX.priority, FileType.PDFTEX.priority,
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(FileType.LATEX.priority, FileType.LATEX2e.priority,
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(FileType.LATEX2e.priority, FileType.PDFLATEX.priority,
                        'PDFTEX is higher priority then plain TEX source.')

        self.assertLess(FileType.LATEX.priority, FileType.README.priority,
                        'README directives file higher priority than TeX source')

        # Add some specific priority tests to catch inadvertant changes to new
        # list.
        self.assertEqual(FileType.ABORT.priority, 1,
                         'Expect signal for immediate stop.')
        self.assertEqual(FileType.FAILED.priority, 2,
                         'Expect priority for FAILED type guess.')
        # Erick: I incremented these by one because I added FileType.DIRECTORY.
        # -- 2019-06-10
        self.assertEqual(FileType.PDF.priority, 14,
                         'Expect priority for PDF type guess.')
        self.assertEqual(FileType.TEX.priority, 19,
                         'Expect priority for TEX type guess.')
        self.assertEqual(FileType.LATEX.priority, 25,
                         'Expect priority for LATEX type guess.')
        self.assertEqual(FileType.ZIP.priority, 40,
                         'Expect priority for ZIP type guess.')
        self.assertEqual(FileType.INCLUDE.priority, 49,
                         'Expect priority for INCLUDE type guess.')


# Moved a type check test for a GIF image to test_checks_file_type.py.
# --Erick 2019-06-10
class TestExternalMethods(TestCase):
    """Test file type identification logic"""

    def test_abreviated_type_methods(self):
        self.assertEqual(FileType.LATEX.name, 'LaTeX', 'Lookup type name')
        self.assertTrue(FileType.LATEX.is_tex_type, 'Expected TeX file type')
        self.assertTrue(FileType.LATEX2E.is_tex_type, 'Expected TeX file type')
        self.assertTrue(FileType.TEX_PRIORITY.is_tex_type,
                        'Expected TeX file type')
        self.assertFalse(FileType.TEX_FAKE.is_tex_type,
                         'Expected non-TeX file type')
