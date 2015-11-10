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

from atrope import exception


class Endorser(object):
    required_fields = (
        "dc:creator",
        "hv:ca",
        "hv:dn",
        "hv:email",
    )

    def __init__(self, meta):
        # FIXME(aloga): DRY this
        meta = meta.get("hv:x509")

        keys = meta.keys()
        if not all([i in keys for i in self.required_fields]):
            reason = "Invalid image list, missing mandatory fields"
            raise exception.InvalidImageList(reason=reason)

        self.name = meta["dc:creator"]
        self.dn = meta["hv:dn"]
        self.ca = meta["hv:ca"]
        self.email = meta["hv:email"]

    def __str__(self):
        return "<Endorser dn:%s, ca:%s>" % (self.dn, self.ca)
