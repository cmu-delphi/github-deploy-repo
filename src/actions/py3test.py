"""Run unit tests."""

# standard library
import os
import subprocess

# third party
import undefx.py3tester.py3tester as p3t

# first party
import delphi.github_deploy_repo.file_operations as file_operations


def py3test(repo_link, commit, path, row, substitutions):
  # py3test [dir]

  # parse arguments
  if 'dir' in row:
    location = file_operations.get_file(row['dir'], path, substitutions)[0]
  else:
    location = os.path.join(path, 'tests')
  pattern = '^(test_.*|.*_test)\\.py$'
  terminal = False

  # find tests
  test_files = p3t.find_tests(location, pattern, terminal)

  # run tests and gather results
  results = [p3t.analyze_results(p3t.run_tests(f)) for f in test_files]

  # check for success
  # TODO: show in repo badge
  totals = {
    'good': 0,
    'bad': 0,
    'lines': 0,
    'hits': 0,
  }
  for test in results:
    totals['good'] += test['unit']['summary']['pass']
    totals['bad'] += test['unit']['summary']['fail']
    totals['bad'] += test['unit']['summary']['error']
    totals['lines'] += test['coverage']['summary']['total_lines']
    totals['hits'] += test['coverage']['summary']['hit_lines']
  if totals['bad'] > 0:
    raise Exception('%d test(s) did not pass' % totals['bad'])
  elif totals['good'] == 0:
    print('no tests found')
  else:
    print('%d test(s) passed!' % totals['good'])
    num = len(results)
    cov = 100 * totals['hits'] / totals['lines']
    print('overall coverage for %d files: %.1f%%' % (num, cov))
