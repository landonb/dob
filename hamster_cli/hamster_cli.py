# -*- coding: utf-8 -*-

# This file is part of 'hamster_cli'.
#
# 'hamster_cli' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'hamster_cli' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'hamster_cli'.  If not, see <http://www.gnu.org/licenses/>.

"""A time tracker for the command line. Utilizing the power of hamster-lib."""

from __future__ import absolute_import, unicode_literals

from gettext import gettext as _

import click
import datetime
import logging
import os
import sys
from click_aliases import ClickAliasedGroup

from hamster_cli import __version__ as hamster_cli_version
from hamster_cli import __appname__ as hamster_cli_appname
from hamster_lib import __version__ as hamster_lib_version
from hamster_lib import HamsterControl
from hamster_lib.helpers import logging as logging_helpers

from . import cmd_options
from . import help_strings
from . import migrate
from .cmd_config import get_config, get_config_instance, get_config_path
from .cmd_options import cmd_options_search, cmd_options_limit_offset, cmd_options_table_bunce, cmd_options_insert
from .cmds_list import activity as list_activity
from .cmds_list import category as list_category
from .cmds_list import tag as list_tag
from .cmds_list.fact import (
    generate_facts_table,
    list_current_fact,
)
from .cmds_usage import activity as usage_activity
from .cmds_usage import category as usage_category
from .cmds_usage import tag as usage_tag
from .complete import tab_complete
from .create import add_fact, cancel_fact, start_fact, stop_fact
from .details import app_details
from .search import search_facts
from .transcode import export_facts
from .helpers.ascii_table import generate_table, warn_if_truncated


# Disable the python_2_unicode_compatible future import warning.
click.disable_unicode_literals_warning = True


# ***
# *** [CONTROLLER] HamsterControl Controller.
# ***


class Controller(HamsterControl):
    """
    A custom controller that adds config handling on top of its regular functionality.
    """

    def __init__(self):
        """Instantiate controller instance and adding client_config to it."""
        lib_config, client_config = get_config(get_config_instance())
        self._verify_args(lib_config)
        super(Controller, self).__init__(lib_config)
        self.client_config = client_config

    def _verify_args(self, lib_config):
        # *cough*hack!*cough*”
        # Because invoke_without_command, we allow command-less hamster
        #   invocations. For one such invocation -- murano -v -- tell the
        #   store not to log.
        # Also tell the store not to log if user did not specify anything,
        #   because we'll show the help/usage (which Click would normally
        #   handle if we hadn't tampered with invoke_without_command).
        if (
            (len(sys.argv) == 1) or
            ((len(sys.argv) == 2) and (sys.argv[1] in ('-v', 'version')))
        ):
            lib_config['sql_log_level'] = 'WARNING'
        elif len(sys.argv) == 1:
            # Because invoke_without_command, now we handle command-less
            # deliberately ourselves.
            pass


pass_controller = click.make_pass_decorator(Controller, ensure=True)


# ***
# *** [VERSION] Version command helper.
# ***


def _hamster_version():
    vers = '{} version {}\nhamster-lib version {}'.format(
        hamster_cli_appname,
        hamster_cli_version,
        hamster_lib_version,
    )
    return vers


# ***
# *** [BASE COMMAND GROUP] One Group to rule them all.
# ***

# (lb): Use invoke_without_command so `hamster -v` works, otherwise click's
# Group (MultiCommand ancestor) does not allow it ('Missing command.').
@click.group(
    cls=ClickAliasedGroup,
    invoke_without_command=True,
    help=help_strings.RUN_HELP,
)
@click.version_option(message=_hamster_version())
@click.option('-v', is_flag=True, help=help_strings.VERSION_HELP)
@pass_controller
@click.pass_context
# NOTE: @click.group transforms this func. definition into a callback that
#       we use as a decorator for the top-level commands (see: @run.command).
def run(ctx, controller, v):
    """General context run right before any of the commands."""

    def _run(ctx, controller, show_version):
        """Make sure that loggers are setup properly."""
        _run_handle_paging(controller)
        _run_handle_banner()
        _run_handle_version(show_version, ctx)
        _run_handle_without_command(ctx)
        _setup_logging(controller)

    def _run_handle_paging(controller):
        if controller.client_config['term_paging']:
            # FIXME/2018-04-22: (lb): Well, actually, don't clear, but rely on paging...
            #   after implementing paging. (Also add --paging option.)
            click.clear()

    def _run_handle_banner():
        # FIXME/2018-04-22: (lb): I disabled the _show_greeting code;
        #                   it's not useful info. And a little boastful.
        # Instead, we could maybe make a hamster-about command?
        #   _show_greeting()
        pass

    def _run_handle_version(show_version, ctx):
        if show_version:
            click.echo(_hamster_version())
            ctx.exit(0)

    def _run_handle_without_command(ctx):
        if len(sys.argv) == 1:
            # Because invoke_without_command, we have to check ourselves
            click.echo(ctx.get_help())

    # Shim to the private run() functions.

    _run(ctx, controller, show_version=v)


def _show_greeting():
    """Display a greeting message providing basic set of information."""
    # 2018-04-22: (lb): It seems to me there are no i18n/l10n files for gettext/_.
    click.echo(_("Welcome to 'hamster_cli', your friendly time tracker for the command line."))
    click.echo("Copyright (C) 2015-2016, Eric Goller <elbenfreund@DenkenInEchtzeit.net>")
    click.echo(_(
        "'hamster_cli' is published under the terms of the GPL3, for details please use"
        " the 'license' command."
    ))
    click.echo()


def _setup_logging(controller):
    """Setup logging for the lib_logger as well as client specific logging."""
    controller.client_logger = logging.getLogger('hamster_cli')
    loggers = [
        controller.lib_logger,
        controller.sql_logger,
        controller.client_logger,
    ]
    # Clear any existing (null)Handlers, and set the level.
    # MAYBE: Allow user to specify different levels for different loggers.
    log_level = controller.client_config['log_level']
    for logger in loggers:
        logger.handlers = []
        logger.setLevel(log_level)

    formatter = logging_helpers.formatter_basic()

    if controller.client_config['log_console']:
        console_handler = logging.StreamHandler()
        logging_helpers.setupHandler(console_handler, formatter, *loggers)

    if controller.client_config['logfile_path']:
        filename = controller.client_config['logfile_path']
        file_handler = logging.FileHandler(filename, encoding='utf-8')
        logging_helpers.setupHandler(file_handler, formatter, *loggers)


def _disable_logging(controller):
    loggers = [
        controller.lib_logger,
        controller.sql_logger,
        controller.client_logger,
    ]
    for logger in loggers:
        logger.handlers = []
        logger.setLevel(logging.NOTSET)


# ***
# *** [VERSION] Ye rote version command.
# ***

@run.command(help=help_strings.VERSION_HELP)
def version():
    """Show version information."""
    _version()


def _version():
    """Show version information."""
    click.echo(_hamster_version())


# ***
# *** [LICENSE] Command.
# ***

# FIXME/MAYBE/2018-05-11 20:57: Rename this hamster-about? Then it's 1st alphabetically.
#                               And you could add a link to the project page?
#                               Seems weird to have a license command anyway, though!
@run.command(hidden=True, help=help_strings.LICENSE_HELP)
def license():
    """Show license information."""
    _license()


def _license():
    """Show license information."""
    # FIXME: (lb): Replace appname with $0, or share module var with setup.py.
    # MAYBE: (lb): Read and print LICENSE file instead of hard coding herein?
    license = """
        'hamster_cli' is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        'hamster_cli' is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with .  If not, see <http://www.gnu.org/licenses/>.
        """
    click.echo(license)


# ***
# *** [DETAILS] Command [about paths, config, etc.].
# ***


@run.command(help=help_strings.DETAILS_HELP)
@pass_controller
def details(controller):
    """List details about the runtime environment."""
    app_details(controller)


# ***
# *** [LIST] Commands.
# ***

# Use a command alias to avoid conflict with builtin of same name
# (i.e., we cannot declare this function, `def list()`).
@run.group('list', help=help_strings.LIST_GROUP_HELP)
@pass_controller
@click.pass_context
def list_group(ctx, controller):
    """Base `list` group command run prior to any of the hamster-list commands."""
    pass


# *** ACTIVITIES.

@list_group.command('activities', help=help_strings.LIST_ACTIVITIES_HELP)
@click.argument('search_term', default='')
@click.option('-c', '--category', help="The search string applied to category names.")
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def list_activities(controller, *args, **kwargs):
    """List all activities. Provide optional filtering by name."""
    category = kwargs['category'] if kwargs['category'] else ''
    del kwargs['category']
    cmd_options.postprocess_options_table_bunce(kwargs)
    list_activity.list_activities(
        controller,
        *args,
        filter_category=category,
        **kwargs
    )


# *** CATEGORIES.

@list_group.command('categories', help=help_strings.LIST_CATEGORIES_HELP)
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def list_categories(controller, *args, **kwargs):
    """List all existing categories, ordered by name."""
    list_category.list_categories(controller)


# *** TAGS.

@list_group.command('tags', help=help_strings.LIST_TAGS_HELP)
@click.argument('search_term', default='')
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def list_tags(controller, *args, **kwargs):
    """List all tags, with filtering and sorting options."""
    cmd_options.postprocess_options_table_bunce(kwargs)
    list_tag.list_tags(controller, *args, **kwargs)


# *** FACTS (w/ time range).
# FIXME/2018-05-12: (lb): Do we really need 2 Facts search commands?

@list_group.command('facts', help=help_strings.LIST_FACTS_HELP)
@cmd_options_search
@cmd_options_limit_offset
@pass_controller
def list_facts(controller, *args, **kwargs):
    """List all facts within a timerange."""
    results = search_facts(controller, *args, **kwargs)
    table, headers = generate_facts_table(results)
    click.echo(generate_table(table, headers=headers))
    warn_if_truncated(controller, len(results), len(table))



@run.command(help=help_strings.SEARCH_HELP)
@click.argument('search_term', nargs=-1, default=None)
# MAYBE/2018-05-05: (lb): Restore the time_range arg scientificsteve removed:
#  @click.argument('time_range', default='')
@cmd_options_search
@cmd_options_limit_offset
@click.option('-a', '--activity', help="The search string applied to activity names.")
@click.option('-c', '--category', help="The search string applied to category names.")
@click.option('-t', '--tag', help='The tags search string (e.g. "tag1 AND (tag2 OR tag3)".')
@click.option('-d', '--description',
              help='The description search string (e.g. "string1 OR (string2 AND string3).')
@click.option('-k', '--key', help='The database key of the fact.')
@pass_controller
def search(controller, description, search_term, *args, **kwargs):
    """Fetch facts matching certain criteria."""
    # [FIXME]
    # Check what we actually match against.
    # NOTE: (lb): Before scientificsteve added all the --options, the
    #       original command accepted a search_term and a time_range,
    #       e.g.,
    #
    #         @click.argument('search_term', default='')
    #         @click.argument('time_range', default='')
    #         def search(controller, search_term, time_range):
    #           return search_facts(controller, search_term, time_range)
    #           # And then the table and click.echo were at the bottom of
    #           # search_facts! And I'm not sure why they were moved here....
    #
    #       MAYBE: Restore supprt for time_range, i.e., let user specify
    #       2 positional args in addition to any number of options. And
    #       figure out why the generate-table and click.echo were moved
    #       here?
    if search_term:
        description = description or ''
        description += ' AND ' if description else ''
        description += ' AND '.join(search_term)
    results = search_facts(description, *args, **kwargs)
    table, headers = generate_facts_table(results)
    click.echo(generate_table(table, headers=headers))
    warn_if_truncated(controller, len(results), len(table))


# ***
# *** [USAGE] Commands.
# ***

@run.group('usage', help=help_strings.USAGE_GROUP_HELP)
@pass_controller
@click.pass_context
def usage_group(ctx, controller):
    """Base `usage` group command run prior to any of the hamster-usage commands."""
    pass


# *** ACTIVITIES.

@usage_group.command('activities', help=help_strings.USAGE_ACTIVITIES_HELP)
@click.argument('search_term', default='')
@click.option('-c', '--category', help="Filter results by category name.")
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def usage_activities(controller, *args, **kwargs):
    """List all activities. Provide optional filtering by name."""

    # This little dance is so category_name is never None, but '',
    # because get_all() distinguishes between category=None and =''.
    category = kwargs['category'] if kwargs['category'] else ''
    del kwargs['category']

    cmd_options.postprocess_options_table_bunce(kwargs)

    usage_activity.usage_activities(
        controller,
        *args,
        filter_category=category,
        **kwargs
    )


# *** CATEGORIES.

@usage_group.command('categories', help=help_strings.USAGE_CATEGORIES_HELP)
@click.argument('search_term', default='')
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def usage_categories(controller, *args, **kwargs):
    """List all categories. Provide optional filtering by name."""
    cmd_options.postprocess_options_table_bunce(kwargs)
    usage_category.usage_categories(
        controller,
        *args,
        **kwargs
    )


# *** TAGS.

@usage_group.command('tags', help=help_strings.USAGE_TAGS_HELP)
@click.argument('search_term', default='')
@cmd_options_table_bunce
@cmd_options_limit_offset
@pass_controller
def usage_tags(controller, *args, **kwargs):
    """List all tags' usage counts, with filtering and sorting options."""

    cmd_options.postprocess_options_table_bunce(kwargs)

    usage_tag.usage_tags(controller, *args, **kwargs)


# ***
# *** [CURRENT-FACT] Commands: start/stop/cancel/current.
# ***


@run.command(help=help_strings.START_HELP)
@click.argument('raw_fact')
@click.argument('start', default='')
@click.argument('end', default='')
@pass_controller
def start(controller, raw_fact, start, end):
    """Start or add a fact."""
    # [FIXME]
    # The original semantics do not work anymore. As we make a clear difference
    # between *adding* a (complete) fact and *starting* a (ongoing) fact.
    # This needs to be reflected in this command.
    start_fact(controller, raw_fact, start, end)


@run.command(help=help_strings.STOP_HELP)
@pass_controller
def stop(controller):
    """Stop tracking current fact. Saving the result."""
    stop_fact(controller)


@run.command(help=help_strings.CANCEL_HELP)
@pass_controller
def cancel(controller):
    """Cancel 'ongoing fact'. E.g stop it without storing in the backend."""
    cancel_fact(controller)


@run.command(help=help_strings.CURRENT_HELP)
@pass_controller
def current(controller):
    """Display current *ongoing fact*."""
    list_current_fact(controller)


# ***
# *** [CREATE-FACT] Commands.
# ***


@run.command(help=help_strings.START_HELP_ON, aliases=['now'])
@cmd_options_insert
@pass_controller
def on(controller, factoid, yes, ask):
    """Start or add a fact using the `on`/`now` directive."""
    add_fact(controller, factoid, time_hint='verify-none', yes=yes, ask=ask)


@run.command(help=help_strings.START_HELP_AT)
@cmd_options_insert
@pass_controller
def at(controller, factoid, yes, ask):
    """Start or add a fact using the `at` directive."""
    add_fact(controller, factoid, time_hint='verify-start', yes=yes, ask=ask)


@run.command(help=help_strings.START_HELP_TO, aliases=['until'])
@cmd_options_insert
@pass_controller
def to(controller, factoid, yes, ask):
    """Start or add a fact using the `to`/`until` directive."""
    add_fact(controller, factoid, time_hint='verify-end', yes=yes, ask=ask)


# (lb): We cannot name the function `from`, which is a Python reserved word,
# so set the command name via the composable group command() decorator.
@run.command('from', help=help_strings.START_HELP_BETWEEN)
@cmd_options_insert
@pass_controller
def between(controller, factoid, yes, ask):
    """Add a fact using the `from ... to` directive."""
    add_fact(controller, factoid, time_hint='verify-both', yes=yes, ask=ask)


# ***
# *** [EDIT] Command(s).
# ***

@run.group('edit', help=help_strings.EDIT_GROUP_HELP)
@pass_controller
@click.pass_context
def edit_group(ctx, controller):
    """Base `edit` group command run prior to any of the hamster-edit commands."""
    pass


# *** FACTS.

@edit_group.command('fact', help=help_strings.EDIT_FACT_HELP)
@click.argument('key', nargs=1)
@pass_controller
def edit_fact(controller, *args, **kwargs):
    """Inline-Edit specified Fact using preferred $EDITOR."""
    update.edit_fact(controller, *args, **kwargs)


# ***
# *** [EXPORT] Command.
# ***


@run.command(help=help_strings.EXPORT_HELP)
@click.argument('format', nargs=1, default='csv')
@click.argument('start', nargs=1, default='')
@click.argument('end', nargs=1, default='')
@click.option('-a', '--activity', help="The search string applied to activity names.")
@click.option('-c', '--category', help="The search string applied to category names.")
@click.option('-t', '--tag', help='The tags search string (e.g. "tag1 AND (tag2 OR tag3)".')
@click.option('-d', '--description',
              help='The description search string (e.g. "string1 OR (string2 AND string3).')
@click.option('-k', '--key', help='The database key of the fact.')
@click.option('-f', '--filename', help="The filename where to store the export file.")
@pass_controller
def export(controller, format, start, end, activity, category, tag, description, key, filename):
    """Export all facts of within a given timewindow to a file of specified format."""
    export_facts(controller, format, start, end, activity, category, tag, description, key, filename)


# ***
# *** [COMPLETE] Command [Bash tab completion].
# ***


# FIXME: YAS! `hidden` is from a branch at:
#          sstaszkiewicz-copperleaf:6.x-maintenance
#        Watch the PR, lest you want to remove this before publishing:
#          https://github.com/pallets/click/pull/985
#          https://github.com/pallets/click/pull/500
@run.command('complete', hidden=True, help=help_strings.COMPLETE_HELP)
@pass_controller
def complete(controller):
    """Bash tab-completion helper."""
    _disable_logging(controller)
    tab_complete(controller)


# ***
# *** [MIGRATE] Commands [database transformations].
# ***

@run.group('migrate', help=help_strings.MIGRATE_GROUP_HELP)
@pass_controller
@click.pass_context
def migrate_group(ctx, controller):
    """Base `migrate` group command run prior to any of the hamster-migrate commands."""
    pass


@migrate_group.command('down', help=help_strings.MIGRATE_DOWN_HELP)
@pass_controller
def migrate_downgrade(controller):
    """Downgrade the database according to its migration version."""
    migrate.downgrade(controller)


@migrate_group.command('up', help=help_strings.MIGRATE_UP_HELP)
@pass_controller
def migrate_upgrade(controller):
    """Upgrade the database according to its migration version."""
    migrate.upgrade(controller)


@migrate_group.command('version', help=help_strings.MIGRATE_VERSION_HELP)
@pass_controller
def migrate_version(controller):
    """Show migration information about the database."""
    migrate.version(controller)

