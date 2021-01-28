# -*- coding: utf-8 -*-

# Copyright 2021 Alvaro Lopez Garcia
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

from atrope.cmd import base
from atrope.image_list import manager
from atrope import utils

from oslo_config import cfg

CONF = cfg.CONF


class BaseImageListCommand(base.BaseCommand):
    def __init__(self, *args, **kwargs):
        super(BaseImageListCommand, self).__init__(*args, **kwargs)
        self._manager = None

    @property
    def manager(self):
        if self._manager is None:
            self._manager = manager.YamlImageListManager()
        return self._manager


class CommandImageListIndex(BaseImageListCommand):
    def __init__(self, parser, name="index",
                 cmd_help="Show the configured image lists."):
        super(CommandImageListIndex, self).__init__(parser, name, cmd_help)

    def run(self):
        fields = ["name", "url", "enabled", "endorser"]
        objs = []
        for lst in self.manager.lists.values():
            d = {}
            for f in fields:
                aux = getattr(lst, f)
                if isinstance(aux, dict):
                    aux = "\n".join([f"{k}: {v}" for k, v in aux.items()])
                d[f] = aux
            objs.append(d)
        utils.print_list(objs, fields)


class CommandImageListFetch(BaseImageListCommand):
    def __init__(self, parser, name="verify",
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
        the_list = CONF.command.list
        show_contents = CONF.command.contents
        if the_list is not None:
            lists = [self.manager.fetch_list(the_list)]
        else:
            lists = self.manager.fetch_lists()

        for lst in lists:
            lst.print_list(contents=show_contents)


class CommandImageListCache(BaseImageListCommand):
    def __init__(self, parser, name="cache",
                 cmd_help="Download images from configured image lists."):
        super(CommandImageListCache, self).__init__(parser, name, cmd_help)

    def run(self):
        self.manager.cache()


class CommandDispatch(BaseImageListCommand):
    def __init__(self, parser, name="sync",
                 cmd_help="Download images from configured image lists "
                          "and sync them to the available dispatchers."):
        super(CommandDispatch, self).__init__(parser, name, cmd_help)

    def run(self):
        self.manager.sync()
