#!/usr/bin/env python

"""
Integration tests for the doorstop.cli package.
"""

import unittest
from unittest.mock import patch, Mock

import os
import shutil
import tempfile

from doorstop.cli.main import main

ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')

ENV = 'TEST_INTEGRATION'  # environment variable to enable integration tests
REASON = "'{0}' variable not set".format(ENV)


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestMain(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop' command."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.temp = tempfile.mkdtemp()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.temp)

    def test_main(self):
        """Verify the 'doorstop' can be called."""
        self.assertIs(None, main([]))

    def test_main_help(self):
        """Verify 'doorstop --help' can be requested."""
        self.assertRaises(SystemExit, main, ['--help'])

    def test_main_error(self):
        """Verify 'doorstop' returns an error in an empty directory."""
        os.chdir(self.temp)
        self.assertRaises(SystemExit, main, [])

    @patch('doorstop.cli.main._run', Mock(return_value=False))
    def test_exit(self):
        """Verify 'doorstop' treats False as an error ."""
        self.assertRaises(SystemExit, main, [])

    @patch('doorstop.cli.main._run', Mock(side_effect=KeyboardInterrupt))
    def test_interrupt(self):
        """Verify 'doorstop' treats KeyboardInterrupt as an error."""
        self.assertRaises(SystemExit, main, [])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestNew(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop new' command."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.temp = tempfile.mkdtemp()

    def tearDown(self):
        os.chdir(self.cwd)
        if os.path.exists(self.temp):
            shutil.rmtree(self.temp)

    def test_new(self):
        """Verify 'doorstop new' can be called."""
        self.assertIs(None, main(['new', '_TEMP', self.temp, '-p', 'REQ']))

    def test_new_error(self):
        """Verify 'doorstop new' returns an error with an unknown parent."""
        self.assertRaises(SystemExit, main,
                          ['new', '_TEMP', self.temp, '-p', 'UNKNOWN'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestAdd(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop add' command."""

    @classmethod
    def setUpClass(cls):
        last = sorted(os.listdir(os.path.join(ROOT, 'reqs', 'tutorial')))[-1]
        number = int(last.replace('TUT', '').replace('.yml', '')) + 1
        filename = "TUT{}.yml".format(str(number).zfill(3))
        cls.path = os.path.join(ROOT, 'reqs', 'tutorial', filename)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_add(self):
        """Verify 'doorstop add' can be called."""
        self.assertIs(None, main(['add', 'TUT']))
        self.assertTrue(os.path.isfile(self.path))

    def test_add_error(self):
        """Verify 'doorstop add' returns an error with an unknown prefix."""
        self.assertRaises(SystemExit, main, ['add', 'UNKNOWN'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestRemove(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop remove' command."""

    def test_remove(self):  # TODO: implement test
        """Verify 'doorstop remove' can be called."""
        self.assertRaises(NotImplementedError, main, ['remove', 'NONE'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestEdit(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop edit' command."""

    @patch('doorstop.core.processor._open')
    def test_edit(self, mock_open):
        """Verify 'doorstop edit' can be called."""
        self.assertIs(None, main(['edit', 'tut2']))
        path = os.path.join(ROOT, 'reqs', 'tutorial', 'TUT002.yml')
        mock_open.assert_called_once_with(os.path.normpath(path))

    def test_edit_error(self):
        """Verify 'doorstop edit' returns an error with an unknown ID."""
        self.assertRaises(SystemExit, main, ['edit', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestImport(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop import' command."""

    def test_import(self):  # TODO: implement test
        """Verify 'doorstop import' can be called."""
        self.assertRaises(NotImplementedError, main, ['import', 'PATH'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestExport(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop export' command."""

    def test_export(self):  # TODO: implement test
        """Verify 'doorstop export' can be called."""
        self.assertRaises(NotImplementedError, main, ['export', 'PATH'])


@unittest.skipUnless(os.getenv(ENV), REASON)  # pylint: disable=R0904
class TestReport(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the 'doorstop report' command."""

    def test_report(self):  # TODO: implement test
        """Verify 'doorstop report' can be called."""
        self.assertRaises(NotImplementedError, main, ['report', 'PATH'])


@patch('doorstop.cli.main._run', Mock(return_value=True))  # pylint: disable=R0904
class TestLogging(unittest.TestCase):  # pylint: disable=R0904
    """Integration tests for the Doorstop CLI logging."""

    def test_verbose_1(self):
        """Verify verbose level 1 can be set."""
        self.assertIs(None, main(['-v']))

    def test_verbose_2(self):
        """Verify verbose level 2 can be set."""
        self.assertIs(None, main(['-v', '-v']))

    def test_verbose_3(self):
        """Verify verbose level 1 can be set."""
        self.assertIs(None, main(['-v', '-v', '-v']))
