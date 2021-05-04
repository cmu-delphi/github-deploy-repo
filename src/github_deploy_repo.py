"""Fetches github repos and deploys them on the delphi server.

This is how Delphi pushes code and other resources to production environments.
Deployment consists of compiling, minimizing, copying, etc.

In addition to automated deployment from GitHub, a repo (or any other data)
contained in a local tar or zip file can be deployed in the same way as an
ordinary repo. This is useful for testing uncommitted changes, deploying
unhosted projects or private repositories, and deploying files which are not
suitable for version control (e.g. binaries).

See also:

- https://github.com/cmu-delphi/github-deploy-repo
- https://developer.github.com/webhooks/
- /home/automation/public_html/github-webhook.php
"""

# standard library
import argparse
import glob
import json
import os
import shutil
import subprocess
import urllib.parse

# third party
import mysql.connector
import requests

# first party
from delphi.github_deploy_repo.actions.compile_coffee import compile_coffee
from delphi.github_deploy_repo.actions.copymove import copymove
from delphi.github_deploy_repo.actions.minimize_js import minimize_js
from delphi.github_deploy_repo.actions.py3test import py3test
from delphi.github_deploy_repo.actions.pytest import pytest
import delphi.github_deploy_repo.database as database
import delphi.operations.secrets as secrets
import delphi.utils.extractor as extractor


def get_argument_parser():
  """Define command line arguments."""

  parser = argparse.ArgumentParser()

  parser.add_argument(
    '-d', '--database',
    default=False,
    action='store_true',
    help='fetch list of stale repos from the database')
  parser.add_argument(
    '-r', '--repo',
    type=str,
    default=None,
    action='store',
    help='deploy only the specified repo (e.g. cmu-delphi/www-nowcast)')
  parser.add_argument(
    '-p', '--package',
    type=str,
    default=None,
    action='store',
    help='manually deploy the specified tar/zip file (e.g. experimental.tgz)')
  parser.add_argument(
    '--branch',
    default='master',
    help='the branch to checkout prior to deploying')

  return parser


def execute(repo_link, commit, path, config):
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

  # optional path substitution
  paths = cfg.get('paths', {})
  if len(paths) > 0:
    print('will substitute the following path fragments:')
    for key, value in paths.items():
      print(' [[%s]] -> %s' % (key, value))

  # execute actions sequentially
  actions = cfg['actions']
  executors = {
    'copy': copymove,
    'move': copymove,
    'compile-coffee': compile_coffee,
    'minimize-js': minimize_js,
    'py3test': py3test,
    'pytest': pytest
  }
  for (idx, row) in enumerate(actions):
    # each row should be either: a map/dict/object with a string field named
    #   "type", or a comment string
    if type(row) == str:
      continue
    elif type(row) != dict or 'type' not in row or type(row['type']) != str:
      raise Exception('invalid action (%d/%d)' % (idx + 1, len(actions)))

    # handle the action based on its type
    action = row.get('type').lower()
    if action in executors:
      executors[action](repo_link, commit, path, row, paths)
    else:
      raise Exception('unsupported action: %s' % action)


def deploy_repo(cnx, owner, name, branch):
  commit = None

  # check whether a deploy file exists
  if owner != '<local>':
    deploy_file_url = (
      'https://raw.githubusercontent.com/%s/%s/%s/deploy.json'
    ) % (
      urllib.parse.quote_plus(owner),
      urllib.parse.quote_plus(name),
      urllib.parse.quote_plus(branch)
    )
    response = requests.head(deploy_file_url)
    if response.status_code != 200:
      msg = (
        'repo %s/%s is private or does not have `deploy.json` '
        'on branch "%s"'
      ) % (owner, name, branch)
      print(msg)
      status = 2

      # update repo status and bail
      database.set_repo_status(cnx, owner, name, branch, commit, status)
      return

  # try to deploy, but catch any exceptions that may arise
  exception = None
  status = -1
  try:
    # a place for temporary files
    tmpdir = 'github_deploy_repo__tmp'
    os.makedirs(tmpdir)

    if owner == '<local>':
      # hash the file for record keeping
      sha1sum = subprocess.check_output("sha1sum '%s'" % name, shell=True)
      commit = sha1sum.decode('utf-8')[:40]
      url = 'file://%s' % name
      print('deploying package %s/%s (%s)' % (owner, name, url))
      print(' file SHA1 hash is %s' % commit)

      # extract the file
      extractor.Extractor.extract(name, tmpdir)

      # workaround for zipped github repos where deploy.json isn't at the root
      contents = glob.glob(os.path.join(tmpdir, '*'))
      if len(contents) == 1 and os.path.isdir(contents[0]):
        tmpdir2 = tmpdir + '2'
        # rename ./tmpdir/repo -> ./tmpdir2
        shutil.move(contents[0], tmpdir2)
        # delete ./tmpdir
        shutil.rmtree(tmpdir)
        # rename tmpdir2 -> ./tmpdir
        shutil.move(tmpdir2, tmpdir)
    else:
      # build the github repo link
      url = 'https://github.com/%s/%s.git' % (
        urllib.parse.quote_plus(owner), urllib.parse.quote_plus(name),
      )
      print('deploying repo %s/%s (%s)' % (owner, name, url))

      # clone the repo
      cmd = 'git clone %s %s' % (url, tmpdir)
      subprocess.check_call(cmd, shell=True, timeout=60)

      # checkout the branch
      cmd = 'git --git-dir %s/.git --work-tree=%s checkout %s' % (
        tmpdir, tmpdir, branch,
      )
      subprocess.check_call(cmd, shell=True, timeout=60)
      print('checked out branch %s' % branch)

      # get the latest commit hash
      cmd = 'git --git-dir %s/.git rev-parse HEAD' % tmpdir
      commit = subprocess.check_output(cmd, shell=True)
      commit = str(commit, 'utf-8').strip()
      print(' most recent commit is %s' % commit)

      # remove trailing ".git" from the display url
      url = url[:-4]

    # deploy the repo
    config_name = 'deploy.json'
    config_file = os.path.join(tmpdir, config_name)
    if os.path.isfile(config_file):
      execute(url, commit, tmpdir, config_name)
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

  if owner != '<local>':
    # update repo status
    database.set_repo_status(cnx, owner, name, branch, commit, status)

  # throw the exception, if it exists
  if exception is not None:
    raise exception


def deploy_all(cnx, repos):
  # deploy one at a time, keeping track of any errors along the way
  exceptions = []
  for (owner, name, branch) in repos:
    try:
      deploy_repo(cnx, owner, name, branch)
    except Exception as ex:
      info = '%s/%s (%s)' % (owner, name, branch)
      print('failed to deploy', info, ex)
      exceptions.append(ex)

  # throw the first exception, if there is one
  if len(exceptions) > 0:
    raise exceptions[0]


def main(args):
  """Command line usage."""

  # don't mix package deploy with database deploy
  if args.package and (args.database or args.repo):
    print('--package cant be used with --repo or --database')
    parser.print_help()
    return

  if args.package and args.branch != 'master':
    raise Exception('--branch is not available with --package')

  # deploy a local archive, which does not require the database
  if args.package:
    # deploy a local tar/zip file as if it were a repo
    deploy_repo(None, '<local>', args.package, None)
    return

  # database setup
  u, p = secrets.db.auto
  cnx = mysql.connector.connect(
      host=secrets.db.host, user=u, password=p, database='utils')

  specific_repos = set()
  if args.repo:
    owner, name = args.repo.split('/')
    specific_repos = {(owner, name, args.branch)}

  database_repos = set()
  if args.database:
    database_repos = set(database.get_repo_list(cnx, args.branch))

  if args.repo and args.database:
    # deploy the specific repo only if it's stale in the database
    repos = specific_repos & database_repos
  else:
    # deploy either a specific repo or all stale repos from the database
    repos = specific_repos | database_repos
  repo_list = sorted(repos)

  if repo_list:
    print('will deploy the following repos:')
    for (owner, name, branch) in repo_list:
      print(' %s/%s (%s)' % (owner, name, branch))
    deploy_all(cnx, repo_list)
  else:
    print('no repos to deploy')

  # database cleanup
  cnx.close()


if __name__ == '__main__':
  main(get_argument_parser().parse_args())
