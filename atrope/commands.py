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
import atrope.image_list.manager
from atrope import utils

from oslo_config import cfg
from six.moves import input

CONF = cfg.CONF


def add_command_parsers(subparsers):
    CommandImageListAdd(subparsers)
    CommandImageListIndex(subparsers)
    CommandImageListFetch(subparsers)
    CommandImageListCache(subparsers)
    CommandDispatch(subparsers)


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

        self.parser.add_argument("-p",
                                 "--prefix",
                                 dest="prefix",
                                 metavar="PREFIX",
                                 default="",
                                 help="If set images names will be prefixed "
                                      "with this.")

        self.parser.add_argument("-P",
                                 "--project",
                                 dest="project",
                                 metavar="PROJECT",
                                 default="",
                                 help="OpenStack project to which these "
                                      "images will be associated.")

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

    def _get_values(self, url, token, prefix, enabled, endorser, project):
        def get_endorser(default={}):
            print("Enter endorser details.")
            dn = input("\tEndorser DN [%s]: " %
                       default.get("dn", "")) or default.get("dn")
            if not dn:
                return {}

            ca = input("\tEndorser CA [%s]: " %
                       default.get("ca", "")) or default.get("ca")
            if not ca:
                print("CA cannot be empty, try again.")
                return get_endorser(default={"dn": dn})

            return {"dn": dn, "ca": ca}

        def get_str(msg, mandatory=False, default=""):
            identifier = input("%s [%s]: " % (msg, default)) or default
            if not identifier and mandatory:
                raise exception.MissingMandatoryFieldImageList(field=msg)
            return identifier

        def get_list(msg, mandatory=False):
            print(msg)
            print("\t(one value per line, empty to finish)")
            ret = []
            el = None
            while True:
                el = input("\timage id: ")
                if not el:
                    break
                ret.append(el)

            if not ret and mandatory:
                raise exception.MissingMandatoryFieldImageList(field=msg)
            return ret

        def print_image_list(identifier, url, token, prefix, enabled,
                             endorser, subscribed_images, project):
            d = {
                "identifier": identifier,
                "url": url,
                "token": token,
                "prefix": prefix,
                "enabled": enabled,
                "endorser dn": endorser.get("dn"),
                "endorser ca": endorser.get("ca"),
                "subscribed images": subscribed_images,
                "project": project,
            }
            utils.print_dict(d)

        identifier = ""
        while True:
            identifier = get_str("list id", mandatory=True, default=identifier)
            url = get_str("list URL", default=url)
            enabled = utils.yn_question(default=enabled)
            endorser = get_endorser(default=endorser)

            token = get_str("auth token", default=token)

            prefix = get_str("prefix", default=prefix)

            project = get_str("project", default="")

            subscribed_images = get_list("subscribed images")

            print_image_list(identifier, url, token, prefix, enabled,
                             endorser, subscribed_images, project)
            msg = "Is the information above correct?"
            correct = utils.yn_question(msg=msg)
            if correct:
                break
            print("\nOK, lets try again")

        return (identifier, url, enabled, endorser,
                token, prefix, subscribed_images, project)

    def run(self):
        identifier = CONF.command.list_id
        url = CONF.command.url
        token = CONF.command.token
        prefix = CONF.command.prefix
        enabled = CONF.command.enabled
        force = CONF.command.force
        endorser_dn = CONF.command.endorser_dn
        endorser_ca = CONF.command.endorser_ca
        project = CONF.command.project
        if (endorser_dn == "") == (endorser_ca == ""):
            if CONF.command.endorser_dn:
                endorser = {"dn": endorser_dn,
                            "ca": endorser_ca}
            else:
                endorser = {}

        if identifier is None:
            self.add_interative(url, token, prefix, enabled, endorser,
                                project, force)
        else:
            self.add_non_interactive(identifier, url, token, prefix, enabled,
                                     endorser, project, force)

    def add_non_interactive(self, identifier, url, token, prefix, enabled,
                            endorser, project, force):
        image_list = atrope.image_list.hepix.HepixImageListSource(
            identifier,
            url,
            enabled=enabled,
            endorser=endorser,
            token=token,
            prefix=prefix,
            project=project
        )

        manager = atrope.image_list.manager.YamlImageListManager()
        manager.add_image_list_source(image_list, force=force)
        manager.write_image_list_sources()

    def add_interative(self, url, token, prefix, enabled, endorser,
                       project, force):
        print("Adding image list, enter the following details (Ctr+C to exit)")
        (identifier, url, enabled, endorser, token, prefix,
         subscribed_images, project) = self._get_values(url, token, prefix,
                                                        enabled, endorser,
                                                        project)
        image_list = atrope.image_list.hepix.HepixImageListSource(
            identifier,
            url,
            enabled=enabled,
            endorser=endorser,
            token=token,
            prefix=prefix,
            subscribed_images=subscribed_images
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
        for lst in manager.lists.values():
            d = {}
            for f in fields:
                d[f] = getattr(lst, f)
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

        for lst in lists:
            lst.print_list(contents=CONF.command.contents)


class CommandImageListCache(Command):
    def __init__(self, parser, name="cache-sync",
                 cmd_help="Sync cache directory."):
        super(CommandImageListCache, self).__init__(parser, name, cmd_help)

    def run(self):
        manager = atrope.image_list.manager.YamlImageListManager()
        manager.sync_cache()


class CommandDispatch(Command):
    def __init__(self, parser, name="dispatch",
                 cmd_help="Dispatch (help TBD)."):
        super(CommandDispatch, self).__init__(parser, name, cmd_help)

        self.parser.add_argument("-n",
                                 "--no-sync",
                                 dest="sync",
                                 default=True,
                                 action="store_false",
                                 help="Do not sync image list with "
                                      "dispatched data")

    def run(self):
        manager = atrope.image_list.manager.YamlImageListManager()
        manager.sync_cache()
        manager.dispatch(CONF.command.sync)


class CommandManager(object):
    def execute(self):
        try:
            CONF.command.func()
        except exception.AtropeException as e:
            print("ERROR: %s" % e, file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nExiting...", file=sys.stderr)
            sys.exit(0)
