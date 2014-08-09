"""Integration tests for the doorstop.cli package."""

import unittest
from unittest.mock import patch, Mock

import os
import tempfile
import shutil

from doorstop.cli.main import main
from doorstop import common
from doorstop.core.builder import _clear_tree
from doorstop import settings

from doorstop.cli.test import ENV, REASON, ROOT, FILES, REQS, TUTORIAL
from doorstop.cli.test import SettingsTestCase


class TempTestCase(unittest.TestCase):

    """Base test case class with a temporary directory."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.temp = tempfile.mkdtemp()

    def tearDown(self):
        os.chdir(self.cwd)
        if os.path.exists(self.temp):
            shutil.rmtree(self.temp)


class MockTestCase(TempTestCase):

    """Base test case class for a temporary mock working copy."""

    def setUp(self):
        super().setUp()
        os.chdir(self.temp)
        common.touch('.mockvcs')
        _clear_tree()


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestMain(SettingsTestCase):

    """Integration tests for the 'doorstop' command."""

    def setUp(self):
        super().setUp()
        self.cwd = os.getcwd()
        self.temp = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        os.chdir(self.cwd)
        shutil.rmtree(self.temp)

    def test_main(self):
        """Verify 'doorstop' can be called."""
        self.assertIs(None, main([]))

    def test_main_error(self):
        """Verify 'doorstop' returns an error in an empty directory."""
        os.chdir(self.temp)
        self.assertRaises(SystemExit, main, [])

    def test_main_custom_root(self):
        """Verify 'doorstop' can be provided a custom root path."""
        os.chdir(self.temp)
        self.assertIs(None, main(['--project', '.']))

    def test_empty(self):
        """Verify 'doorstop' can be run in a working copy with no docs."""
        os.mkdir(os.path.join(self.temp, '.mockvcs'))
        os.chdir(self.temp)
        self.assertIs(None, main([]))
        self.assertTrue(settings.REFORMAT)
        self.assertTrue(settings.CHECK_REF)
        self.assertTrue(settings.CHECK_CHILD_LINKS)
        self.assertFalse(settings.REORDER)
        self.assertTrue(settings.CHECK_LEVELS)
        self.assertTrue(settings.CHECK_SUSPECT_LINKS)
        self.assertTrue(settings.CHECK_REVIEW_STATUS)

    def test_options(self):
        """Verify 'doorstop' can be run with options."""
        os.mkdir(os.path.join(self.temp, '.mockvcs'))
        os.chdir(self.temp)
        self.assertIs(None, main(['--no-reformat',
                                  '--no-ref-check',
                                  '--no-child-check',
                                  '--reorder',
                                  '--no-level-check',
                                  '--no-suspect-check',
                                  '--no-review-check']))
        self.assertFalse(settings.REFORMAT)
        self.assertFalse(settings.CHECK_REF)
        self.assertFalse(settings.CHECK_CHILD_LINKS)
        self.assertTrue(settings.REORDER)
        self.assertFalse(settings.CHECK_LEVELS)
        self.assertFalse(settings.CHECK_SUSPECT_LINKS)
        self.assertFalse(settings.CHECK_REVIEW_STATUS)


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestCreate(TempTestCase):

    """Integration tests for the 'doorstop create' command."""

    def test_create(self):
        """Verify 'doorstop create' can be called."""
        self.assertIs(None, main(['create', '_TEMP', self.temp, '-p', 'REQ']))

    def test_create_error_unknwon_parent(self):
        """Verify 'doorstop create' returns an error with an unknown parent."""
        self.assertRaises(SystemExit, main,
                          ['create', '_TEMP', self.temp, '-p', 'UNKNOWN'])

    def test_create_error_reserved_prefix(self):
        """Verify 'doorstop create' returns an error with a reserved prefix."""
        self.assertRaises(SystemExit, main,
                          ['create', 'ALL', self.temp, '-p', 'REQ'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestDelete(MockTestCase):

    """Integration tests for the 'doorstop delete' command."""

    def test_delete(self):
        """Verify 'doorstop delete' can be called."""
        main(['create', 'PREFIX', 'prefix'])
        self.assertIs(None, main(['delete', 'PREFIX']))

    def test_delete_error(self):
        """Verify 'doorstop delete' returns an error on unknown document."""
        self.assertRaises(SystemExit, main, ['delete', 'UNKNOWN'])


def get_next_number():
    """Helper function to get the next document number."""
    last = None
    for last in sorted(os.listdir(TUTORIAL), reverse=True):
        if "index" not in last:
            break
    assert last
    number = int(last.replace('TUT', '').replace('.yml', '')) + 1
    return number


@patch('doorstop.settings.SERVER_ADDRESS', None)
@unittest.skipUnless(os.getenv(ENV), REASON)
class TestAdd(unittest.TestCase):

    """Integration tests for the 'doorstop add' command."""

    @classmethod
    def setUpClass(cls):
        number = get_next_number()
        filename = "TUT{}.yml".format(str(number).zfill(3))
        cls.path = os.path.join(TUTORIAL, filename)

    def tearDown(self):
        common.delete(self.path)

    def test_add(self):
        """Verify 'doorstop add' can be called."""
        self.assertIs(None, main(['add', 'TUT']))
        self.assertTrue(os.path.isfile(self.path))

    def test_add_multiple(self):
        """Verify 'doorstop add' can be called with a given positive count"""
        number = get_next_number()
        numbers = (number, number + 1, number + 2)
        self.assertIs(None, main(['add', 'TUT', '--count', '3']))
        filenames = ("TUT{}.yml".format(str(x).zfill(3)) for x in numbers)
        paths = [os.path.join(TUTORIAL, f) for f in filenames]
        self.assertTrue(os.path.isfile(paths[0]))
        self.assertTrue(os.path.isfile(paths[1]))
        self.assertTrue(os.path.isfile(paths[2]))
        os.remove(paths[1])
        os.remove(paths[2])

    def test_add_multiple_non_positive(self):
        """Verify 'doorstop add' rejects non-positive integers for counts."""
        self.assertRaises(SystemExit, main, ['add', 'TUT', '--count', '-1'])

    def test_add_specific_level(self):
        """Verify 'doorstop add' can be called with a specific level."""
        self.assertIs(None, main(['add', 'TUT', '--level', '1.42']))
        self.assertTrue(os.path.isfile(self.path))

    def test_add_error(self):
        """Verify 'doorstop add' returns an error with an unknown prefix."""
        self.assertRaises(SystemExit, main, ['add', 'UNKNOWN'])


@unittest.skip("TODO: enable tests")
@unittest.skipUnless(os.getenv(ENV), REASON)
class TestAddServer(unittest.TestCase):

    """Integration tests for the 'doorstop add' command using a server."""

    @classmethod
    def setUpClass(cls):
        number = get_next_number()
        filename = "TUT{}.yml".format(str(number).zfill(3))
        cls.path = os.path.join(TUTORIAL, filename)

    def tearDown(self):
        common.delete(self.path)

    def test_add(self):
        """Verify 'doorstop add' expects a server."""
        self.assertRaises(SystemExit, main, ['add', 'TUT'])

    @patch('doorstop.settings.SERVER_ADDRESS', None)
    def test_add_no_server(self):
        """Verify 'doorstop add' can be called if there is no server."""
        self.assertIs(None, main(['add', 'TUT']))

    def test_add_disable_server(self):
        """Verify 'doorstop add' can be called when the server is disabled."""
        self.assertIs(None, main(['add', 'TUT', '--no-server']))

    # TODO: add a patch to bypass server call
    def test_add_custom_server(self):
        """Verify 'doorstop add' can be called without a server."""
        self.assertIs(None, main(['add', 'TUT', '--server', 'example.com']))

    def test_add_force(self):
        """Verify 'doorstop add' can be called with a missing server."""
        self.assertIs(None, main(['add', 'TUT', '--force']))


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestRemove(unittest.TestCase):

    """Integration tests for the 'doorstop remove' command."""

    ITEM = os.path.join(TUTORIAL, 'TUT003.yml')

    def setUp(self):
        self.backup = common.read_text(self.ITEM)

    def tearDown(self):
        common.write_text(self.backup, self.ITEM)

    def test_remove(self):
        """Verify 'doorstop remove' can be called."""
        self.assertIs(None, main(['remove', 'tut3']))
        self.assertFalse(os.path.exists(self.ITEM))

    def test_remove_error(self):
        """Verify 'doorstop remove' returns an error on unknown item UIDs."""
        self.assertRaises(SystemExit, main, ['remove', 'tut9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestReorder(unittest.TestCase):

    """Integration tests for the 'doorstop reorder' command."""

    @classmethod
    def setUpClass(cls):
        cls.prefix = 'tut'
        cls.path = os.path.join('docs', 'reqs', 'tutorial', 'index.yml')

    def tearDown(self):
        common.delete(self.path)

    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(return_value='yes'))
    def test_reorder_document_yes(self, mock_launch):
        """Verify 'doorstop reorder' can be called with a document (yes)."""
        self.assertIs(None, main(['reorder', self.prefix]))
        mock_launch.assert_called_once_with(self.path, tool=None)
        self.assertFalse(os.path.exists(self.path))

    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(return_value='no'))
    def test_reorder_document_no(self, mock_launch):
        """Verify 'doorstop reorder' can be called with a document (no)."""
        self.assertIs(None, main(['reorder', self.prefix]))
        mock_launch.assert_called_once_with(self.path, tool=None)
        self.assertFalse(os.path.exists(self.path))

    @patch('doorstop.core.editor.launch')
    def test_reorder_document_auto(self, mock_launch):
        """Verify 'doorstop reorder' can be called with a document (auto)."""
        self.assertIs(None, main(['reorder', self.prefix, '--auto']))
        mock_launch.assert_never_called()

    @patch('doorstop.core.document.Document._reorder_automatic')
    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(return_value='no'))
    def test_reorder_document_manual(self, mock_launch, mock_reorder_auto):
        """Verify 'doorstop reorder' can be called with a document (manual)."""
        self.assertIs(None, main(['reorder', self.prefix, '--manual']))
        mock_launch.assert_called_once_with(self.path, tool=None)
        mock_reorder_auto.assert_never_called()
        self.assertFalse(os.path.exists(self.path))

    @patch('builtins.input', Mock(return_value='yes'))
    def test_reorder_document_error(self):
        """Verify 'doorstop reorder' can handle invalid YAML."""

        def bad_yaml_edit(path, **_):
            """Simulate adding invalid YAML to the index."""
            common.write_text("%bad", path)

        with patch('doorstop.core.editor.launch', bad_yaml_edit):
            self.assertRaises(SystemExit, main, ['reorder', self.prefix])

        self.assertTrue(os.path.exists(self.path))

    def test_reorder_document_unknown(self):
        """Verify 'doorstop reorder' returns an error on an unknown prefix."""
        self.assertRaises(SystemExit, main, ['reorder', 'FAKE'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestEdit(unittest.TestCase):

    """Integration tests for the 'doorstop edit' command."""

    @patch('doorstop.core.editor.launch')
    def test_edit_item(self, mock_launch):
        """Verify 'doorstop edit' can be called with an item."""
        self.assertIs(None, main(['edit', 'tut2']))
        path = os.path.join(TUTORIAL, 'TUT002.yml')
        mock_launch.assert_called_once_with(os.path.normpath(path), tool=None)

    def test_edit_item_unknown(self):
        """Verify 'doorstop edit' returns an error on an unknown item."""
        self.assertRaises(SystemExit, main, ['edit', '--item', 'FAKE001'])

    @patch('time.time', Mock(return_value=123))
    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(return_value='yes'))
    def test_edit_document_yes_yes(self, mock_launch):
        """Verify 'doorstop edit' can be called with a document (yes, yes)."""
        path = "TUT-123.yml"
        self.assertIs(None, main(['edit', 'tut']))
        mock_launch.assert_called_once_with(os.path.normpath(path), tool=None)

    @patch('time.time', Mock(return_value=456))
    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(return_value='no'))
    def test_edit_document_no_no(self, mock_launch):
        """Verify 'doorstop edit' can be called with a document (no, no)."""
        path = "TUT-456.yml"
        self.assertIs(None, main(['edit', 'tut']))
        common.delete(path)
        mock_launch.assert_called_once_with(os.path.normpath(path), tool=None)

    @patch('time.time', Mock(return_value=789))
    @patch('doorstop.core.editor.launch')
    @patch('builtins.input', Mock(side_effect=['no', 'yes']))
    def test_edit_document_no_yes(self, mock_launch):
        """Verify 'doorstop edit' can be called with a document (no, yes)."""
        path = "TUT-789.yml"
        self.assertIs(None, main(['edit', 'tut']))
        mock_launch.assert_called_once_with(os.path.normpath(path), tool=None)

    def test_edit_document_unknown(self):
        """Verify 'doorstop edit' returns an error on an unknown document."""
        self.assertRaises(SystemExit, main, ['edit', '--document', 'FAKE'])

    def test_edit_error(self):
        """Verify 'doorstop edit' returns an error with an unknown UID."""
        self.assertRaises(SystemExit, main, ['edit', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestLink(unittest.TestCase):

    """Integration tests for the 'doorstop link' command."""

    ITEM = os.path.join(TUTORIAL, 'TUT003.yml')

    def setUp(self):
        self.backup = common.read_text(self.ITEM)

    def tearDown(self):
        common.write_text(self.backup, self.ITEM)

    def test_link(self):
        """Verify 'doorstop link' can be called."""
        self.assertIs(None, main(['link', 'tut3', 'req2']))

    def test_link_unknown_child(self):
        """Verify 'doorstop link' returns an error with an unknown child."""
        self.assertRaises(SystemExit, main, ['link', 'unknown3', 'req2'])
        self.assertRaises(SystemExit, main, ['link', 'tut9999', 'req2'])

    def test_link_unknown_parent(self):
        """Verify 'doorstop link' returns an error with an unknown parent."""
        self.assertRaises(SystemExit, main, ['link', 'tut3', 'unknown2'])
        self.assertRaises(SystemExit, main, ['link', 'tut3', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestUnlink(unittest.TestCase):

    """Integration tests for the 'doorstop unlink' command."""

    ITEM = os.path.join(TUTORIAL, 'TUT003.yml')

    def setUp(self):
        self.backup = common.read_text(self.ITEM)
        main(['link', 'tut3', 'req2'])  # create a temporary link

    def tearDown(self):
        common.write_text(self.backup, self.ITEM)

    def test_unlink(self):
        """Verify 'doorstop unlink' can be called."""
        self.assertIs(None, main(['unlink', 'tut3', 'req2']))

    def test_unlink_unknown_child(self):
        """Verify 'doorstop unlink' returns an error with an unknown child."""
        self.assertRaises(SystemExit, main, ['unlink', 'unknown3', 'req2'])
        self.assertRaises(SystemExit, main, ['link', 'tut9999', 'req2'])

    def test_unlink_unknown_parent(self):
        """Verify 'doorstop unlink' returns an error with an unknown parent."""
        self.assertRaises(SystemExit, main, ['unlink', 'tut3', 'unknown2'])
        self.assertRaises(SystemExit, main, ['unlink', 'tut3', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestClear(unittest.TestCase):

    """Integration tests for the 'doorstop clear' command."""

    @patch('doorstop.core.item.Item.clear')
    def test_clear_item(self, mock_clear):
        """Verify 'doorstop clear' can be called with an item."""
        self.assertIs(None, main(['clear', 'tut2']))
        self.assertEqual(1, mock_clear.call_count)

    def test_clear_item_unknown(self):
        """Verify 'doorstop clear' returns an error on an unknown item."""
        self.assertRaises(SystemExit, main, ['clear', '--item', 'FAKE001'])

    @patch('doorstop.core.item.Item.clear')
    def test_clear_document(self, mock_clear):
        """Verify 'doorstop clear' can be called with a document"""
        self.assertIs(None, main(['clear', 'tut']))
        self.assertEqual(14, mock_clear.call_count)

    def test_clear_document_unknown(self):
        """Verify 'doorstop clear' returns an error on an unknown document."""
        self.assertRaises(SystemExit, main, ['clear', '--document', 'FAKE'])

    @patch('doorstop.core.item.Item.clear')
    def test_clear_tree(self, mock_clear):
        """Verify 'doorstop clear' can be called with a tree"""
        self.assertIs(None, main(['clear', 'all']))
        self.assertEqual(41, mock_clear.call_count)

    def test_clear_tree_item(self):
        """Verify 'doorstop clear' returns an error with tree and item."""
        self.assertRaises(SystemExit, main, ['clear', '--item', 'all'])

    def test_clear_tree_document(self):
        """Verify 'doorstop clear' returns an error with tree and document."""
        self.assertRaises(SystemExit, main, ['clear', '--document', 'all'])

    def test_clear_error(self):
        """Verify 'doorstop clear' returns an error with an unknown UID."""
        self.assertRaises(SystemExit, main, ['clear', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestReview(unittest.TestCase):

    """Integration tests for the 'doorstop review' command."""

    @patch('doorstop.core.item.Item.review')
    def test_review_item(self, mock_review):
        """Verify 'doorstop review' can be called with an item."""
        self.assertIs(None, main(['review', 'tut2']))
        self.assertEqual(1, mock_review.call_count)

    def test_review_item_unknown(self):
        """Verify 'doorstop review' returns an error on an unknown item."""
        self.assertRaises(SystemExit, main, ['review', '--item', 'FAKE001'])

    @patch('doorstop.core.item.Item.review')
    def test_review_document(self, mock_review):
        """Verify 'doorstop review' can be called with a document"""
        self.assertIs(None, main(['review', 'tut']))
        self.assertEqual(14, mock_review.call_count)

    def test_review_document_unknown(self):
        """Verify 'doorstop review' returns an error on an unknown document."""
        self.assertRaises(SystemExit, main, ['review', '--document', 'FAKE'])

    @patch('doorstop.core.item.Item.review')
    def test_review_tree(self, mock_review):
        """Verify 'doorstop review' can be called with a tree"""
        self.assertIs(None, main(['review', 'all']))
        self.assertEqual(41, mock_review.call_count)

    def test_review_tree_item(self):
        """Verify 'doorstop review' returns an error with tree and item."""
        self.assertRaises(SystemExit, main, ['review', '--item', 'all'])

    def test_review_tree_document(self):
        """Verify 'doorstop review' returns an error with tree and document."""
        self.assertRaises(SystemExit, main, ['review', '--document', 'all'])

    def test_review_error(self):
        """Verify 'doorstop review' returns an error with an unknown UID."""
        self.assertRaises(SystemExit, main, ['review', 'req9999'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestImport(unittest.TestCase):

    """Integration tests for the 'doorstop import' command."""

    def tearDown(self):
        common.delete(os.path.join(ROOT, 'tmp'))
        common.delete(os.path.join(REQS, 'REQ099.yml'))

    def test_import_document(self):
        """Verify 'doorstop import' can import a document."""
        self.assertRaises(SystemExit,
                          main, ['import', '--document', 'TMP', 'tmp'])

    def test_import_document_with_parent(self):
        """Verify 'doorstop import' can import a document with a parent."""
        self.assertIs(None, main(['import', '--document', 'TMP', 'tmp',
                                  '--parent', 'REQ']))

    def test_import_item(self):
        """Verify 'doorstop import' can import an item.."""
        self.assertIs(None, main(['import', '--item', 'REQ', 'REQ099']))

    def test_import_item_with_attrs(self):
        """Verify 'doorstop import' can import an item with attributes."""
        self.assertIs(None, main(['import', '--item', 'REQ', 'REQ099',
                                  '--attrs', "{'text': 'The item text.'}"]))

    def test_import_error(self):
        """Verify 'doorstop import' requires a document or item."""
        self.assertRaises(SystemExit, main, ['import', '--attr', "{}"])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestImportFile(MockTestCase):

    """Integration tests for the 'doorstop import' command."""

    def test_import_file_missing_prefix(self):
        """Verify 'doorstop import' returns an error with a missing prefix."""
        path = os.path.join(FILES, 'exported.xlsx')
        self.assertRaises(SystemExit, main, ['import', path])

    def test_import_file_extra_flags(self):
        """Verify 'doorstop import' returns an error with extra flags."""
        path = os.path.join(FILES, 'exported.xlsx')
        self.assertRaises(SystemExit,
                          main, ['import', path, 'PREFIX', '-d', '_', '_'])
        self.assertRaises(SystemExit,
                          main, ['import', path, 'PREFIX', '-i', '_', '_'])

    def test_import_file_to_document_unknown(self):
        """Verify 'doorstop import' returns an error for unknown documents."""
        path = os.path.join(FILES, 'exported.xlsx')
        self.assertRaises(SystemExit, main, ['import', path, 'PREFIX'])

    def test_import_file_with_map(self):
        """Verify 'doorstop import' can import a file using a custom map."""
        path = os.path.join(FILES, 'exported-map.csv')
        dirpath = os.path.join(self.temp, 'imported', 'prefix')
        main(['create', 'PREFIX', dirpath])
        # Act
        self.assertIs(None, main(['import', path, 'PREFIX',
                                  '--map', "{'mylevel': 'level'}"]))
        # Assert
        path = os.path.join(dirpath, 'REQ001.yml')
        self.assertTrue(os.path.isfile(path))
        text = common.read_text(path)
        self.assertIn('\nlevel: 1.2.3', text)

    def test_import_file_with_map_invalid(self):
        """Verify 'doorstop import' returns an error with an invalid map."""
        path = os.path.join(FILES, 'exported.csv')
        self.assertRaises(SystemExit,
                          main, ['import', path, 'PREFIX', '--map', "{'my"])

    def test_import_csv_to_document_existing(self):
        """Verify 'doorstop import' can import CSV to an existing document."""
        path = os.path.join(FILES, 'exported.csv')
        dirpath = os.path.join(self.temp, 'imported', 'prefix')
        main(['create', 'PREFIX', dirpath])
        # Act
        self.assertIs(None, main(['import', path, 'PREFIX']))
        # Assert
        path = os.path.join(dirpath, 'REQ001.yml')
        self.assertTrue(os.path.isfile(path))

    def test_import_tsv_to_document_existing(self):
        """Verify 'doorstop import' can import TSV to an existing document."""
        path = os.path.join(FILES, 'exported.tsv')
        dirpath = os.path.join(self.temp, 'imported', 'prefix')
        main(['create', 'PREFIX', dirpath])
        # Act
        self.assertIs(None, main(['import', path, 'PREFIX']))
        # Assert
        path = os.path.join(dirpath, 'REQ001.yml')
        self.assertTrue(os.path.isfile(path))

    def test_import_xlsx_to_document_existing(self):
        """Verify 'doorstop import' can import XLSX to an existing document."""
        path = os.path.join(FILES, 'exported.xlsx')
        dirpath = os.path.join(self.temp, 'imported', 'prefix')
        main(['create', 'PREFIX', dirpath])
        # Act
        self.assertIs(None, main(['import', path, 'PREFIX']))
        # Assert
        path = os.path.join(dirpath, 'REQ001.yml')
        self.assertTrue(os.path.isfile(path))


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestExport(TempTestCase):

    """Integration tests for the 'doorstop export' command."""

    def test_export_document_error_unknown(self):
        """Verify 'doorstop export' returns an error for an unknown format."""
        self.assertRaises(SystemExit, main, ['export', 'req', 'req.fake'])

    def test_export_document_error_directory(self):
        """Verify 'doorstop publish' returns an error with a directory."""
        self.assertRaises(SystemExit, main, ['export', 'req', self.temp])

    def test_export_document_error_no_extension(self):
        """Verify 'doorstop publish' returns an error with no extension."""
        path = os.path.join(self.temp, 'req')
        self.assertRaises(SystemExit, main, ['export', 'req', path])

    def test_export_document_stdout(self):
        """Verify 'doorstop export' can create output."""
        self.assertIs(None, main(['export', 'tut']))

    def test_export_document_stdout_width(self):
        """Verify 'doorstop export' can create output."""
        self.assertIs(None, main(['export', 'tut', '--width', '72']))

    def test_export_document_yaml(self):
        """Verify 'doorstop export' can create a YAML file."""
        path = os.path.join(self.temp, 'tut.yml')
        self.assertIs(None, main(['export', 'tut', path]))
        self.assertTrue(os.path.isfile(path))

    def test_export_document_xlsx(self):
        """Verify 'doorstop export' can create an XLSX file."""
        path = os.path.join(self.temp, 'tut.xlsx')
        self.assertIs(None, main(['export', 'tut', path]))
        self.assertTrue(os.path.isfile(path))

    def test_export_tree_xlsx(self):
        """Verify 'doorstop export' can create an XLSX directory."""
        path = os.path.join(self.temp, 'all')
        self.assertIs(None, main(['export', 'all', path, '--xlsx']))
        self.assertTrue(os.path.isdir(path))

    def test_export_tree_no_path(self):
        """Verify 'doorstop export' returns an error with no path."""
        self.assertRaises(SystemExit, main, ['export', 'all'])


@unittest.skipUnless(os.getenv(ENV), REASON)
class TestPublish(TempTestCase):

    """Integration tests for the 'doorstop publish' command."""

    def setUp(self):
        super().setUp()
        self.backup = (settings.PUBLISH_CHILD_LINKS,
                       settings.PUBLISH_BODY_LEVELS)

    def tearDown(self):
        super().tearDown()
        (settings.PUBLISH_CHILD_LINKS,
         settings.PUBLISH_BODY_LEVELS) = self.backup

    def test_publish_unknown(self):
        """Verify 'doorstop publish' returns an error for an unknown format."""
        self.assertRaises(SystemExit, main, ['publish', 'req', 'req.fake'])

    def test_publish_document(self):
        """Verify 'doorstop publish' can create output."""
        self.assertIs(None, main(['publish', 'tut']))
        self.assertTrue(settings.PUBLISH_CHILD_LINKS)

    def test_publish_document_with_child_links(self):
        """Verify 'doorstop publish' can create output with child links."""
        self.assertIs(None, main(['publish', 'tut']))
        self.assertTrue(settings.PUBLISH_CHILD_LINKS)

    def test_publish_document_without_child_links(self):
        """Verify 'doorstop publish' can create output without child links."""
        self.assertIs(None, main(['publish', 'tut', '--no-child-links']))
        self.assertFalse(settings.PUBLISH_CHILD_LINKS)

    def test_publish_document_without_body_levels(self):
        """Verify 'doorstop publish' can create output without body levels."""
        self.assertIs(None, main(['publish', 'tut', '--no-body-levels']))
        self.assertFalse(settings.PUBLISH_BODY_LEVELS)

    def test_publish_document_error_empty(self):
        """Verify 'doorstop publish' returns an error in an empty folder."""
        os.chdir(self.temp)
        self.assertRaises(SystemExit, main, ['publish', 'req'])

    def test_publish_document_error_directory(self):
        """Verify 'doorstop publish' returns an error with a directory."""
        self.assertRaises(SystemExit, main, ['publish', 'req', self.temp])

    def test_publish_document_error_no_extension(self):
        """Verify 'doorstop publish' returns an error with no extension."""
        path = os.path.join(self.temp, 'req')
        self.assertRaises(SystemExit, main, ['publish', 'req', path])

    def test_publish_document_text(self):
        """Verify 'doorstop publish' can create text output."""
        self.assertIs(None, main(['publish', 'tut', '--width', '75']))

    def test_publish_document_text_file(self):
        """Verify 'doorstop publish' can create a text file."""
        path = os.path.join(self.temp, 'req.txt')
        self.assertIs(None, main(['publish', 'req', path]))
        self.assertTrue(os.path.isfile(path))

    def test_publish_document_markdown(self):
        """Verify 'doorstop publish' can create Markdown output."""
        self.assertIs(None, main(['publish', 'req', '--markdown']))

    def test_publish_document_markdown_file(self):
        """Verify 'doorstop publish' can create a Markdown file."""
        path = os.path.join(self.temp, 'req.md')
        self.assertIs(None, main(['publish', 'req', path]))
        self.assertTrue(os.path.isfile(path))

    def test_publish_document_html(self):
        """Verify 'doorstop publish' can create HTML output."""
        self.assertIs(None, main(['publish', 'hlt', '--html']))

    def test_publish_document_html_file(self):
        """Verify 'doorstop publish' can create an HTML file."""
        path = os.path.join(self.temp, 'req.html')
        self.assertIs(None, main(['publish', 'req', path]))
        self.assertTrue(os.path.isfile(path))

    def test_publish_tree_html(self):
        """Verify 'doorstop publish' can create an HTML directory."""
        path = os.path.join(self.temp, 'all')
        self.assertIs(None, main(['publish', 'all', path]))
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(os.path.isfile(os.path.join(path, 'index.html')))

    def test_publish_tree_text(self):
        """Verify 'doorstop publish' can create a text directory."""
        path = os.path.join(self.temp, 'all')
        self.assertIs(None, main(['publish', 'all', path, '--text']))
        self.assertTrue(os.path.isdir(path))
        self.assertFalse(os.path.isfile(os.path.join(path, 'index.html')))

    def test_publish_tree_no_path(self):
        """Verify 'doorstop publish' returns an error with no path."""
        self.assertRaises(SystemExit, main, ['publish', 'all'])


@patch('doorstop.cli.commands.run', Mock(return_value=True))
class TestLogging(unittest.TestCase):

    """Integration tests for the Doorstop CLI logging."""

    def test_verbose_0(self):
        """Verify verbose level 0 can be set."""
        self.assertIs(None, main([]))

    def test_verbose_1(self):
        """Verify verbose level 1 can be set."""
        self.assertIs(None, main(['-v']))

    def test_verbose_2(self):
        """Verify verbose level 2 can be set."""
        self.assertIs(None, main(['-vv']))

    def test_verbose_3(self):
        """Verify verbose level 3 can be set."""
        self.assertIs(None, main(['-vvv']))

    def test_verbose_4(self):
        """Verify verbose level 4 can be set."""
        self.assertIs(None, main(['-vvvv']))

    def test_verbose_5(self):
        """Verify verbose level 5 cannot be set."""
        self.assertIs(None, main(['-vvvvv']))
        self.assertEqual(4, common.verbosity)

    def test_verbose_quiet(self):
        """Verify verbose level -1 can be set."""
        self.assertIs(None, main(['-q']))
        self.assertEqual(-1, common.verbosity)
