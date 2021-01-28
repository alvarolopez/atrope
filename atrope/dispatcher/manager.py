# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg
from oslo_log import log

from atrope import exception
from atrope import importutils

opts = [
    cfg.MultiStrOpt('dispatcher',
                    default=['noop'],
                    help='Dispatcher to process images. Can be specified '
                         'multiple times.'),
    cfg.StrOpt('prefix',
               default="",
               help="If set, the image name's will be prefixed by this "
               "option."),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="dispatchers")

LOG = log.getLogger(__name__)

DISPATCHER_NAMESPACE = 'atrope.dispatcher'


class DispatcherManager(object):
    def __init__(self):
        self.dispatchers = []
        for dispatcher in CONF.dispatchers.dispatcher:
            cls_ = "%s.%s.Dispatcher" % (DISPATCHER_NAMESPACE, dispatcher)
            self.dispatchers.append(importutils.import_class(cls_)())

    def sync(self, image_list, **kwargs):
        """Sync the images from one list with the dispatchers.

        This method will dispatch all the images associated with the image
        list. Afterwards it will remove any image associated to that image list
        that was not set for dispatch (i.e. it will remove old images).
        """
        self._dispatch_list(image_list, **kwargs)
        self._sync_list(image_list)

    def _sync_list(self, image_list):
        """Sync a list after sending all the images to the dispatcher.

        This methid will call the sync_list method for each of the dispatchers,
        in theory these methods should remove old images that were not
        dispached.
        """
        for dispatcher in self.dispatchers:
            dispatcher.sync(image_list)

    def _dispatch_list(self, image_list, **kwargs):
        """Dispatch a list of images to each of the dispatchers.

        This command will receive an image list and will dispatch all the
        images into the catalog.

        :param image_list: image list to dispatch
        :param **kwargs: extra metadata to be added to the image.
        """

        LOG.info("Preparing to dispatch list '%s''" % image_list.name)

        kwargs.setdefault("image_list", image_list.name)
        kwargs.setdefault("project", image_list.project)

        is_public = False if image_list.token else True

        if image_list.image_list is not None:
            if image_list.image_list.vo is not None:
                kwargs["vo"] = image_list.image_list.vo

        try:
            images = image_list.get_valid_subscribed_images()
        except exception.ImageListNotFetched:
            LOG.warning(f"Image list {image_list.name} has not been fetched "
                        "skipping dispatch.")
            images = []

        for image in images:
            image_name = ("%(global prefix)s%(list prefix)s%(image name)s" %
                          {"global prefix": CONF.dispatchers.prefix,
                           "list prefix": image_list.prefix,
                           "image name": image.title})
            self._dispatch_image(image_name, image, is_public, **kwargs)

    def _dispatch_image(self, image_name, image, is_public, **kwargs):
        """Dispatch a single image to each of the dispatchers."""
        for dispatcher in self.dispatchers:
            try:
                dispatcher.dispatch(image_name, image, is_public, **kwargs)
            except Exception as e:
                LOG.exception("An exception has occured when dispatching "
                              "image %s" % image.identifier)
                LOG.exception(e)
