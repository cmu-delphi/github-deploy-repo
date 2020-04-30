"""Provides an abstraction around the database."""


def get_repo_list(cnx, branch):
  # pick all repos with status of 0
  cur = cnx.cursor()
  cur.execute("SELECT `repo` FROM `github_deploy_repo` WHERE `status` = 0")
  repos = [repo.split('/', 2) for (repo,) in cur]
  cur.close()
  repos = [tuple(repo) for repo in repos if repo[2] == branch]
  return repos


def set_repo_status(cnx, owner, name, branch, commit, status):
  # update the repo status table
  repo = '%s/%s/%s' % (owner, name, branch)
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
