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

from oslo.config import cfg

from atrope import importutils

opts = [
    cfg.MultiStrOpt('dispatcher',
                    default=['noop'],
                    help='Dispatcher to process images. Can be specified '
                         'multiple times.'),
]

CONF = cfg.CONF
CONF.register_opts(opts)

DISPATCHER_NAMESPACE = 'atrope.dispatcher'


class DispatcherManager(object):
    def __init__(self):
        self.dispatchers = []
        for dispatcher in CONF.dispatcher:
            cls_ = "%s.%s.Dispatcher" % (DISPATCHER_NAMESPACE, dispatcher)
            self.dispatchers.append(importutils.import_class(cls_)())

    def dispatch_list_and_sync(self, image_list, **kwargs):
        """Dispatch and sync the images list.

        This method will dispatch all the images associated with the image
        list. Afterwards it will remove any image associated to that image list
        that was not set for dispatch.
        """
        self.dispatch_list(image_list, **kwargs)
        for dispatcher in self.dispatchers:
            dispatcher.sync(image_list)

    def dispatch_list(self, image_list, **kwargs):
        """Dispatch a list of images to each of the dispatchers.

        This command will receive an image list and will dispatch all the
        images into the catalog.

        :param image_list: image list to dispatch
        :param **kwargs: extra metadata to be added to the image.
        """

        kwargs.setdefault("image_list", image_list.name)

        for image in image_list.get_subscribed_images():
            self.dispatch_image(image, **kwargs)

    def dispatch_image(self, image, **kwargs):
        """Dispatch a single image to each of the dispatchers."""
        for dispatcher in self.dispatchers:
            dispatcher.dispatch(image, **kwargs)
