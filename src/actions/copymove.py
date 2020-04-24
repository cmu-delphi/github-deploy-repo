"""Copy and/or move files."""

# standard library
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import time

# first party
import delphi.github_deploy_repo.file_operations as file_operations

# header for generated files
HEADER_WIDTH = 55
HEADER_LINES = [
  # output from `figlet 'DO NOT EDIT'`
  r' ____   ___    _   _  ___ _____   _____ ____ ___ _____ ',
  r'|  _ \ / _ \  | \ | |/ _ \_   _| | ____|  _ \_ _|_   _|',
  r'| | | | | | | |  \| | | | || |   |  _| | | | | |  | |  ',
  r'| |_| | |_| | | |\  | |_| || |   | |___| |_| | |  | |  ',
  r'|____/ \___/  |_| \_|\___/ |_|   |_____|____/___| |_|  ',
]


def add_header(repo_link, commit, src, dst_ext):
  # build the header based on the source language
  ext = dst_ext.lower()
  pre_block, post_block, pre_line, post_line = '', '', '', ''
  blanks = '\n\n\n'
  if ext in ('html', 'xml'):
    pre_block, post_block = '<!--\n', '-->\n' + blanks
  elif ext in ('js', 'min.js', 'css', 'c', 'cpp', 'h', 'hpp', 'java'):
    pre_block, post_block = '/*\n', '*/\n' + blanks
  elif ext in ('py', 'r', 'coffee', 'htaccess', 'sh'):
    pre_line, post_line, post_block = '# ', ' #', blanks
  elif ext in ('php'):
    # be sure to not introduce whitespace (e.g. newlines) outside php tags
    pre_block, post_block = '<?php /*\n', '*/\n' + blanks + '?>'
  else:
    # nothing modified, return the original file
    print(' warning: skipped header for file extension [%s]' % dst_ext)
    return src

  # additional header lines
  t = round(time.time())
  dt = datetime.datetime.fromtimestamp(t).isoformat(' ')
  lines = [
    '',
    'Automatically generated from sources at:',
    repo_link,
    '',
    ('Commit hash: %s' % commit),
    ('Deployed at: %s (%d)' % (dt, t)),
  ]

  # add the header to a copy of the source file
  tmp = file_operations.get_file(src[0] + '__header')
  print(' adding header [%s] -> [%s]' % (src[0], tmp[0]))
  with open(tmp[0], 'wb') as fout:
    fout.write(bytes(pre_block, 'utf-8'))
    for line in HEADER_LINES + [line.center(HEADER_WIDTH) for line in lines]:
      fout.write(bytes(pre_line + line + post_line + '\n', 'utf-8'))
    fout.write(bytes(post_block, 'utf-8'))
    with open(src[0], 'rb') as fin:
      fout.write(fin.read())

  # return the new file
  return tmp


def replace_keywords(src, templates):
  # load list of (key, value) pairs
  pairs = []
  for t in templates:
    with open(t[0], 'r') as f:
      pairs.extend(json.loads(f.read()))

  # make a new file to hold the results
  tmp = file_operations.get_file(src[0] + '__valued')
  print(' replacing %d keywords [%s] -> [%s]' % (len(pairs), src[0], tmp[0]))
  with open(tmp[0], 'w') as fout:
    with open(src[0], 'r') as fin:
      for line in fin.readlines():
        for (k, v) in pairs:
          line = line.replace(k, v)
        fout.write(line)

  # return the new file
  return tmp


def copymove_single(repo_link, commit, path, row, src, dst, is_move):
  action = 'move' if is_move else 'copy'
  print(' %s %s -> %s' % (action, src[2], dst[2]))
  # check access
  file_operations.check_file(src[0], path)
  # put a big "do not edit" warning at the top of the file
  if row.get('add-header-comment', False) is True:
    src = add_header(repo_link, commit, src, dst[3])
  # replace template keywords with values
  templates = row.get('replace-keywords')
  if type(templates) is str:
    templates = [templates]
  if type(templates) in (tuple, list):
    full_templates = [file_operations.get_file(t, path) for t in templates]
    src = replace_keywords(src, full_templates)
  # make the copy (method depends on destination)
  if dst[0].startswith('/var/www/html/'):
    # copy to staging area
    tmp = file_operations.get_file(src[2] + '__tmp', '/common/')
    print(' [%s] -> [%s]' % (src[0], tmp[0]))
    shutil.copy(src[0], tmp[0])
    # make directory and move the file as user `webadmin`
    cmd = "sudo -u webadmin -s mkdir -p '%s'" % (dst[1])
    print('  [%s]' % cmd)
    subprocess.check_call(cmd, shell=True)
    cmd = "sudo -u webadmin -s mv -fv '%s' '%s'" % (tmp[0], dst[0])
    print('  [%s]' % cmd)
    subprocess.check_call(cmd, shell=True)
  else:
    # make directory and copy the file
    print(' [%s] -> [%s]' % (src[0], dst[0]))
    os.makedirs(dst[1], exist_ok=True)
    shutil.copy(src[0], dst[0])
  # maybe delete the source file
  if is_move:
    os.remove(src[0])


def copymove(repo_link, commit, path, row, substitutions):
  # {copy|move} <src> <dst> [add-header-comment] [replace-keywords]
  src = file_operations.get_file(row['src'], path, substitutions)
  dst = file_operations.get_file(row['dst'], path, substitutions)
  # determine which file(s) should be used
  if 'match' in row:
    sources, destinations = [], []
    for name in glob.glob(os.path.join(src[0], '*')):
      src2 = file_operations.get_file(name)
      basename = src2[2]
      if re.match(row['match'], basename) is not None:
        sources.append(src2)
        file_path = os.path.join(dst[0], basename)
        destinations.append(file_operations.get_file(file_path))
  else:
    sources, destinations = [src], [dst]
  # apply the action to each file
  is_move = row.get('type').lower() == 'move'
  for src, dst in zip(sources, destinations):
    copymove_single(repo_link, commit, path, row, src, dst, is_move)
