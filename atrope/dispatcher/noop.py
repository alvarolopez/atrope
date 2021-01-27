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

from oslo_log import log

from atrope.dispatcher import base

LOG = log.getLogger(__name__)


class Dispatcher(base.BaseDispatcher):
    """This dummy dispatcher does nothing."""

    def sync(self, image_list):
        """I do nothing."""

    def dispatch(self, image_name, image, *args, **kwargs):
        """In theory I should do something with the image.

        In practise I do nothing, since I am the NOOP dispatcher.
        """
        LOG.info("Dispatching image (noop) %s" % image)
        LOG.info("Dispatching image (noop) args: %s" % args)
        LOG.info("Dispatching image (noop) kwargs: %s" % kwargs)
