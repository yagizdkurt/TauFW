"""Mocked transports and ROOT lifecycles; never contact storage or import PyROOT."""

import gzip
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.FIO import FileIO
from TauFW.Utilities.FIO._internal import remote, root


class RemoteTests(unittest.TestCase):
    def test_commands_use_argument_lists_capture_and_timeout(self):
        result = subprocess.CompletedProcess(["xrdcp"], 0, "", "")
        source = "root://storage.example//store/space name.root?token=opaque"
        with mock.patch.object(remote.subprocess, "run", return_value=result) as command:
            remote.copy_file(source, "local name.root", False, 12)
        arguments = command.call_args.args[0]
        self.assertEqual(arguments, ["xrdcp", "--nopbar", source, str(Path("local name.root").absolute())])
        self.assertFalse(command.call_args.kwargs["shell"])
        self.assertEqual(command.call_args.kwargs["timeout"], 12)
        self.assertEqual(command.call_args.kwargs["stderr"], subprocess.PIPE)

    def test_exists_distinguishes_absence_and_transport_failures(self):
        url = "root://storage.example//store/file.root"
        cases = [(53, "", "[ERROR] [3011] No such file or directory", False),
                 (0, "Flags: 16 (IsReadable)\n", "", True),
                 (53, "", "[ERROR] [3010] Permission denied", None)]
        for status, output, errors, expected in cases:
            with self.subTest(status=status, errors=errors):
                result = subprocess.CompletedProcess(["xrdfs"], status, output, errors)
                with mock.patch.object(remote.subprocess, "run", return_value=result):
                    if expected is None:
                        with self.assertRaises(subprocess.CalledProcessError) as failure:
                            FileIO().exists(url)
                        self.assertIn("Permission denied", failure.exception.stderr)
                    else:
                        self.assertEqual(FileIO().exists(url), expected)
        with mock.patch.object(remote.subprocess, "run", side_effect=subprocess.TimeoutExpired("xrdfs", 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                FileIO(timeout=1).exists(url)

    def test_gfal_stat_and_srm_listing_preserve_query_parameters(self):
        url = "srm://storage.example/srm/managerv2?SFN=/pnfs/user&token=opaque"
        results = [subprocess.CompletedProcess([], 0, "Access: (0755/drwxr-xr-x)\n", ""),
                   subprocess.CompletedProcess([], 0, "file name.json.gz\n", "")]
        with mock.patch.object(remote.subprocess, "run", side_effect=results) as command:
            entries = FileIO().list_directory(url)
        self.assertEqual(entries, ["srm://storage.example/srm/managerv2?SFN=/pnfs/user/file%20name.json.gz&token=opaque"])
        self.assertEqual(command.call_args_list[0].args[0], ["gfal-stat", url])
        self.assertEqual(command.call_args_list[1].args[0], ["gfal-ls", url])

    def test_missing_credentials_are_not_reported_as_a_missing_remote_file(self):
        url = "gsiftp://storage.example/path/file"
        absent = subprocess.CompletedProcess([], 2, "", "No such file or directory")
        credentials = subprocess.CompletedProcess([], 2, "", "Could not load certificate: No such file or directory")
        with mock.patch.object(remote.subprocess, "run", return_value=absent):
            self.assertFalse(FileIO().exists(url))
        with mock.patch.object(remote.subprocess, "run", return_value=credentials):
            with self.assertRaises(subprocess.CalledProcessError):
                FileIO().exists(url)

    def test_remote_listing_rejects_outside_paths_and_preserves_root_slashes(self):
        url = "root://storage.example//store/user"
        with mock.patch.object(remote, "run_command", return_value=SimpleNamespace(stdout="/store/user/file.root\n")):
            self.assertEqual(remote.list_directory(url, 5), [url + "/file.root"])
        with mock.patch.object(remote, "run_command", return_value=SimpleNamespace(stdout="/store/other/file.root\n")):
            with self.assertRaises(ValueError):
                remote.list_directory(url, 5)

    def test_failed_move_never_deletes_source_and_same_file_is_rejected(self):
        source = "root://one.example//store/file.root"
        destination = "root://two.example//store/file.root"
        failed = subprocess.CompletedProcess(["xrdcp"], 53, "", "copy failed")
        with mock.patch.object(remote, "kind", side_effect=["file", None]), \
             mock.patch.object(remote.subprocess, "run", return_value=failed), \
             mock.patch.object(remote, "remove_file") as remove:
            with self.assertRaises(subprocess.CalledProcessError):
                FileIO().move_file(source, destination)
            remove.assert_not_called()
        with mock.patch.object(remote, "kind", return_value="file"), \
             mock.patch.object(remote, "copy_file") as copy:
            with self.assertRaises(ValueError):
                FileIO().move_file(source, "root://one.example:1094/store/file.root", overwrite=True)
            copy.assert_not_called()

    def test_cross_protocol_copy_uses_gfal_and_file_uris(self):
        with mock.patch.object(remote, "run_command") as command:
            remote.copy_file("root://one.example//store/file", "gsiftp://two.example/path/file", True, 5)
            self.assertEqual(command.call_args.args[0][:2], ["gfal-copy", "--force"])
            remote.copy_file("local file", "srm://two.example/path/file", False, 5)
            self.assertTrue(command.call_args.args[0][1].startswith("file:///"))
            self.assertIn("local%20file", command.call_args.args[0][1])

    def test_remote_json_staging_upload_and_cleanup(self):
        url = "root://storage.example//store/config.json.gz"
        uploads = []
        with tempfile.TemporaryDirectory() as directory:
            files = FileIO(temporary_directory=directory)

            def transfer(source, destination, overwrite, timeout):
                if source == url:
                    Path(destination).write_bytes(gzip.compress(b'{"count": 2}'))
                else:
                    uploads.append((destination, gzip.decompress(Path(source).read_bytes()), overwrite))

            with mock.patch.object(remote, "copy_file", side_effect=transfer), \
                 mock.patch.object(remote, "kind", return_value=None):
                self.assertEqual(files.read_json(url), {"count": 2})
                files.write_json(url, {"count": 3})
                self.assertEqual(uploads, [(url, b'{\n  "count": 3\n}\n', False)])
                with self.assertRaises(NotImplementedError):
                    files.append_text(url, "more")
            with mock.patch.object(remote, "copy_file", side_effect=RuntimeError("transfer failed")):
                with self.assertRaisesRegex(RuntimeError, "transfer failed"):
                    files.read_json(url)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_remote_filenames_cannot_escape_the_staging_directory(self):
        url = r"root://storage.example//store/..\..\outside.json"
        with tempfile.TemporaryDirectory() as directory:
            files = FileIO(temporary_directory=directory)

            def download(source, destination, overwrite, timeout):
                staged = Path(destination)
                self.assertEqual(staged.parent.parent, Path(directory))
                self.assertEqual(staged.name, "content")
                staged.write_bytes(b'{"valid": true}')

            with mock.patch.object(remote, "copy_file", side_effect=download):
                self.assertEqual(files.read_json(url), {"valid": True})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_recursive_directory_removal_is_explicit(self):
        url = "root://storage.example//store/user"
        with mock.patch.object(remote, "list_directory", return_value=[url + "/file"]), \
             mock.patch.object(remote, "run_command") as command:
            with self.assertRaises(OSError):
                remote.remove_directory(url, False, 5)
            command.assert_not_called()
        with mock.patch.object(remote, "list_directory", side_effect=[[url + "/file"], []]), \
             mock.patch.object(remote, "kind", return_value="file"), \
             mock.patch.object(remote, "run_command") as command:
            remote.remove_directory(url, True, 5)
            self.assertEqual([call.args[0][2] for call in command.call_args_list], ["rm", "rmdir"])

    def test_srm_recursive_removal_extends_sfn_before_other_query_parameters(self):
        url = "srm://storage.example/srm?SFN=/pnfs/user&token=opaque"
        child = "srm://storage.example/srm?SFN=/pnfs/user/file&token=opaque"
        with mock.patch.object(remote, "list_directory", return_value=[child]), \
             mock.patch.object(remote, "kind", return_value="file"), \
             mock.patch.object(remote, "run_command") as command:
            remote.remove_directory(url, True, 5)
        self.assertEqual([call.args[0] for call in command.call_args_list],
                         [["gfal-rm", child], ["gfal-rm", "-r", url]])


class RootTests(unittest.TestCase):
    def setUp(self):
        self.handle = mock.Mock()
        self.handle.IsZombie.return_value = False
        self.module = SimpleNamespace(TFile=SimpleNamespace(Open=mock.Mock(return_value=self.handle)))
        patcher = mock.patch.object(root, "root_module", return_value=self.module)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_root_closes_on_caller_failure_and_zombie_open(self):
        with self.assertRaisesRegex(RuntimeError, "caller failed"):
            with FileIO().open_root_file("local.root"):
                raise RuntimeError("caller failed")
        self.handle.Close.assert_called_once()
        self.handle.reset_mock()
        self.handle.IsZombie.return_value = True
        with self.assertRaises(OSError):
            with FileIO().open_root_file("bad.root"):
                self.fail("Zombie files must not be yielded")
        self.handle.Close.assert_called_once()

    def test_histogram_is_detached_before_file_closes(self):
        histogram, detached = mock.Mock(), mock.Mock()
        histogram.InheritsFrom.return_value = True
        histogram.Clone.return_value = detached
        self.handle.Get.return_value = histogram
        self.assertIs(FileIO().read_root_histogram("local.root", "cutflow"), detached)
        detached.SetDirectory.assert_called_once_with(0)
        histogram.SetDirectory.assert_not_called()
        self.handle.Close.assert_called_once()
        self.handle.reset_mock()
        self.handle.Get.return_value = None
        with self.assertRaises(KeyError):
            FileIO().read_root_histogram("local.root", "missing")
        self.handle.Close.assert_called_once()

    def test_xrootd_reads_stream_without_file_transfer(self):
        url = "root://storage.example//store/input.root"
        with mock.patch.object(remote, "copy_file") as transfer:
            with FileIO().open_root_file(url) as handle:
                self.assertIs(handle, self.handle)
            self.module.TFile.Open.assert_called_once_with(url, "READ")
            transfer.assert_not_called()

    def test_remote_root_upload_follows_close_and_failed_caller_never_uploads(self):
        url = "gsiftp://storage.example/path/output.root"
        uploads = []
        with tempfile.TemporaryDirectory() as directory:
            files = FileIO(temporary_directory=directory)

            def create_file(location, mode):
                Path(location).write_bytes(b"ROOT output")
                return self.handle

            def upload(source, destination, overwrite, timeout):
                self.assertTrue(self.handle.Close.called)
                uploads.append((destination, Path(source).read_bytes()))

            self.module.TFile.Open.side_effect = create_file
            with mock.patch.object(remote, "kind", return_value=None), \
                 mock.patch.object(remote, "copy_file", side_effect=upload):
                with files.open_root_file(url, "RECREATE"):
                    pass
                self.assertEqual(uploads, [(url, b"ROOT output")])
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    with files.open_root_file(url, "RECREATE"):
                        raise RuntimeError("failed")
                self.assertEqual(len(uploads), 1)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_object_write_failure_closes_file_and_names_are_validated_first(self):
        self.handle.WriteObject.return_value = 0
        with self.assertRaises(OSError):
            FileIO().write_root_objects("local.root", {"hist": object()})
        self.handle.Close.assert_called_once()
        self.module.TFile.Open.reset_mock()
        with self.assertRaises(ValueError):
            FileIO().write_root_objects("local.root", {"../hist": object()})
        self.module.TFile.Open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
