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
import pprint

import dateutil.parser
import dateutil.tz
from oslo_config import cfg
from oslo_log import log
import requests

from atrope import endorser
from atrope import exception
from atrope import image
from atrope.image_list import source
from atrope import smime
from atrope import utils

opts = [
    cfg.StrOpt('hepix_sources',
               default='/etc/atrope/hepix.yaml',
               help='Where the HEPiX image list sources are stored.'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="sources")

LOG = log.getLogger(__name__)


class HepixImageList(object):
    """A Hepix Image List.

    Objects of this class will hold the representation of the
    downloaded Hepix image list.
    """
    required_fields = (
        "dc:date:created",
        "dc:date:expires",
        "hv:endorser",
        "dc:identifier",
        "dc:description",
        "dc:title",
        "hv:images",
        "dc:source",
        "hv:version",
        "hv:uri",
    )

    def __init__(self, meta):
        meta = meta.get("hv:imagelist", {})
        keys = meta.keys()
        if not all([i in keys for i in self.required_fields]):
            reason = "Invalid image list, missing mandatory fields"
            raise exception.InvalidImageList(reason=reason)

        self.created = dateutil.parser.parse(meta["dc:date:created"])
        self.expires = dateutil.parser.parse(meta["dc:date:expires"])
        self.uuid = meta["dc:identifier"]
        self.description = meta["dc:description"]
        self.name = meta["dc:title"]
        self.source = meta["dc:source"]
        self.version = meta["hv:version"]
        self.uri = meta["hv:uri"]

        endorser_meta = meta.get("hv:endorser")
        self.endorser = endorser.Endorser(endorser_meta)

        self.images = []
        for img_meta in meta.get("hv:images"):
            self.images.append(image.HepixImage(img_meta))

        self.vo = meta.get('ad:vo', None)

    def get_images(self):
        return self.images


class HepixImageListSource(source.BaseImageListSource):
    """An image list."""

    def __init__(self, name, url="", enabled=True, subscribed_images=[],
                 prefix="", project="", **kwargs):

        super(HepixImageListSource, self).__init__(
            name,
            url=url,
            enabled=enabled,
            subscribed_images=subscribed_images,
            prefix=prefix,
            project=project
        )

        self.token = kwargs.get("token", "")

        self.endorser = kwargs.get("endorser", {})

        self.image_list = None

        self.signer = None
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
            self.verified, self.signer, raw_list = self._verify()
            try:
                list_as_dict = json.loads(raw_list)
            except ValueError:
                LOG.error("Invalid JSON for image list '%s'", self.name)
                raise exception.InvalidImageList(reason="Invalid JSON.")

            image_list = HepixImageList(list_as_dict)
            self.image_list = image_list

            self.expired = self._check_expiry()
            self.trusted = self._check_endorser()

    def _fetch(self):
        """Get the image list from the server.

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
        """Verify the image list SMIME signature.

        :returns: tuple (signers, raw_list) with the signers and the raw list.
        :raises: exception.SMIMEValidationError if it is not possible to verify
                 the signature.
        """
        verifier = smime.SMIMEVerifier()
        try:
            signer, raw_list = verifier.verify(self.contents)
        except Exception:
            raise
        else:
            return True, signer, raw_list

    def _check_endorser(self):
        """Check the endorsers of an image list.

        :returns: True of False if endorsers are trusted or not.
        """

        list_endorser = self.image_list.endorser
        msg = None
        if (self.signer.dn != list_endorser.dn or
                self.signer.ca != list_endorser.ca):
            msg = ("List '%s' signer != list endorser "
                   "'%s' != '%s'" %
                   (self.name, self.signer, list_endorser))
        elif self.endorser["dn"] != list_endorser.dn:
            msg = ("List '%s' endorser is not trusted, DN mismatch "
                   "'%s' != '%s'" %
                   self.name, self.endorser["dn"], list_endorser.dn)
        elif self.endorser["ca"] != list_endorser.ca:
            msg = ("List '%s' endorser CA is invalid '%s' != '%s'" %
                   self.name, self.endorser["ca"], list_endorser.ca)
        if msg:
            LOG.error(msg)
            self.error = msg
            return False
        return True

    def _check_expiry(self):
        now = datetime.datetime.now(dateutil.tz.tzlocal())
        if self.image_list.expires < now:
            LOG.warning("List '%s' expired on '%s'",
                        self.name, self.image_list.expires)
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
            d["contents"] = pprint.pformat(self.contents)
        images = [str(img.identifier) for img in self.get_images()]
        if images:
            d["images"] = images
        subscribed = self.subscribed_images or images
        d["images (subscribed)"] = subscribed

        utils.print_dict(d)
