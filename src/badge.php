<?php
/*
generates a "badge" for github repos (based on http://shield.io)

initial version by dfarrow on 2016-10-20

test like:
  curl http://delphi.midas.cs.cmu.edu/~automation/public/github_deploy_repo/badge.php?repo=cmu-delphi/www-nowcast
*/

// conveniently reuse automation's database "library"
require('database.php');
$dbh = DatabaseConnect();

// the data is in the query string
$repo = $_GET['repo'];

// trust no one
$repo = mysql_real_escape_string($repo);

// defaults
$hash = '????????';
$status = -2;

if ($repo && $dbh) {
  // get the has and status for this repo
  $result = mysql_query("SELECT substring(`commit`, 1, 7) `hash`, `status` FROM utils.`github_deploy_repo` WHERE `repo` = '{$repo}'");
  if($row = mysql_fetch_array($result)) {
    $hash = $row['hash'];
    $status = $row['status'];
  }
}

// close database connection
mysql_close($dbh);

// status label and color
if($status == 0) {
  $label = 'queued';
  $color = '#aaa';
} elseif($status == 1) {
  $label = 'success';
  $color = '#4c1';
} elseif($status == 2) {
  $label = 'skipped';
  $color = '#aaa';
} else if($status == -1) {
  $label = 'failed';
  $color = '#d54';
} else {
  $label = 'unknown';
  $color = '#f73';
}

// set headers to indicate that this response shouldn't be cached
$now = time();
$fmt = "D, d M Y H:i:s";
header("Pragma: no-cache");
header("Cache-Control: no-cache, no-store, must-revalidate");
header("Date: " . gmdate($fmt, $now) . " GMT");
header("Expires: " . gmdate($fmt, $now - 1) . " GMT");
header("Last-Modified: " . gmdate($fmt, $now) . " GMT");

// generate the svg
header("Content-Type: image/svg+xml;charset=utf-8");
?>
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40">
  <g shape-rendering="crispEdges">
    <path fill="#555" d="M0 0h54v40H0z"/>
    <path fill="#aaa" d="M54 0h68v20H54z"/>
    <path fill="<?php print($color); ?>" d="M54 20h68v20H54z"/>
  </g>
  <g fill="#fff" font-size="11">
    <g font-family="DejaVu Sans,Verdana,Geneva,sans-serif" text-anchor="end">
      <text x="49" y="14">version</text>
      <text x="49" y="34">deploy</text>
    </g>
    <g font-family="DejaVu Sans Mono,monospace" text-anchor="middle">
      <text x="87" y="14"><?php print($hash); ?></text>
    </g>
    <g font-family="DejaVu Sans,Verdana,Geneva,sans-serif" text-anchor="middle">
      <text x="87" y="34"><?php print($label); ?></text>
    </g>
  </g>
</svg>
