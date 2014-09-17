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

import atrope.image_list
from atrope import utils

import prettytable
from oslo.config import cfg

CONF = cfg.CONF


def add_command_parsers(subparsers):
    CommandImageListIndex(subparsers)
    CommandImageListFetch(subparsers)

command_opt = cfg.SubCommandOpt('command',
                                title='Commands',
                                help='Show available commands.',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)


class Command(object):
    def __init__(self, parser, name, cmd_help):
        self.name = name
        self.cmd_help = cmd_help
        self.parser = parser.add_parser(name,
                                            help=cmd_help)
        self.parser.set_defaults(func=self.run)

    def run(self):
        raise NotImplementedError("Method must me overriden on subclass")


class CommandImageListIndex(Command):
    def __init__(self, parser, name="imagelist-index",
                 cmd_help="Show the configured image lists"):
        super(CommandImageListIndex, self).__init__(parser, name, cmd_help)

    def run(self):
        manager = atrope.image_list.ImageListManager()
        # TODO(aloga): wrap the fields, since the output is huge
        fields = ["name", "url", "enabled", "endorser"]
        objs = []
        for l in manager.configured_lists.values():
            d = {}
            for f in fields:
                d[f] = getattr(l, f)
            objs.append(d)
        utils.print_list(objs, fields)


class CommandImageListFetch(Command):
    def __init__(self, parser, name="imagelist-fetch",
                 cmd_help="Fetch and verify the configured image lists."):
        super(CommandImageListFetch, self).__init__(parser, name, cmd_help)

        self.parser.add_argument("-c",
                                 "--contents",
                                 dest="contents",
                                 default=False,
                                 action="store_true",
                                 help="Show the list contents")

        self.parser.add_argument("list",
                                 default=None,
                                 nargs='?',
                                 help="Image list to fetch.")

    def run(self):
        manager = atrope.image_list.ImageListManager()
        if CONF.command.list is not None:
            lists = [manager.fetch_list(CONF.command.list)]
        else:
            lists = manager.fetch_lists()

        for l in lists:
            l.print_list(contents=CONF.command.contents)


#class CommandImageListDownload(Command):
#    def __init__(self, parser, name="imagelist-download",
#                 cmd_help="Fetch the configured image lists"):
#        super(CommandImageListFetch, self).__init__(parser, name, cmd_help)
#
#    def run(self):
#        manager = atrope.image_list.ImageListManager()
#        manager.fetch_lists()


class CommandManager(object):
    def execute(self):
        CONF.command.func()
