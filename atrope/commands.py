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

import sys

from atrope import exception
import atrope.image_list
from atrope import utils

from oslo.config import cfg

CONF = cfg.CONF


def add_command_parsers(subparsers):
    CommandImageListAdd(subparsers)
    CommandImageListIndex(subparsers)
    CommandImageListFetch(subparsers)
#    CommandImageListCache(subparsers)

command_opt = cfg.SubCommandOpt('command',
                                title='Commands',
                                help='Show available commands.',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)


class Command(object):
    def __init__(self, parser, name, cmd_help):
        self.name = name
        self.cmd_help = cmd_help
        self.parser = parser.add_parser(name, help=cmd_help)
        self.parser.set_defaults(func=self.run)

    def run(self):
        raise NotImplementedError("Method must me overriden on subclass")


class CommandImageListAdd(Command):
    def __init__(self, parser, name="imagelist-add",
                 cmd_help="Add a list to the configured image lists"):
        super(CommandImageListAdd, self).__init__(parser, name, cmd_help)

        self.parser.add_argument("list_id",
                                 default=None,
                                 nargs='?',
                                 help="List ID to add.")

        self.parser.add_argument("-u",
                                 "--url",
                                 dest="url",
                                 metavar="URL",
                                 default="",
                                 help="List URL")

        self.parser.add_argument("-o",
                                 "--endorser_dn",
                                 dest="endorser_dn",
                                 metavar="DN",
                                 default="",
                                 help="Endorser's DN")

        self.parser.add_argument("-c",
                                 "--endorser_ca",
                                 dest="endorser_ca",
                                 metavar="CA DN",
                                 default="",
                                 help="Endorser's CA DN")

        self.parser.add_argument("-t",
                                 "--token",
                                 dest="token",
                                 metavar="TOKEN",
                                 default="",
                                 help="Access token to use")

        self.parser.add_argument("-f",
                                 "--force",
                                 dest="force",
                                 default=False,
                                 action="store_true",
                                 help="Overwrite list if it exists")

        group = self.parser.add_mutually_exclusive_group()
        group.add_argument("-e",
                           "--enabled",
                           dest="enabled",
                           default=True,
                           action="store_true",
                           help="Add list as enabled (default)")

        group.add_argument("-d",
                           "--disabled",
                           dest="enabled",
                           action="store_false",
                           help="Add list as disabled")

    def _get_values(self, url, token, enabled, endorser):
        def get_endorser(default={}):
            print "Enter endorser details."
            dn = raw_input("\tEndorser DN [%s]: " %
                           default.get("dn", "")) or default.get("dn")
            if not dn:
                return {}

            ca = raw_input("\tEndorser CA [%s]: " %
                           default.get("ca", "")) or default.get("ca")
            if not ca:
                print "CA cannot be empty, try again."
                return get_endorser(default={"dn": dn})

            return {"dn": dn, "ca": ca}

        def get_str(msg, mandatory=False, default=""):
            identifier = raw_input("%s [%s]: " % (msg, default)) or default
            if not identifier and mandatory:
                raise exception.MissingMandatoryFieldImageList(field=msg)
            return identifier

        def print_image(identifier, url, token, enabled, endorser):
            d = {
                "identifier": identifier,
                "url": url,
                "token": token,
                "enabled": enabled,
                "endorser dn": endorser.get("dn"),
                "endorser ca": endorser.get("ca"),
            }
            utils.print_dict(d)

        identifier = ""
        while True:
            identifier = get_str("list id", mandatory=True, default=identifier)
            url = get_str("list URL", default=url)
            enabled = utils.yn_question(default=enabled)
            endorser = get_endorser(default=endorser)

            token = get_str("token", default=token)

            print_image(identifier, url, token, enabled, endorser)
            msg = "Is the information above correct?"
            correct = utils.yn_question(msg=msg)
            if correct:
                break
            print
            print "OK, lets try again"

        return identifier, url, enabled, endorser, token

    def run(self):
        identifier = CONF.command.list_id
        url = CONF.command.url
        token = CONF.command.token
        enabled = CONF.command.enabled
        force = CONF.command.force
        endorser_dn = CONF.command.endorser_dn
        endorser_ca = CONF.command.endorser_ca
        if (endorser_dn is "") == (endorser_ca is ""):
            if CONF.command.endorser_dn:
                endorser = {"dn": endorser_dn,
                            "ca": endorser_ca}
            else:
                endorser = {}

        if identifier is None:
            self.add_interative(url, token, enabled, endorser, force)
        else:
            self.add_non_interactive(identifier, url, token,
                                     enabled, endorser, force)

    def add_non_interactive(self, identifier, url, token,
                            enabled, endorser, force):
        image_list = atrope.image_list.source.ImageListSource(
            identifier,
            url,
            enabled=enabled,
            endorser=endorser,
            token=token
        )

        manager = atrope.image_list.manager.YamlImageListManager()
        manager.add_image_list_source(image_list, force=force)
        manager.write_image_list_sources()

    def add_interative(self, url, token, enabled, endorser, force):
        print "Adding image list, enter the following details (Ctr+C to exit)"
        identifier, url, enabled, endorser, token = self._get_values(url,
                                                                     token,
                                                                     enabled,
                                                                     endorser)
        image_list = atrope.image_list.source.ImageListSource(
            identifier,
            url,
            enabled=enabled,
            endorser=endorser,
            token=token
        )

        manager = atrope.image_list.manager.YamlImageListManager()
        try:
            manager.add_image_list_source(image_list, force=force)
            manager.write_image_list_sources()
        except exception.DuplicatedImageList:
            msg = "Image with id '%s' already in index, update?" % identifier
            force = utils.yn_question(msg)
            if force:
                manager.add_image_list_source(image_list, force=True)
                manager.write_image_list_sources()


class CommandImageListIndex(Command):
    def __init__(self, parser, name="imagelist-index",
                 cmd_help="Show the configured image lists"):
        super(CommandImageListIndex, self).__init__(parser, name, cmd_help)

    def run(self):
        manager = atrope.image_list.manager.YamlImageListManager()
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
        manager = atrope.image_list.manager.YamlImageListManager()
        if CONF.command.list is not None:
            lists = [manager.fetch_list(CONF.command.list)]
        else:
            lists = manager.fetch_lists()

        for l in lists:
            l.print_list(contents=CONF.command.contents)


#class CommandImageListCache(Command):
#    def __init__(self, parser, name="cache-sync",
#                 cmd_help="Sync cache directory."):
#        super(CommandImageListCache, self).__init__(parser, name, cmd_help)
#
#    def run(self):
#        manager = atrope.image_list.manager.YamlImageListManager()
#        manager.sync_cache()


class CommandManager(object):
    def execute(self):
        try:
            CONF.command.func()
        except exception.AtropeException as e:
            print >> sys.stderr, "ERROR: %s" % e
            sys.exit(1)
        except KeyboardInterrupt:
            print >> sys.stderr, "\nExiting..."
            sys.exit(0)
