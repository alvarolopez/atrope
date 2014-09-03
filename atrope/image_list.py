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

import logging
import os.path

from oslo.config import cfg
import requests
import yaml

from atrope import paths
from atrope import utils

opts = [
    cfg.StrOpt('image_lists',
               default='/etc/atrope/lists.yaml',
               help='Report definition location.'),
    cfg.StrOpt('lists_path',
               default=paths.state_path_def('lists'),
               help='Where instances are stored on disk'),
    cfg.BoolOpt('cleanup_disabled_lists',
               default=True,
               help=('Wheter to remove from the state dir a list that '
                     'has been disabled.')),
]

CONF = cfg.CONF
CONF.register_opts(opts)

# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ImageLists(object):
    def __init__(self):
        utils.makedirs(CONF.lists_path)
        self._load_data()
        self._get_lists()

    def _load_data(self):
        """Load YAML image lists."""

        with open(CONF.image_lists, "rb") as f:
            self.image_lists = yaml.safe_load(f)

    def _get_lists(self):
        """Download and store the configured lists."""
        for name, list_meta in self.image_lists.iteritems():
            url = list_meta.get("url", None)
            enabled = list_meta.get("enabled", True)

            if not enabled:
                continue

            if url is None:
                logging.error("Skipping image list '%s', no url provided" % name)
                continue

            logging.debug("Getting image list '%s' from '%s'" % (name, url))

            basedir = os.path.join(CONF.lists_path, "%s.list" % name)
            utils.makedirs(basedir)

            l = requests.get(url)
            with open(os.path.join(basedir, name), 'w') as f:
                # NOTE(aloga): asume that file is small and that we
                # do not really need to stream it
                f.write(l.content)

    def _verify_list(self, *args, **kwargs):
        return True

    def _check_stored_lists(self):
        pass
        # 1. load directory contents
        # 2. traverse directory
        # 3. check against the stored lists
        #       - if list is disabled, add to disabled lists
        #       - if list is enabled and endorsed is trusted, add to enabled lists
        #       - if list is enabeld and endorser is not trusted, add to disabled lists
