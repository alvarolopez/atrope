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
import pprint

from oslo.config import cfg
import requests
import yaml

from atrope import exception
from atrope import image
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

cli_opts = [
    cfg.StrOpt('index',
               help="Show the configured image lists",
               positional=True),
]

CONF = cfg.CONF
CONF.register_opts(opts)
CONF.register_cli_opts(cli_opts, group='imagelist')



# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ImageList(object):
    """An image list."""

    def __init__(self, name, url=None, enabled=True, endorser={}, token=None):
        self.name = name

        self.url = url
        self.token = token

        self.enabled = enabled

        self.endorser = endorser
        self.signers = None
        self.verified = False
        self.trusted = False

        self.contents = None
        self.d_contents = {}

        self.images = []

    def fetch(self):
        if self.enabled and self.url:
            self.contents = self._fetch()
            self.verified, self.signers, raw_list = self._verify()
            # FIXME(aloga): We should check that the JSON is valid, and that
            # load the data into the object.
            try:
                self.d_contents = json.loads(raw_list)
            except ValueError:
                raise exception.InvalidImageList(reason="Invalid JSON.")

            img_list = self.d_contents.get("hv:imagelist", {})
            for img in img_list.get("hv:images"):
                self.images.append(image.VMCasterImage(img))

            self.trusted = self._check_endorser()

    def __repr__(self):
        return "<%s: %s>" % (
            self.__class__.__name__,
            self.name
        )

    def _fetch(self):
        """
        Get the image list from the server.

        If it is needed, use a token to authenticate against the server.

        :returns: the image list.
        :raises: exception.ImageListDownloadFailed if it is not possible to get
                 the image.
        """
        if self.token:
            auth = (self.token, 'x-oauth-basic')
        else:
            auth = None
        response = requests.get(self.url, auth=auth)
        if response.status_code != 200:
            raise exception.ImageListDownloadFailed(code=response.status_code,
                                                    reason=response.reason)
        else:
            return response.content

    def _verify(self):
        """
        Verify the image list SMIME signature.

        :returns: tuple (signers, raw_list) with the signers and the raw list.
        :raises: exception.SMIMEValidationError if it is not possible to verify
                 the signature.
        """
        verifier = smime.SMIMEVerifier()
        try:
            signers, raw_list = verifier.verify(self.contents)
        except Exception as e:
            raise e
        else:
            return True, signers, raw_list

    def _check_endorser(self):
        """
        Check the endorsers of an image list.

        :returns: True of False if endorsers are trusted or not.
        """

        # FIXME(aloga): This should be in its own class
        list_endorser = self.d_contents.get("hv:imagelist", {})
        list_endorser = list_endorser.get("hv:endorser", {})
        list_endorser = list_endorser.get("hv:x509", {})
        if not all(i in list_endorser for i in ("hv:ca", "hv:dn")):
            logging.error("List '%s' does not contain a valid endorser" %
                          self.name)
            return False

        if self.endorser["dn"] != list_endorser["hv:dn"]:
            logging.error("List '%s' endorser is not trusted, DN mismatch "
                          "%s != %s" % (self.name, self.endorser["dn"],
                                        list_endorser["hv:dn"]))
            return False

        if self.endorser["ca"] != list_endorser["hv:ca"]:
            logging.error("List '%s' endorser CA is invalid "
                          "%s != %s" % (self.name, self.endorser["ca"],
                                        list_endorser["hv:ca"]))
            return False
        return True

    def print_list(self, contents=False):
        d = {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            # FIXME(aloga): objectify endorser
            "endorser_dn": self.endorser.get("dn", None),
            "endorser_ca": self.endorser.get("ca", None),
        }
        d["verified"] = self.verified
        d["trusted"] = self.trusted
        d["token set"] = self.token and True
        if self.contents is not None and contents:
            d["contents"] = pprint.pformat(self.d_contents)

        utils.print_dict(d)


class ImageListManager(object):
    def __init__(self):
        utils.makedirs(CONF.lists_path)

        self.configured_lists = {}
        self.loaded_lists = None

        with open(CONF.image_lists, "rb") as f:
            image_lists = yaml.safe_load(f)

        for name, list_meta in image_lists.iteritems():
            l = ImageList(name,
                          url=list_meta.get("url", None),
                          enabled=list_meta.get("enabled", True),
                          endorser=list_meta.get("endorser", {}),
                          token=list_meta.get("token", None))
            self.configured_lists[name] = l

    def _fetch_and_verify(self, l):
        """
        Fetch and verify an image list.

        If there are errors loading the list the appropriate attributes won't
        be set, so there is no need to fail here, but rather return the list.
        """
        try:
            l.fetch()
        except exception.AtropeException as e:
            logging.error("Error loading list '%s', reason: %s" %
                            (l.name, e.message))
            logging.debug("Exception while downloading list '%s'" % l.name,
                            exc_info=e)
        return l

    def fetch_list(self, image_list):
        """Get an individual list."""
        l = self.configured_lists.get(image_list)
        if l is None:
            raise exception.InvalidImageList(reason="not found in configuration")
        return self._fetch_and_verify(l)

    def fetch_lists(self):
        """Get all the configured lists."""
        all_lists = []
        for l in self.configured_lists.values():
            l = self._fetch_and_verify(l)
            all_lists.append(l)

        return all_lists

    def load_lists(self):
        if self.loaded_lists is None:
            self.loaded_lists = self.fetch_lists()
