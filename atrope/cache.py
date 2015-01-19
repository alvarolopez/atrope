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

from oslo.config import cfg
from oslo.log import log

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
        self.path = os.path.abspath(CONF.cache.path)
        utils.makedirs(self.path)

    def sync(self, lists):

        valid_paths = [self.path]
        invalid_paths = []

        for l in lists.values():
            if l.enabled:
                basedir = os.path.join(self.path, l.name)
                valid_paths.append(basedir)
                imgdir = os.path.join(self.path, l.name, 'images')
                if l.trusted and l.verified and not l.expired:
                    utils.makedirs(imgdir)
                    valid_paths.append(imgdir)
                    for img in l.get_subscribed_images():
                        try:
                            img.download(imgdir)
                        except (exception.ImageVerificationFailed,
                                exception.ImageDownloadFailed):
                            # FIXME(aloga): we should notify about this in the
                            # cmd line.
                            pass
                        else:
                            valid_paths.append(img.location)

        for root, dirs, files in os.walk(self.path):
            if root not in valid_paths:
                invalid_paths.append(root)
            for i in files + dirs:
                i = os.path.join(root, i)
                if i not in valid_paths:
                    invalid_paths.append(i)

        if invalid_paths:
            LOG.debug("Marked %s as invalid cache files/dirs.", invalid_paths)
        else:
            LOG.debug("No invalid files in cache dir.")

        for i in invalid_paths:
            LOG.warning("Removing '%s' from cache directory.", i)
            utils.rm(i)
