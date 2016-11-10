'''
===============
=== Purpose ===
===============

Fetches github repos and "deploys" them on the delphi server. (Aka, push to
production.) Deployment consists of compiling, minimizing, copying, etc.

See also:
  - https://github.com/cmu-delphi/
  - https://developer.github.com/webhooks/
  - /home/automation/public_html/github-webhook.php


=====================
=== Configuration ===
=====================

This program follows deployment instructions defined in a JSON file. By
default, this file is named "deploy.json" and lives in the root of the
git repository. Most fields should be self-explanatory, but the various
commands ("actions") are described below.

  - [copy] Copies a file. Note that the source file must reside with the
    repository (e.g. it will refuse to copy /etc/passwd). The destination
    file, however, can be anywhere in the filesystem (well, anywhere the
    user has write access). Existing files will be overwritten. Additional
    fields:
    - [src] The source file. (required)
    - [dst] The destination file. (required)
    - [match] A regular expression. The action is applied to all files whose
      basename matches the regex. If this field is present, `src` and `dst` are
      interpreted as directories instead of files. (optional)
    - [add-header-comment] Whether to include a header comment (containing a
      warning not to edit the file and a pointer to the repository) at the top
      of the destination file. (optional)
    - [replace-keywords] Replace template strings in source file with values
      found in the list of template files. Each file is a JSON object
      containing a list of (key, value) pairs to be replaced. (optional)

  - [move] Identical to the `copy` command except the source file is deleted.

  - [compile-coffee] Transpiles a CoffeeScript file to a JavaScript file.
    Additional fields:
    - [src] The input file. (required)
    - [dst] The output file. (required)

  - [minimize-js] Minimize a JavaScript file. Additional fields:
    - [src] The input file. (required)
    - [dst] The output file. (required)


=======================
=== Data Dictionary ===
=======================

`github_deploy_repo` is the table where repo information is stored.
+----------+--------------+------+-----+---------------+----------------+
| Field    | Type         | Null | Key | Default       | Extra          |
+----------+--------------+------+-----+---------------+----------------+
| id       | int(11)      | NO   | PRI | NULL          | auto_increment |
| repo     | varchar(128) | NO   | UNI | NULL          |                |
| commit   | char(40)     | NO   |     | 0000[...]0000 |                |
| datetime | datetime     | NO   |     | NULL          |                |
| status   | int(11)      | NO   |     | 0             |                |
+----------+--------------+------+-----+---------------+----------------+
id: unique identifier for each record
repo: the name of the github repo (in the form of "owner/name")
commit: hash of the latest commit
datetime: the date and time of the last status update
statue: one of 0 (queued), 1 (success), 2 (skipped), or -1 (failed)


=================
=== Changelog ===
=================

2016-11-09
  + support header for htaccess files
  + treat actions of type string as comments
  + `move` command
  + match files for copy/move with optional regex
2016-11-05
  * fancier header for generated files
2016-11-03
  * create directories when copying files
2016-10-28
  + support header for PHP files
  * fix newlines when replacing keywords
  * fix copy to non-web locations
  * use python secrets
2016-10-21
  + templating via "replace-keywords"
2016-10-20
  + switch database and store deploy status
2016-10-17
  * original version
'''

# built-in
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
# external
import mysql.connector
# local
import secrets


# header for generated files
HEADER_WIDTH = 55
HEADER_LINES = [
  # from the command line, run: figlet "DO NOT EDIT"
  ' ____   ___    _   _  ___ _____   _____ ____ ___ _____ ',
  '|  _ \ / _ \  | \ | |/ _ \_   _| | ____|  _ \_ _|_   _|',
  '| | | | | | | |  \| | | | || |   |  _| | | | | |  | |  ',
  '| |_| | |_| | | |\  | |_| || |   | |___| |_| | |  | |  ',
  '|____/ \___/  |_| \_|\___/ |_|   |_____|____/___| |_|  ',
  ' ' * HEADER_WIDTH,
  'Automatically generated from sources at:'.center(HEADER_WIDTH),
]


def get_file(name, path=None):
  if path is not None:
    name = os.path.join(path, name)
  absname = os.path.abspath(name)
  path, name = os.path.split(absname)
  if '.' in name:
    ext = name[name.index('.') + 1:]
  else:
    ext = ''
  return absname, path, name, ext


def add_header(repo_link, src, dst_ext):
  # build the header based on the source language
  ext = dst_ext.lower()
  pre_block, post_block, pre_line, post_line = '', '', '', ''
  blanks = '\n\n\n'
  if ext in ('html', 'xml'):
    pre_block, post_block = '<!--\n', '-->\n' + blanks
  elif ext in ('js', 'min.js', 'css', 'c', 'cpp', 'h', 'hpp', 'java'):
    pre_block, post_block = '/*\n', '*/\n' + blanks
  elif ext in ('py', 'r', 'coffee', 'htaccess'):
    pre_line, post_line, post_block = '# ', ' #', blanks
  elif ext in ('php'):
    # be sure to not introduce whitespace (e.g. newlines) outside php tags
    pre_block, post_block = '<?php /*\n', '*/\n' + blanks + '?>'
  else:
    # nothing modified, return the original file
    print(' warning: skipped header for file extension [%s]' % dst_ext)
    return src

  # add the header to a copy of the source file
  tmp = get_file(src[0] + '__header')
  print(' adding header [%s] -> [%s]' % (src[0], tmp[0]))
  with open(tmp[0], 'wb') as fout:
    fout.write(bytes(pre_block, 'utf-8'))
    for line in HEADER_LINES + [repo_link.center(HEADER_WIDTH)]:
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
  tmp = get_file(src[0] + '__valued')
  print(' replacing %d keywords [%s] -> [%s]' % (len(pairs), src[0], tmp[0]))
  with open(tmp[0], 'w') as fout:
    with open(src[0], 'r') as fin:
      for line in fin.readlines():
        for (k, v) in pairs:
          line = line.replace(k, v)
        fout.write(line)

  # return the new file
  return tmp


def execute(repo_link, path, config):
  # magic and versioning
  typestr = 'delphi deploy config'
  v_min = v_max = 1

  # parse the config file
  with open(os.path.join(path, config)) as f:
    cfg = json.loads(f.read())

  # cfg better be a map/dictionary
  if type(cfg) is not dict:
    raise Exception('unable to load deploy config file')

  # sanity checks
  for (name, result) in [
    ['type', cfg.get('type') == typestr],
    ['version', v_min <= cfg.get('version', 0) <= v_max],
    ['actions', type(cfg.get('actions')) is list],
  ]:
    if not result:
      raise Exception('missing or invalid deploy config `%s`' % name)

  # just in case
  if cfg.get('skip', False) is True:
    print('field `skip` is present and true - skipping deploy')
    return

  # restrict read access to only files in the provided working directory
  source_dir = get_file(path)[0]
  def check_file(abspath):
    if not abspath.startswith(source_dir):
      raise Exception('file [%s] is not inside [%s]' % (abspath, source_dir))

  # execute actions sequentially
  actions = cfg['actions']
  for (idx, row) in enumerate(actions):
    # each row should be either: a map/dict/object with a string field named
    #   "type", or a comment string
    if type(row) == str:
      continue
    elif type(row) != dict or 'type' not in row or type(row['type']) != str:
      raise Exception('invalid action (%d/%d)' % (idx + 1, len(actions)))

    # handle the action based on its type
    action = row.get('type').lower()
    if action in ('copy', 'move'):
      # {copy|move} <src> <dst> [add-header-comment] [replace-keywords]
      src, dst = get_file(row['src'], path), get_file(row['dst'], path)
      # check access
      check_file(src[0])
      # determine which file(s) should be used
      if 'match' in row:
        sources, destinations = [], []
        for name in glob.glob(os.path.join(src[0], '*')):
          src2 = get_file(name)
          basename = src2[2]
          if re.match(row['match'], basename) is not None:
            sources.append(src2)
            destinations.append(get_file(os.path.join(dst, basename)))
      else:
        sources, destinations = [src], [dst]
      # apply the action to each file
      for src, dst in zip(sources, destinations):
        print(' %s %s -> %s' % (action, src[2], dst[2]))
        # put a big "do not edit" warning at the top of the file
        if row.get('add-header-comment', False) is True:
          src = add_header(repo_link, src, dst[3])
        # replace template keywords with values
        templates = row.get('replace-keywords')
        if type(templates) is str:
          templates = [templates]
        if type(templates) in (tuple, list):
          src = replace_keywords(src, [get_file(t, path) for t in templates])
        # make the copy (method depends on destination)
        if dst[0].startswith('/var/www/html/'):
          # copy to staging area
          tmp = get_file(src[2] + '__tmp', '/common')
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
        if action == 'move':
          os.remove(src[0])
    elif action == 'compile-coffee':
      # compile-coffee <src> <dst>
      src, dst = get_file(row['src'], path), get_file(row['dst'], path)
      print(' %s %s -> %s' % (action, src[2], dst[2]))
      check_file(src[0])
      cmd = "coffee -c -p '%s' > '%s'" % (src[0], dst[0])
      print('  [%s]' % cmd)
      subprocess.check_call(cmd, shell=True)
    elif action == 'minimize-js':
      # minimize-js <src> <dst>
      src, dst = get_file(row['src'], path), get_file(row['dst'], path)
      print(' %s %s -> %s' % (action, src[2], dst[2]))
      check_file(src[0])
      cmd = "uglifyjs '%s' -c -m -o '%s'" % (src[0], dst[0])
      print('  [%s]' % cmd)
      subprocess.check_call(cmd, shell=True)
    else:
      raise Exception('unsupported action: %s' % action)


def deploy_repo(cnx, owner, name):
  # try to deploy, but catch any exceptions that may arise
  exception = None
  status = -1
  commit = None
  try:
    # build the github repo link
    url = 'https://github.com/%s/%s.git' % (owner, name)
    print('deploying repo %s/%s (%s)' % (owner, name, url))

    # a place for temporary files
    tmpdir = 'github_deploy_repo__tmp'
    os.makedirs(tmpdir)

    # clone the repo
    cmd = 'git clone %s %s' % (url, tmpdir)
    subprocess.check_call(cmd, shell=True, timeout=60)
    # get the latest commit hash
    cmd = 'git --git-dir %s/.git rev-parse HEAD' % tmpdir
    commit = subprocess.check_output(cmd, shell=True)
    commit = str(commit, 'utf-8').strip()
    print(' most recent commit is %s' % commit)

    # deploy the repo
    config_name = 'deploy.json'
    config_file = os.path.join(tmpdir, config_name)
    if os.path.isfile(config_file):
      execute(url[:-4], tmpdir, config_name)
      status = 1
    else:
      print('deploy config does not exist for this repo (%s)' % config_file)
      status = 2
  except Exception as ex:
    exception = ex

  # safely cleanup temporary files
  try:
    shutil.rmtree(tmpdir)
  except Exception as ex:
    if exception is None:
      exception = ex

  # update repo status
  set_repo_status(cnx, owner, name, commit, status)

  # throw the exception, if it exists
  if exception is not None:
    raise exception


def deploy_all(cnx, repos):
  # deploy one at a time, keeping track of any errors along the way
  exceptions = []
  for (owner, name) in repos:
    try:
      deploy_repo(cnx, owner, name)
    except Exception as ex:
      print('failed to deploy %s/%s - %s' % (str(owner), str(name), str(ex)))
      exceptions.append(ex)

  # throw the first exception, if there is one
  if len(exceptions) > 0:
    raise exceptions[0]


def get_repo_list(cnx):
  # pick all repos with status of 0
  cur = cnx.cursor()
  cur.execute("SELECT `repo` FROM `github_deploy_repo` WHERE `status` = 0")
  repos = [repo.split('/') for (repo,) in cur]
  cur.close()
  return repos


def set_repo_status(cnx, owner, name, commit, status):
  # update the repo status table
  repo = '%s/%s' % (owner, name)
  cur = cnx.cursor()

  # execute the proper update
  if commit is not None:
    args = (repo, commit, status, commit, status)
    cur.execute("""
      INSERT INTO `github_deploy_repo`
        (`repo`, `commit`, `datetime`, `status`)
      VALUES
        (%s, %s, now(), %s)
      ON DUPLICATE KEY UPDATE
        `commit` = %s, `datetime` = now(), status = %s
    """, args)
  else:
    args = (repo, status, status)
    cur.execute("""
      INSERT INTO `github_deploy_repo`
        (`repo`, `datetime`, `status`)
      VALUES
        (%s, now(), %s)
      ON DUPLICATE KEY UPDATE
        `datetime` = now(), status = %s
    """, args)

  # cleanup
  cur.close()
  cnx.commit()


if __name__ == '__main__':
  # args and usage
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-d', '--database',
    default=False,
    action='store_true',
    help='fetch list of repos from the database')
  parser.add_argument(
    '-r', '--repo',
    type=str,
    default=None,
    action='store',
    help='manually deploy the specified repo (e.g. cmu-delphi/www-nowcast)')
  args = parser.parse_args()

  # require either database or specific repo
  if not (args.database ^ (args.repo is not None)):
    print('Exactly one of `database` or `repo` must be given.')
    parser.print_help()
    sys.exit(0)

  # database setup
  u, p = secrets.db.auto
  cnx = mysql.connector.connect(user=u, password=p, database='utils')

  if args.database:
    # deploy from database
    repos = get_repo_list(cnx)
    if len(repos) > 0:
      print('will deploy the following repos:')
      for (owner, name) in repos:
        print(' %s/%s' % (owner, name))
      deploy_all(cnx, repos)
    else:
      print('no repos to deploy')

  if args.repo is not None:
    # deploy manually
    owner, name = args.repo.split('/')
    deploy_repo(cnx, owner, name)

  # database cleanup
  cnx.close()
