"""Minimize a JavaScript file."""

# standard library
import subprocess

# first party
import delphi.github_deploy_repo.file_operations as file_operations


def minimize_js(repo_link, commit, path, row, substitutions):
  # minimize-js <src> [dst]
  src = file_operations.get_file(row['src'], path, substitutions)
  if 'dst' in row:
    dst = file_operations.get_file(row['dst'], path, substitutions)
  else:
    dst = src
  # check access
  file_operations.check_file(src[0], path)
  # minimize
  action = row.get('type').lower()
  print(' %s %s -> %s' % (action, src[2], dst[2]))
  cmd = "uglifyjs '%s' -c -m -o '%s'" % (src[0], dst[0])
  print('  [%s]' % cmd)
  subprocess.check_call(cmd, shell=True)
