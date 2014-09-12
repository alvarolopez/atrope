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

CONF = cfg.CONF
CONF.register_opts(opts)

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

        if self.enabled and self.url:
            self.content = self._get()
            self.verified, self.signers, raw_list = self._verify()
            # FIXME(aloga): We should check that the JSON is valid, and that
            # load the data into the object.
            try:
                self.d_contents = json.loads(raw_list)
            except ValueError:
                raise exception.InvalidImageList(reason="Invalid JSON.")

            img_list = self.d_contents.get("hv:imagelist", {})
            for img in img_list.get("hv:images"):
                print img
                self.images.append(image.VMCasterImage(img))

            self.trusted = self._check_endorser()

    def __repr__(self):
        return "<%s: %s>" % (
            self.__class__.__name__,
            self.name
        )

    def _get(self):
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
            signers, raw_list = verifier.verify(self.content)
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


class ImageListManager(object):
    def __init__(self):
        utils.makedirs(CONF.lists_path)

        self.image_lists = {}
        self.enabled_lists = None
        self.disabled_lists = None
        self.untrusted_lists = None

        self._load_data()
        self.get_lists()

    def _load_data(self):
        """Load YAML image lists."""

        with open(CONF.image_lists, "rb") as f:
            self.image_lists = yaml.safe_load(f)

    def _reset_lists(self):
        self.enabled_lists = []
        self.disabled_lists = []
        self.untrusted_lists = []

    def get_lists(self):
        """
        Get the configured lists that can be loaded.

        A list is loaded if it is enabled and can be verified
        or if it is disabled. We assume that a list that cannot
        be verified will raise an exception, therefore we do not
        load it.
        """
        self._reset_lists()

        for name, list_meta in self.image_lists.iteritems():
            try:
                l = ImageList(name,
                         url=list_meta.get("url", None),
                         enabled=list_meta.get("enabled", True),
                         endorser=list_meta.get("endorser", {}),
                         token=list_meta.get("token", None))
            except exception.AtropeException as e:
                logging.error("Skipping list '%s', reason: %s" %
                              (name, e.message))
                logging.debug("Exception while downloading list '%s'" % name,
                              exc_info=e)
            else:
                if l.enabled:
                    if l.trusted:
                        self.enabled_lists.append(l)
                    else:
                        self.untrusted_lists.append(l)
                else:
                    self.disabled_lists.append(l)

        logging.debug("Enabled lists: %s" % self.enabled_lists)
        logging.debug("Disabled lists: %s" % self.disabled_lists)
        logging.debug("Untrusted lists: %s" % self.untrusted_lists)

    def download_images(self):
        """Download the images to disk."""
        if self.enabled_lists is None:
            self.get_lists()

        for l in self.enabled_lists:
            basedir = os.path.join(CONF.lists_path, l.name, 'images')
            utils.makedirs(basedir)

            for img in l.images:
                img.download(basedir)
