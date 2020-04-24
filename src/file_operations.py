"""Utilities for handling files."""

# standard library
import os


def get_substituted_path(path, substitutions):
  for key, value in substitutions.items():
    pattern = '[[%s]]' % key
    if pattern in path:
      path = path.replace(pattern, value)
  return path


def get_file(name, path=None, substitutions={}):
  new_name = get_substituted_path(name, substitutions)
  if new_name != name:
    print('substituted [%s] -> [%s]' % (name, new_name))
    name = new_name
  if path is not None:
    name = os.path.join(path, name)
  absname = os.path.abspath(name)
  path, name = os.path.split(absname)
  if '.' in name:
    ext = name[name.index('.') + 1:]
  else:
    ext = ''
  return absname, path, name, ext


def check_file(abspath, path):
  source_dir = get_file(path)[0]
  if not abspath.startswith(source_dir):
    raise Exception('file [%s] is not inside [%s]' % (abspath, source_dir))
