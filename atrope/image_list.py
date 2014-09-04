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

import json
import logging
import os.path

from oslo.config import cfg
import requests
import yaml

from atrope import exception
from atrope import paths
from atrope import smime
from atrope import utils

opts = [
    cfg.StrOpt('image_lists',
               default='/etc/atrope/lists.yaml',
               help='Report definition location.'),
    cfg.StrOpt('lists_path',
               default=paths.state_path_def('lists'),
               help='Where instances are stored on disk'),
]

CONF = cfg.CONF
CONF.register_opts(opts)

# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ImageLists(object):
    def __init__(self):
        self.verifier = smime.SMIMEVerifier()

        utils.makedirs(CONF.lists_path)

        self.image_lists = {}
        self.valid_lists = {}

        self._load_data()
        self._get_lists()

    def _load_data(self):
        """Load YAML image lists."""

        with open(CONF.image_lists, "rb") as f:
            self.image_lists = yaml.safe_load(f)

    def _get_lists(self):
        """Download and store the configured lists."""

        self.valid_lists = {}

        for name, list_meta in self.image_lists.iteritems():
            url = list_meta.get("url", None)
            enabled = list_meta.get("enabled", True)
            endorser = list_meta.get("endorser", {})

            if not enabled:
                continue

            if url is None:
                logging.error("Skipping image list '%s', no url provided" %
                              name)
                continue

            if not all(i in endorser for i in ("dn", "ca")):
                logging.warning("List '%s' has no valid endorser, it won't "
                                "be downloaded" % name)
                continue

            logging.debug("Getting image list '%s' from '%s'" % (name, url))

            # NOTE(aloga): asume that file is small and that we
            # do not really need to stream it
            l = requests.get(url)
            try:
                signers, raw_list = self.verifier.verify(l.content)
            except exception.SMIMEValidationError as e:
                logging.error("Cannot verify list '%s' downloaded from '%s'" %
                              (name, url))
                logging.error(e)
                continue

            try:
                contents = json.loads(raw_list)
            except ValueError:
                logging.error("Cannot load list '%s', invalid JSON" % name)
                continue

            # FIXME(aloga): make checks about the list fields that are
            # needed. This code here is horrible
            list_endorser = contents.get("hv:imagelist", {})
            list_endorser = list_endorser.get("hv:endorser", {})
            list_endorser = list_endorser.get("hv:x509", {})
            if not all(i in list_endorser for i in ("hv:ca", "hv:dn")):
                logging.error("List '%s' does not contain a valid endorser" %
                              name)
                continue

            if endorser["dn"] != list_endorser["hv:dn"]:
                logging.error("List '%s' endorser is not trusted, DN "
                              "mismatch %s != %s" % (name, endorser["dn"],
                                                     list_endorser["hv:dn"]))
                continue

            if endorser["ca"] != list_endorser["hv:ca"]:
                logging.error("List '%s' endorser CA is invalid "
                              "%s != %s" % (name, endorser["ca"],
                                            list_endorser["hv:ca"]))
                continue

            basedir = os.path.join(CONF.lists_path, "%s.list" % name)
            utils.makedirs(basedir)
            with open(os.path.join(basedir, name), 'w') as f:
                f.write(l.content)

            with open(os.path.join(basedir, "%s.raw" % name), 'w') as f:
                f.write(raw_list)

            self.valid_lists[name] = {
                "signers": signers,
                "contents": contents,
            }

        logging.debug("Loaded the following lists: %s" % self.valid_lists)

    def _verify_list(self, msg):
        return True

    def _check_stored_lists(self):
        pass
        # 1. load directory contents
        # 2. traverse directory
        # 3. check against the stored lists
        #       - if list is disabled, add to disabled
        #         lists
        #       - if list is enabled and endorsed is trusted,
        #         add to enabled lists
        #       - if list is enabeld and endorser is not trusted,
        #         add to disabled lists
