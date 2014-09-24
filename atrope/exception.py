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

import logging
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AtropeException(Exception):
    msg_fmt = "An unknown exception occurred."

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if not message:
            try:
                message = self.msg_fmt % kwargs
            except Exception:
                exc_info = sys.exc_info()
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                logger.exception('Exception in string format operation')
                for name, value in kwargs.iteritems():
                    logger.error("%s: %s" % (name, value))
                raise exc_info[0], exc_info[1], exc_info[2]

        super(AtropeException, self).__init__(message)


class SMIMEValidationError(AtropeException):
    msg_fmt = "Could not validate SMIME message: %(exception)s"


class ImageListDownloadFailed(AtropeException):
    msg_fmt = "Cannot get image list, reason: (%(code)s) %(reason)s"


class InvalidImageList(AtropeException):
    msg_fmt = "Image list is not valid: %(reason)s"


class ImageAlreadyDownloaded(AtropeException):
    msg_fmt = "Image already downloaded into %(location)s"


class ImageNotFoundOnDisk(AtropeException):
    msg_fmt = "Image cannot be found on %(location)s"


class ImageVerificationFailed(AtropeException):
    msg_fmt = "Image %(id)s verification failed %(expected)s != %(obtained)s"


class MissingMandatoryFieldImageList(AtropeException):
    msg_fmt = "Image list is not valid, field '%(field)s' cannot be empty"


class DuplicatedImageList(AtropeException):
    msg_fmt = "Image list with id %(id)s exists"
