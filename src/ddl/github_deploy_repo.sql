/*
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
- `id`
  unique identifier for each record
- `repo`
  the name of the github repo (in the form of "owner/name/branch")
- `commit`
  hash of the latest commit
- `datetime`
  the date and time of the last status update
- `status`
  one of 0 (queued), 1 (success), 2 (skipped), or -1 (failed)
*/
CREATE TABLE `github_deploy_repo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `repo` varchar(128) NOT NULL,
  `commit` char(40) NOT NULL DEFAULT '0000000000000000000000000000000000000000',
  `datetime` datetime NOT NULL,
  `status` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `repo` (`repo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
