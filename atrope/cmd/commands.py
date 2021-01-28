# -*- coding: utf-8 -*-

# Copyright 2014 Alvaro Lopez Garcia
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import print_function

import sys

from atrope import exception
from atrope.cmd import image_list
from atrope.cmd import version

from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF


def add_command_parsers(subparsers):
    image_list.CommandImageListIndex(subparsers)
    image_list.CommandImageListFetch(subparsers)
    image_list.CommandImageListCache(subparsers)
    image_list.CommandDispatch(subparsers)
    version.CommandVersion(subparsers)


command_opt = cfg.SubCommandOpt('command',
                                title='Commands',
                                help='Show available commands.',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)

LOG = log.getLogger(__name__)


class CommandManager(object):
    def execute(self):
        try:
            LOG.info("Atrope session starts >>>>>>>>>>")
            CONF.command.func()
        except exception.AtropeException as e:
            print("ERROR: %s" % e, file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nExiting...", file=sys.stderr)
            sys.exit(0)
        finally:
            LOG.info("Atrope session ends <<<<<<<<<<<<")
