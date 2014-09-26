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

import datetime
import json
import logging
import pprint

import dateutil
import requests

from atrope import exception
import atrope.image_list.hepix
from atrope import smime
from atrope import utils

# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ImageListSource(object):
    """An image list."""

    def __init__(self, name, url="", enabled=True,
                 endorser={}, token="", images=[]):
        self.name = name

        self.url = url
        self.token = token

        # subscribed images
        self.images = images

        self.enabled = enabled

        self.endorser = endorser

        self.image_list = None

        self.signers = None
        self.verified = False
        self.trusted = False
        self.expired = None
        self.error = None

        self.contents = None

    def _set_error(func):
        def decorated(self):
            try:
                func(self)
            except Exception as e:
                self.error = e
                raise
        return decorated

    @_set_error
    def fetch(self):
        if self.enabled and self.url:
            self.contents = self._fetch()
            self.verified, self.signers, raw_list = self._verify()
            try:
                list_as_dict = json.loads(raw_list)
            except ValueError:
                raise exception.InvalidImageList(reason="Invalid JSON.")

            image_list = atrope.image_list.hepix.HepixImageList(list_as_dict)
            self.image_list = image_list

            self.expired = self._check_expiry()
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
        except Exception:
            raise
        else:
            return True, signers, raw_list

    def _check_endorser(self):
        """
        Check the endorsers of an image list.

        :returns: True of False if endorsers are trusted or not.
        """

        list_endorser = self.image_list.endorser

        if self.endorser["dn"] != list_endorser.dn:
            msg = ("List '%s' endorser is not trusted, DN mismatch %s != %s" %
                   (self.name, self.endorser["dn"], list_endorser.dn))
            logging.error(msg)
            self.error = msg
            return False

        if self.endorser["ca"] != list_endorser.ca:
            msg = ("List '%s' endorser CA is invalid %s != %s" %
                   (self.name, self.endorser["ca"], list_endorser.ca))
            logging.error(msg)
            self.error = msg
            return False
        return True

    def _check_expiry(self):
        now = datetime.datetime.now(dateutil.tz.tzlocal())
        if self.image_list.expires < now:
            logging.info("List '%s' expired on '%s'" %
                         (self.name, self.image_list.expires))
            return True
        return False

    def print_list(self, contents=False):
        d = {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "endorser dn": self.endorser.get("dn", None),
            "endorser ca": self.endorser.get("ca", None),
        }
        d["verified"] = self.verified
        d["trusted"] = self.trusted
        d["expired"] = self.expired
        d["token set"] = self.token and True
        if self.error is not None:
            d["error"] = self.error
        if self.contents is not None and contents:
            d["contents"] = pprint.pformat(self.d_contents)
        if self.images:
            d["subscribed images"] = self.images
        utils.print_dict(d)
