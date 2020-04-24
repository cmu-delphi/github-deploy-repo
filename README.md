# Status
[![Deploy Status](http://delphi.midas.cs.cmu.edu/~automation/public/github_deploy_repo/badge.php?repo=cmu-delphi/github-deploy-repo)](#)

# About
Fetches github repos and deploys them on the Delphi server.

*Including this one :)*

# Deployment Language

<!-- TODO: provide additional documentation for the deployment language -->

Deployment instructions are defined in a JSON file. By default, this file is
named **"deploy.json"** and lives in the root of the git repository. Most
fields should be self-explanatory, but the various commands (aka "actions") are
described below.

## `copy`

Copies a file. Note that the source file must reside with the repository (e.g.
it will refuse to copy `/etc/passwd`). The destination file, however, can be
anywhere in the filesystem (well, anywhere the user has write access). Existing
files will be overwritten.

Additional fields:

- `src` (**required**)

    The source file.

- `dst` (**required**)

    The destination file.

- `match` (_optional_)

    A regular expression. The action is applied to all files whose basename
    matches the regex. If this field is present, `src` and `dst` are
    interpreted as directories instead of files.

- `add-header-comment` (_optional_)

    Whether to include a header comment (containing a warning not to edit the
    file and a pointer to the repository) at the top of the destination file.


- `replace-keywords` (_optional_)

    Replace template strings in source file with values found in the list of
    template files. Each file is a JSON object containing a list of (key,
    value) pairs to be replaced.

## `move`

Identical to the [`copy`](#copy) command, except the source file is deleted.

## `compile-coffee`

Transpiles a CoffeeScript file to a JavaScript file.

Additional fields:

- `src` (**required**)

    The input file.

- `dst` (_optional_)

    The output file. Default is `src` with extension replaced with "js", unless
    otherwise specified.

## `minimize-js`

Minimize a JavaScript file.

Additional fields:

- `src` (**required**)

    The input file.

- `dst` (_optional_)

    The output file. Defaults to `src` unless otherwise specified.

## `py3test`

Runs unit and coverage tests for python using
[py3tester](https://github.com/undefx/py3tester). Any test errors or failures
will cause the deployment to fail, even if it was otherwise successful.

Additional fields:

- `dir` (_optional_)

    The directory, relative to the repo root, containing unit tests. Defaults
    to "tests" (e.g. "repo_name/tests").
