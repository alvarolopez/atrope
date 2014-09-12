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

import os.path

import requests

from atrope import exception


class BaseImage(object):
    pass


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

    def __init__(self, image_dict):
        image_dict = image_dict.get("hv:image", {})

        keys = image_dict.keys()
        if not all(i in keys for i in self.required_fields):
            raise exception.InvalidImageList(
                reason="Invalid image definition."
            )

        self.uri = image_dict.get("hv:uri")
        self.sha512 = image_dict.get("sl:checksum:sha512")
        self.identifier = image_dict.get("dc:identifier")

    def download(self, basedir):
        dest = os.path.join(basedir, self.identifier)

        with open(dest, 'wb') as f:
            response = requests.get(self.uri, stream=True)

            if not response.ok:
                # FIXME(aloga)
                pass

            for block in response.iter_content(1024):
                if block:
                    f.write(block)
                    f.flush()
