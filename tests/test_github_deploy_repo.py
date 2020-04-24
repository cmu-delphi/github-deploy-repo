"""Unit tests for github_deploy_repo.py."""

# standard library
import argparse
import unittest

# py3tester coverage target
__test_target__ = 'delphi.github_deploy_repo.github_deploy_repo'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_argument_parser(self):
    """Return a parser for command-line arguments."""

    self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)
