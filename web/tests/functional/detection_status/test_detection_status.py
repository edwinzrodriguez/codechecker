#
# -------------------------------------------------------------------------
#
#  Part of the CodeChecker project, under the Apache License v2.0 with
#  LLVM Exceptions. See LICENSE for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# -------------------------------------------------------------------------
""" detection_status function test. """


import json
import os
import shutil
import unittest

from codechecker_api.codeCheckerDBAccess_v6.ttypes import DetectionStatus, \
    Encoding, ReportFilter

from libtest import codechecker
from libtest import env


class TestDetectionStatus(unittest.TestCase):

    def setup_class(self):
        """Setup the environment for testing detection_status."""

        global TEST_WORKSPACE
        TEST_WORKSPACE = env.get_workspace('detection_status')

        # Set the TEST_WORKSPACE used by the tests.
        os.environ['TEST_WORKSPACE'] = TEST_WORKSPACE

        # Configuration options.
        codechecker_cfg = {
            'suppress_file': None,
            'skip_list_file': None,
            'check_env': env.test_env(TEST_WORKSPACE),
            'workspace': TEST_WORKSPACE,
            'checkers': [],
            'reportdir': os.path.join(TEST_WORKSPACE, 'reports'),
            'test_project': 'hello',
            'analyzers': ['clangsa', 'clang-tidy']
        }

        # Start or connect to the running CodeChecker server and get connection
        # details.
        print("This test uses a CodeChecker server... connecting...")
        server_access = codechecker.start_or_get_server()
        server_access['viewer_product'] = 'detection_status'
        codechecker.add_test_package_product(server_access, TEST_WORKSPACE)

        # Extend the checker configuration with the server access.
        codechecker_cfg.update(server_access)

        # Export the test configuration to the workspace.
        env.export_test_cfg(TEST_WORKSPACE,
                            {'codechecker_cfg': codechecker_cfg})

    def teardown_class(self):
        """Clean up after the test."""

        # TODO: If environment variable is set keep the workspace
        # and print out the path.
        global TEST_WORKSPACE

        check_env = env.import_test_cfg(TEST_WORKSPACE)[
            'codechecker_cfg']['check_env']
        codechecker.remove_test_package_product(TEST_WORKSPACE, check_env)

        print("Removing: " + TEST_WORKSPACE)
        shutil.rmtree(TEST_WORKSPACE, ignore_errors=True)

    def setup_method(self, method):
        # TEST_WORKSPACE is automatically set by test package __init__.py .
        self.test_workspace = os.environ['TEST_WORKSPACE']

        test_class = self.__class__.__name__
        print('Running ' + test_class + ' tests in ' + self.test_workspace)

        self._codechecker_cfg = env.import_codechecker_cfg(self.test_workspace)

        # Get the CodeChecker cmd if needed for the tests.
        self._codechecker_cmd = env.codechecker_cmd()
        self._test_dir = os.path.join(self.test_workspace, 'test_files')
        self._run_name = 'hello'

        try:
            os.makedirs(self._test_dir)
        except os.error:
            # Directory already exists.
            pass

        # Setup a viewer client to test viewer API calls.
        self._cc_client = env.setup_viewer_client(self.test_workspace)
        self.assertIsNotNone(self._cc_client)

        # Remove all runs before the test cases.
        runs = self._cc_client.getRunData(None, None, 0, None)
        if runs:
            run_id = max(map(lambda run: run.runId, runs))
            self._cc_client.removeRun(run_id, None)

        self.clang_tidy_cfg = os.path.join(self._test_dir, '.clang-tidy')

        # Change working dir to testfile dir so CodeChecker can be run easily.
        self.__old_pwd = os.getcwd()
        os.chdir(self._test_dir)

        self._source_file = "main.cpp"

        # Init project dir.
        makefile = "all:\n\t$(CXX) -c main.cpp -Wno-division-by-zero " \
                   "-Wno-all -Wno-extra -o /dev/null\n"
        project_info = {
            "name": "hello",
            "clean_cmd": "",
            "build_cmd": "make"
        }

        with open(os.path.join(self._test_dir, 'Makefile'), 'w',
                  encoding="utf-8", errors="ignore") as f:
            f.write(makefile)
        with open(os.path.join(self._test_dir, 'project_info.json'), 'w',
                  encoding="utf-8", errors="ignore") as f:
            json.dump(project_info, f)

        self.sources = ["""
int main()
{
  int i = 1 / 0;

  sizeof(42);
  sizeof(42);
  sizeof(42);
}""", """
int main()
{
  int i = 1 / 0;

  int* p = 0;

  i = *p + 42;

  sizeof(42);
  sizeof(42);
  sizeof(42);
}""", """
int main()
{
  int i = 1 / 2;

  int* p = 0;

  i = *p + 42;

  sizeof(42);
  sizeof(42);
  sizeof(42);
}""", """


int main()
{
  int i = 1 / 0;

  int* p = 0;

  i = *p + 42;

  sizeof(42);
  sizeof(42);
}"""]

    def teardown_method(self, method):
        """Restore environment after tests have ran."""
        os.chdir(self.__old_pwd)

    def _create_source_file(self, version):
        with open(os.path.join(self._test_dir, self._source_file), 'w',
                  encoding="utf-8", errors="ignore") as f:
            f.write(self.sources[version])

    def _check_source_file(self, cfg):
        return codechecker.check_and_store(cfg, self._run_name, self._test_dir)

    def _create_clang_tidy_cfg_file(self, checkers):
        """ This function will create a .clang-tidy config file. """
        with open(self.clang_tidy_cfg, 'w') as f:
            f.write("Checks: '{0}'".format(','.join(checkers)))

    def test_same_file_change(self):
        """
        This tests the change of the detection status of bugs when the file
        content changes.
        """
        # Check the first file version
        self._create_source_file(0)
        self._check_source_file(self._codechecker_cfg)

        runs = self._cc_client.getRunData(None, None, 0, None)
        run_id = max([run.runId for run in runs])

        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)

        self.assertEqual(len(reports), 5)
        self.assertTrue(
            all([r.detectionStatus == DetectionStatus.NEW for r in reports]))

        # Check the second file version
        self._create_source_file(1)
        self._check_source_file(self._codechecker_cfg)
        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)
        for report in reports:
            if report.detectionStatus == DetectionStatus.UNRESOLVED:
                self.assertIn(report.bugHash,
                              ['3cfc9ec31117e138b052abfb064517e5',
                               '209be2f6905590d99853ce01d52a78e0',
                               'e8f47588c8095f02a53e338984ce52ba'])
            elif report.detectionStatus == DetectionStatus.NEW:
                self.assertIn(report.bugHash,
                              ['cbd629ba2ee25c41cdbf5e2e336b1b1c'])
            else:
                self.assertTrue(False)

        # Check the third file version
        self._create_source_file(2)
        self._check_source_file(self._codechecker_cfg)
        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)
        for report in reports:
            if report.detectionStatus == DetectionStatus.RESOLVED:
                self.assertIn(report.bugHash,
                              ['209be2f6905590d99853ce01d52a78e0',
                               'e8f47588c8095f02a53e338984ce52ba'])

                file_content = self._cc_client.getSourceFileData(
                    report.fileId,
                    True,
                    Encoding.DEFAULT).fileContent

                self.assertEqual(
                    file_content,
                    self.sources[1],
                    "Resolved bugs should be shown with the old file content.")

            elif report.detectionStatus == DetectionStatus.NEW:
                self.assertIn(report.bugHash,
                              ['ac147b31a745d91be093bd70bbc5567c'])
            elif report.detectionStatus == DetectionStatus.UNRESOLVED:
                self.assertIn(report.bugHash,
                              ['3cfc9ec31117e138b052abfb064517e5',
                               'cbd629ba2ee25c41cdbf5e2e336b1b1c'])

                file_content = self._cc_client.getSourceFileData(
                    report.fileId,
                    True,
                    Encoding.DEFAULT).fileContent

                self.assertEqual(
                    file_content,
                    self.sources[2],
                    "Unresolved bug should be shown with the new file "
                    "content.")

            else:
                self.assertTrue(False)

        # Check the second file version again
        self._create_source_file(1)
        self._check_source_file(self._codechecker_cfg)
        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)
        for report in reports:
            if report.detectionStatus == DetectionStatus.UNRESOLVED:
                self.assertIn(report.bugHash,
                              ['3cfc9ec31117e138b052abfb064517e5',
                               'cbd629ba2ee25c41cdbf5e2e336b1b1c'])
            elif report.detectionStatus == DetectionStatus.REOPENED:
                self.assertIn(report.bugHash,
                              ['209be2f6905590d99853ce01d52a78e0',
                               'e8f47588c8095f02a53e338984ce52ba'])
            elif report.detectionStatus == DetectionStatus.RESOLVED:
                self.assertIn(report.bugHash,
                              ['ac147b31a745d91be093bd70bbc5567c'])

        # Check the fourth file version
        self._create_source_file(3)
        self._check_source_file(self._codechecker_cfg)
        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)
        for report in reports:
            if report.detectionStatus == DetectionStatus.UNRESOLVED:
                self.assertIn(report.bugHash,
                              ['209be2f6905590d99853ce01d52a78e0',
                               'e8f47588c8095f02a53e338984ce52ba',
                               'cbd629ba2ee25c41cdbf5e2e336b1b1c',
                               '3cfc9ec31117e138b052abfb064517e5'])

                file_content = self._cc_client.getSourceFileData(
                    report.fileId,
                    True,
                    Encoding.DEFAULT).fileContent

                self.assertEqual(
                    file_content,
                    self.sources[3],
                    "Reopened bugs should be shown with the new file content.")

            elif report.detectionStatus == DetectionStatus.RESOLVED:
                self.assertIn(report.bugHash,
                              ['ac147b31a745d91be093bd70bbc5567c'])

    def test_check_without_metadata(self):
        """
        This test checks whether the storage works without a metadata.json.
        """
        self._create_source_file(0)

        codechecker.log_and_analyze(self._codechecker_cfg,
                                    self._test_dir)

        try:
            # Test storage without metadata.json.
            os.remove(os.path.join(self._codechecker_cfg['reportdir'],
                                   'metadata.json'))
        except OSError:
            # metadata.json already removed.
            pass

        codechecker.store(self._codechecker_cfg, 'hello')

        runs = self._cc_client.getRunData(None, None, 0, None)
        run_id = max([run.runId for run in runs])

        reports = self._cc_client.getRunResults([run_id],
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)

        self.assertEqual(len(reports), 5)

    def test_detection_status_off(self):
        """
        This test checks reports which have detection status of 'Off'.
        """
        cfg = dict(self._codechecker_cfg)

        self._create_source_file(0)
        self._check_source_file(cfg)

        self._create_source_file(1)
        self._check_source_file(cfg)

        reports = self._cc_client.getRunResults(None,
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)
        offed_reports = [r for r in reports
                         if r.detectionStatus == DetectionStatus.OFF]
        self.assertEqual(len(offed_reports), 0)

        unavail_reports = [r for r in reports
                           if r.detectionStatus == DetectionStatus.UNAVAILABLE]
        self.assertEqual(len(unavail_reports), 0)

        cfg['checkers'] = ['-d', 'core.DivideZero']

        self._create_source_file(1)
        self._check_source_file(cfg)

        reports = self._cc_client.getRunResults(None,
                                                100,
                                                0,
                                                [],
                                                ReportFilter(),
                                                None,
                                                False)

        offed_reports = [r for r in reports
                         if r.detectionStatus == DetectionStatus.OFF]
        self.assertEqual(len(offed_reports), 1)

        unavail_reports = [r for r in reports
                           if r.detectionStatus == DetectionStatus.UNAVAILABLE]
        self.assertEqual(len(unavail_reports), 0)

    def test_detection_status_off_with_cfg(self):
        """ Test detection status with .clang-tidy config file. """
        # Explicitly disable all hicpp checkers from the command line but
        # enable all hicpp and modernize checkers from the .clang-tidy file.
        # If we store the results to the server than no reports will be marked
        # as OFF.
        cfg = dict(self._codechecker_cfg)
        cfg['checkers'] = ['-d', 'hicpp']
        cfg['analyzer_config'] = ['clang-tidy:take-config-from-directory=true']

        self._create_source_file(1)
        self._create_clang_tidy_cfg_file(['-*', 'hicpp-*', 'modernize-*'])
        return_code = self._check_source_file(cfg)
        self.assertEqual(return_code, 0)
        reports = self._cc_client.getRunResults(
            None, 100, 0, [], ReportFilter(), None, False)

        hicpp_results = [r for r in reports
                         if r.checkerId.startswith('hicpp')]
        self.assertTrue(hicpp_results)

        modernize_results = [r for r in reports
                             if r.checkerId.startswith('modernize')]
        self.assertTrue(modernize_results)

        offed_reports = [r for r in reports
                         if r.detectionStatus == DetectionStatus.OFF]
        self.assertEqual(len(offed_reports), 0)

        # Store the reports again to see that still no reports are marked as
        # OFF (every report marked as Unresolved).
        self._check_source_file(cfg)

        reports = self._cc_client.getRunResults(
            None, 100, 0, [], ReportFilter(), None, False)
        self.assertTrue([r for r in reports
                         if r.detectionStatus == DetectionStatus.UNRESOLVED])

        # Remove .clang-tidy configuration file.
        os.remove(self.clang_tidy_cfg)

    def test_store_multiple_dir_no_off(self):
        """
        Store multiple report directory and check that no reports are marked
        as OFF.
        """
        cfg = dict(self._codechecker_cfg)
        cfg['checkers'] = ['-d', 'core.DivideZero']

        self._create_source_file(1)
        codechecker.log_and_analyze(cfg,
                                    self._test_dir)

        # Remove metadata.json.
        try:
            os.remove(os.path.join(cfg['reportdir'],
                                   'metadata.json'))
        except OSError:
            pass

        # Analyze the same project to a different report directory and disable
        # modernize checkers.
        cfg['checkers'] = ['-d', 'deadcode.DeadStores']
        cfg['reportdir'] = self._codechecker_cfg['reportdir'] + "2"

        orig_test_dir = self._test_dir
        self._test_dir = self._test_dir + "2"
        shutil.copytree(orig_test_dir, self._test_dir)
        self._create_source_file(3)

        codechecker.log_and_analyze(cfg,
                                    self._test_dir)

        # Set back test dir.
        self._test_dir = orig_test_dir

        # Store two report directory.
        cfg['reportdir'] = '{0} {1}'.format(
            cfg['reportdir'],
            self._codechecker_cfg['reportdir'])
        codechecker.store(cfg, 'hello')

        # Check that no reports are marked as OFF.
        reports = self._cc_client.getRunResults(
            None, 100, 0, [], ReportFilter(), None, False)

        offed_reports = [r for r in reports
                         if r.detectionStatus == DetectionStatus.OFF]
        self.assertEqual(len(offed_reports), 0)
