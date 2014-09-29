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
import logging

from oslo.config import cfg
import yaml

from atrope import exception
import atrope.image_list.source

opts = [
    cfg.StrOpt('image_list_sources',
               default='/etc/atrope/lists.yaml',
               help='Where the image list sources are stored.'),
]

CONF = cfg.CONF
CONF.register_opts(opts)

# FIXME(aloga): this should be configurable
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BaseImageListManager(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.configured_lists = {}
        self.loaded_lists = None

        self._load_sources()

    @abc.abstractmethod
    def _load_sources(self):
        """Load the image sources from disk."""

    @abc.abstractmethod
    def add_image_list_source(self, image):
        """Add an image source to the configuration file."""

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
            raise exception.InvalidImageList(reason="not found in config")
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


class YamlImageListManager(BaseImageListManager):
    def __init__(self):
        super(YamlImageListManager, self).__init__()

    def _load_sources(self):
        with open(CONF.image_list_sources, "rb") as f:
            image_lists = yaml.safe_load(f)

        for name, list_meta in image_lists.iteritems():
            l = atrope.image_list.source.ImageListSource(
                name,
                url=list_meta.get("url", ""),
                enabled=list_meta.get("enabled", True),
                endorser=list_meta.get("endorser", {}),
                token=list_meta.get("token", ""),
                images=list_meta.get("images", [])
            )
            self.configured_lists[name] = l

    def add_image_list_source(self, image_list, force=False):
        if image_list.name in self.configured_lists and not force:
            raise exception.DuplicatedImageList(id=image_list.name)

        self.configured_lists[image_list.name] = image_list

    def write_image_list_sources(self):
        lists = {}
        for name, image_list in self.configured_lists.iteritems():
            lists[name] = {"url": image_list.url,
                           "enabled": image_list.enabled,
                           "endorser": image_list.endorser,
                           "token": image_list.token,
                           "images": image_list.images}
        dump = yaml.dump(lists)
        if not dump:
            raise exception.AtropeException()

        with open(CONF.image_list_sources, "w") as f:
            f.write(dump)
