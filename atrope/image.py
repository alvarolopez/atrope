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

import abc
import hashlib
import logging
import os.path

import requests

from atrope import exception
from atrope import utils

# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BaseImage(object):
    __metaclass__ = abc.ABCMeta

    uri = sha512 = identifier = location = None

    @abc.abstractmethod
    def __init__(self, image_info):
        pass

    @abc.abstractmethod
    def download(self, dest):
        """
        Download the image.

        :param dest: destionation directory.
        """

    def verify_checksum(self, location=None):
        """Verify the image's checksum."""

        location = location or self.location
        if location is None:
            raise exception.ImageNotFoundOnDisk(location=location)

        sha512 = utils.get_file_checksum(location)
        if sha512.hexdigest() != self.sha512:
            raise exception.ImageVerificationFailed(
                id=self.identifier,
                expected=self.sha512,
                obtained=sha512.hexdigest()
            )


class VMCasterImage(BaseImage):
    # TODO(aloga): are all of this really required?
    required_fields = (
        "ad:group",
        "ad:mpuri",
        "ad:user:fullname",
        "ad:user:guid",
        "ad:user:uri",
        "dc:description",
        "dc:identifier",
        "dc:title",
        "hv:hypervisor",
        "hv:format",
        "hv:size",
        "hv:uri",
        "hv:version",
        "sl:arch",
        "sl:checksum:sha512",
        "sl:comments",
        "sl:os",
        "sl:osname",
        "sl:osversion",
    )

    def __init__(self, image_info):
        super(VMCasterImage, self).__init__(image_info)

        image_dict = image_info.get("hv:image", {})

        keys = image_dict.keys()
        if not all(i in keys for i in self.required_fields):
            raise exception.InvalidImageList(
                reason="Invalid image definition."
            )

        self.uri = image_dict.get("hv:uri")
        self.sha512 = image_dict.get("sl:checksum:sha512")
        self.identifier = image_dict.get("dc:identifier")

    def _download(self, location):
        logging.debug("Downloading image '%s' into '%s'" %
                      (self.identifier, location))
        with open(location, 'wb') as f:
            response = requests.get(self.uri, stream=True)

            if not response.ok:
                # FIXME(aloga)
                pass

            for block in response.iter_content(1024):
                if block:
                    f.write(block)
                    f.flush()
        try:
            self.verify_checksum(location=location)
        except exception.ImageVerificationFailed as e:
            logging.error(e)
        else:
            logging.debug("Image '%s' downloaded into '%s'" %
                          (self.identifier, location))


    def download(self, basedir):
        # The image has been already downloaded in this execution.
        if self.location is not None:
            raise exception.ImageAlreadyDownloaded(location=self.location)

        location = os.path.join(basedir, self.identifier)

        if not os.path.exists(location):
            self._download(location)
        else:
            # Image exists, is it checksum valid?
            try:
                self.verify_checksum(location=location)
            except exception.ImageVerificationFailed:
                logging.info("Image '%s' found in '%s' is not valid, "
                             "downloading again" % (self.identifier,location))
                self._download(location)
            else:
                logging.debug("Image '%s' already downloaded into '%s'" %
                              (self.identifier,location))

        self.location = location
