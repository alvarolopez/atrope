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
import os.path

from oslo.config import cfg
import yaml

from atrope import exception
from atrope import paths
from atrope import utils
import atrope.image_list.source

opts = [
    cfg.StrOpt('image_list_sources',
               default='/etc/atrope/lists.yaml',
               help='Where the image list sources are stored.'),
    cfg.StrOpt('cache_dir',
               default=paths.state_path_def('lists'),
               help='Where instances are stored on disk'),
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

        self.cache_dir = os.path.abspath(CONF.cache_dir)
        utils.makedirs(self.cache_dir)

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

    def sync_cache(self):
        self.load_lists()

        valid_paths = [self.cache_dir]
        invalid_paths = []

        for l in self.loaded_lists:
            if l.enabled:
                basedir = os.path.join(self.cache_dir, l.name)
                valid_paths.append(basedir)
                imgdir = os.path.join(self.cache_dir, l.name, 'images')
                if l.trusted and l.verified and not l.expired:
                    utils.makedirs(imgdir)
                    valid_paths.append(imgdir)
                    for img in l.image_list.images:
                        if l.images and img.identifier not in l.images:
                            continue

                        try:
                            img.download(imgdir)
                        except exception.ImageVerificationFailed:
                            # FIXME(aloga): we should notify about this in the
                            # cmd line.
                            pass
                        else:
                            valid_paths.append(img.location)

        for root, dirs, files in os.walk(self.cache_dir):
            if root not in valid_paths:
                invalid_paths.append(root)
            for i in files + dirs:
                i = os.path.join(root, i)
                if i not in valid_paths:
                    invalid_paths.append(i)

        logging.debug("Marked %s as invalid cache files/dirs." % invalid_paths)
        for i in invalid_paths:
            logging.debug("Removing %s from cache directory." % i)
            utils.rm(i)


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
