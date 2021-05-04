"""Run unit tests."""

# standard library
import os
import subprocess

# third party
import pytest

# first party
import delphi.github_deploy_repo.file_operations as file_operations

class Plugin:
  def __init__(self):
    self.summary={
      "passed":0,
      "failed":0,
      "skipped":0,
      "errors":0
    }
  def pytest_runtest_logreport(self, report):
    self.summary[report.outcome] += 1
  def pytest_internalerror(self, *args, **kwargs):
    self.summary["errors"] += 1
  def pytest_exception_interact(self, *args, **kwargs):
    self.summary["errors"] += 1

def pytest(repo_link, commit, path, row, substitutions):
  # pytest [dir]

  # parse arguments
  if 'dir' in row:
    location = file_operations.get_file(row['dir'], path, substitutions)[0]
  else:
    location = os.path.join(path, 'tests')
  pattern = '^(test_.*|.*_test)\\.py$'

  # run tests and gather results
  p = Plugin()
  pytest.main([location, 'no:terminal'], plugins=[p])
  bad = p.summary['failed'] + p.summary['errors']
  if bad > 0:
    raise Exception('%d test(s) did not pass' % bad)
  elif p.summary['passed'] == 0:
    print('no tests found')
  else:
    print('%d test(s) passed!' % p.summary['passed'])
