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

import dateutil.parser
import dateutil.tz

from atrope import endorser
from atrope import exception
from atrope import image


class HepixImageList(object):
    """
    A Hepix Image List.

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
