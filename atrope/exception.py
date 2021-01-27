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

import os

from oslo_log import log

LOG = log.getLogger(__name__)


class AtropeException(Exception):
    msg_fmt = "An unknown exception occurred."

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if not message:
            try:
                message = self.msg_fmt % kwargs
            except Exception:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception('Exception in string format operation')
                for name, value in kwargs.items():
                    LOG.error("%s: %s" % (name, value))
                message = self.msg_fmt

        super(AtropeException, self).__init__(message)


class CannotOpenFile(AtropeException):
    msg_fmt = "Cannot open file %(file)s: %(reason)s"

    def __init__(self, message=None, errno=0, **kwargs):
        kwargs["reason"] = os.strerror(errno)
        super(CannotOpenFile, self).__init__(message=message, **kwargs)


class SMIMEValidationError(AtropeException):
    msg_fmt = "Could not validate SMIME message: %(err)s"


class ImageListDownloadFailed(AtropeException):
    msg_fmt = "Cannot get image list, reason: (%(code)s) %(reason)s"


class ImageDownloadFailed(AtropeException):
    msg_fmt = "Cannot get image, reason: (%(code)s) %(reason)s"


class InvalidOVAFile(AtropeException):
    msg_fmt = "Invalid OVA file, reason: %(reason)s"


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


class ImageListNotFetched(AtropeException):
    msg_fmt = "Image list %(id)s has not been fetched"


class GlanceError(AtropeException):
    msg_fmt = "An unknown Glance exception occurred."


class GlanceMissingConfiguration(GlanceError):
    msg_fmt = "Glance catalog requires one of %(flags)s flags"


class DuplicatedImage(AtropeException):
    msg_fmt = "Found several images with same sha512 %(images)s"


class ImageListSpecIsBorken(AtropeException):
    # NOTE(aloga): Borken in the class name is intentional
    msg_fmt = ("The image list spec is broken and I am not able to "
               "guess what the image format is.")


class MetadataOverwriteNotSupported(AtropeException):
    msg_fmt = "Setting %(key)s property is not supported."


class GlanceInvalidMappingFIle(GlanceError):
    msg_fmt = "Cannot load %(file)s mapping file: %(reason)s."
