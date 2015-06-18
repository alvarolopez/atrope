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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseDispatcher(object):
    """Base class for all dispatchers."""

    @abc.abstractmethod
    def sync(self, image_list):
        """Sync the image_list images.

        This method should sync the image list's images with those that have
        been dispatched in the past.
        """

    @abc.abstractmethod
    def dispatch(self, image_name, image, is_public, **kwargs):
        """Save an image with its metadata."""
