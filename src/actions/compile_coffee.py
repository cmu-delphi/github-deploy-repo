"""Compile a CoffeeScript file."""

# standard library
import subprocess

# first party
import delphi.github_deploy_repo.file_operations as file_operations


def compile_coffee(repo_link, commit, path, row, substitutions):
  # compile-coffee <src> [dst]
  src = file_operations.get_file(row['src'], path, substitutions)
  if 'dst' in row:
    dst = file_operations.get_file(row['dst'], path, substitutions)
  else:
    basename, extension = src[2:4]
    if extension != '':
      basename = basename[:-len(extension)] + 'js'
    else:
      basename += '.js'
    dst = file_operations.get_file(basename, src[1])
  # check access
  file_operations.check_file(src[0], path)
  # compile
  action = row.get('type').lower()
  print(' %s %s -> %s' % (action, src[2], dst[2]))
  cmd = "coffee -c -p '%s' > '%s'" % (src[0], dst[0])
  print('  [%s]' % cmd)
  subprocess.check_call(cmd, shell=True)
