<?php
/*
updates local repos (via automation) whenever a new commit is pushed to github

initial version by dfarrow on 2016-10-17

test like:
  curl -X POST -d '{"after":"abcd1234", "repository":{"name":"some-delphi-repo"}}' http://delphi.midas.cs.cmu.edu/~automationpublic/github_deploy_repo/webhook.php
*/

// conveniently reuse automation's database "library"
require('database.php');
$dbh = DatabaseConnect();

// the data comes as a json string in the POST body
// todo - check the HTTP header's HMAC, make sure the data hasn't been spoofed
$data = json_decode(file_get_contents('php://input'), true);

// extract the relevant info (see `sample.json`)
$name = $data['repository']['name'];
$repo = 'cmu-delphi/' . $name;
$hash = $data['after'];
$branch = strpos($data['ref'], 'refs/heads/') === 0 ? substr($data['ref'], 11) : null;

// trust no one
$repo = mysql_real_escape_string($repo);
$hash = mysql_real_escape_string($hash);
if ($branch !== null) {
  $branch = mysql_real_escape_string($branch);
}

if ($name && $dbh && $branch !== null) {
  // append the repo name to the list of repos to update
  $full_repo = $repo . '/' . $branch;
  mysql_query("INSERT INTO utils.`github_deploy_repo` (`repo`, `commit`, `datetime`) VALUES ('{$full_repo}', '{$hash}', now()) ON DUPLICATE KEY UPDATE `commit` = '{$hash}', `datetime` = now(), status = 0");

  // queue the step that will actually update the repos ([github] Deploy Repo)
  RunStep(42);
}

// close database connection
mysql_close($dbh);

// github doesn't need a response... but why not
print(":)\n");
?>
