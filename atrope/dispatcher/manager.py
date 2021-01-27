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

        LOG.info("Preparing to dispatch list '%s''" % image_list.name)

        kwargs.setdefault("image_list", image_list.name)
        kwargs.setdefault("project", image_list.project)

        is_public = False if image_list.token else True

        if image_list.image_list is not None:
            if image_list.image_list.vo is not None:
                kwargs["vo"] = image_list.image_list.vo

        for image in image_list.get_valid_subscribed_images():
            image_name = ("%(global prefix)s%(list prefix)s%(image name)s" %
                          {"global prefix": CONF.dispatchers.prefix,
                           "list prefix": image_list.prefix,
                           "image name": image.title})
            self.dispatch_image(image_name, image, is_public, **kwargs)

    def dispatch_image(self, image_name, image, is_public, **kwargs):
        """Dispatch a single image to each of the dispatchers."""
        for dispatcher in self.dispatchers:
            try:
                dispatcher.dispatch(image_name, image, is_public, **kwargs)
            except Exception as e:
                LOG.exception("An exception has occured when dispatching "
                              "image %s" % image.identifier)
                LOG.exception(e)
