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

import pathlib

from oslo_config import cfg
from oslo_log import log

from atrope import exception
from atrope import paths
from atrope import utils

opts = [
    cfg.StrOpt('path',
               default=paths.state_path_def('lists'),
               help='Where instances are stored on disk'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="cache")

LOG = log.getLogger(__name__)


class CacheManager(object):
    def __init__(self):
        self.path = pathlib.Path(CONF.cache.path)
        utils.makedirs(self.path)  # FIXME
        self._valid_paths = [self.path]

    def _download_list(self, lst):
        LOG.info(f"Syncing list with ID '{lst.name}'")
        if lst.enabled:
            LOG.info(f"List '{lst.name}' is enabled, checking if downloaded "
                     "images are valid")
            basedir = self.path / lst.name
            imgdir = basedir / 'images'
            if lst.trusted and lst.verified and not lst.expired:
                utils.makedirs(imgdir)  # FIXME(aloga) pathlib
                self._valid_paths.append(basedir)
                self._valid_paths.append(imgdir)
                for img in lst.get_subscribed_images():
                    try:
                        img.download(imgdir)
                    except (exception.ImageVerificationFailed,
                            exception.ImageDownloadFailed):
                        pass
                    else:
                        pass
                        self._valid_paths.append(pathlib.Path(img.location))
        else:
            LOG.info(f"List '{lst.name}' is disabled, images will be "
                     "marked for removal")

    def _clean_invalid(self, base):
        LOG.info(f"Checking for invalid files in cache dir ({base}).")
        invalid_paths = []

        for f in base.glob("**/*"):
            if f not in self._valid_paths:
                invalid_paths.append(f)

        if not invalid_paths:
            LOG.info(f"No invalid files in cache dir ({base}).")

        for i in invalid_paths:
            LOG.warning(f"Removing '{i}' from cache.")
            utils.rm(i)  # FIXME

    def sync_one(self, lst):
        self._download_list(lst)
        self._clean_invalid(self.path / lst.name)

    def sync(self, lists):
        LOG.info("Starting cache sync")

        for lst in lists.values():
            self.sync_one(lst)
        self._clean_invalid(self.path)

        LOG.info("Sync completed")
