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

import urlparse

import glanceclient
from keystoneclient.auth.identity import v2 as v2_auth
from keystoneclient.auth.identity import v3 as v3_auth
from keystoneclient import discover
from keystoneclient.openstack.common.apiclient import exceptions as ks_exc
from keystoneclient import session
from oslo.config import cfg
from oslo.log import log

from atrope.dispatcher import base
from atrope import exception

opts = [
    cfg.StrOpt('username',
               default=None,
               help='Glance user name that will upload the images.'),
    cfg.StrOpt('user_id',
               default=None,
               help='Glance user UUID that will upload the images.'),
    cfg.StrOpt('password',
               default=None,
               help='Password for the glance user.'),
    cfg.StrOpt('tenant_name',
               default=None,
               help='Tenant name for the user.'),
    cfg.StrOpt('tenant_id',
               default=None,
               help='Tenant UUID for the user.'),
    cfg.StrOpt('auth_url',
               default=None,
               help='URL of the identity service to authenticate with.'),
    cfg.StrOpt('endpoint',
               default=None,
               help='URL of the image service to upload images to. '
                    'If this option is not specified, the image service will'
                    'be obtained from the identity service.'),
    cfg.BoolOpt('insecure',
               default=False,
               help='Explicitly allow us to perform '
                    '\"insecure SSL\" (https) requests. The server\'s '
                    'certificate will not be verified against any '
                    'certificate authorities. This option should '
                    'be used with caution.'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="glance")

LOG = log.getLogger(__name__)

class Dispatcher(base.BaseDispatcher):
    """Glance dispatcher.

    This dispatcher will upload images to a glance catalog. The images are
    uploaded, and some metadata is associated to them so as to distinguish
    them from normal images:

        - all images will be tagged with the tag "atrope".
        - the following properties will be set:
            - "sha512": will contain the sha512 checksum for the image.
            - "vmcatcher_event_dc_description": will contain the appdb
              description
            - "vmcatcher_event_ad_mpuri": will contain the marketplate uri
            - "appdb_id": will contain the AppDB UUID

    Moreover, some glance property keys will be set:
        - os_version
        - os_name
        - architecture
        - disk_format
        - container_format

    """
    def __init__(self):
        if not (CONF.glance.username or CONF.glance.user_id):
            raise exception.GlanceMissingConfiguration(flags=["username",
                                                              "user_id"])
        elif not (CONF.glance.tenant_name or CONF.glance.tenant_id):
            raise exception.GlanceMissingConfiguration(flags=["tenant_name",
                                                              "tenant_id"])
        elif not (CONF.glance.endpoint or CONF.glance.auth_url):
            raise exception.GlanceMissingConfiguration(flags=["endpoint",
                                                              "auth_url"])

        self.token, self.endpoint = self._get_token_and_endpoint()

        self.client = glanceclient.Client('2', endpoint=self.endpoint,
                                          token=self.token,
                                          insecure=CONF.glance.insecure)

    def _discover_auth_versions(self, session, auth_url):
        # discover the API versions the server is supporting base on the
        # given URL
        v2_auth_url = None
        v3_auth_url = None
        try:
            ks_discover = discover.Discover(session=session, auth_url=auth_url)
            v2_auth_url = ks_discover.url_for('2.0')
            v3_auth_url = ks_discover.url_for('3.0')
        except ks_exc.ClientException as e:
            # Identity service may not support discover API version.
            # Lets trying to figure out the API version from the original URL.
            url_parts = urlparse.urlparse(auth_url)
            (scheme, netloc, path, params, query, fragment) = url_parts
            path = path.lower()
            if path.startswith('/v3'):
                v3_auth_url = auth_url
            elif path.startswith('/v2'):
                v2_auth_url = auth_url
            else:
                # not enough information to determine the auth version
                msg = ('Unable to determine the Keystone version '
                        'to authenticate with using the given '
                        'auth_url. Identity service may not support API '
                        'version discovery. Please provide a versioned '
                        'auth_url instead. error=%s') % (e)
                raise exception.GlanceError(msg)

        return (v2_auth_url, v3_auth_url)


    def _get_ks_session(self, **kwargs):
        ks_session = session.Session.construct(kwargs)

        # discover the supported keystone versions using the given auth url
        auth_url = kwargs.pop('auth_url', None)
        (v2_auth_url, v3_auth_url) = self._discover_auth_versions(
            session=ks_session,
            auth_url=auth_url)

        # Determine which authentication plugin to use. First inspect the
        # auth_url to see the supported version. If both v3 and v2 are
        # supported, then use the highest version if possible.
        user_id = kwargs.pop('user_id', None)
        username = kwargs.pop('username', None)
        password = kwargs.pop('password', None)
        user_domain_name = kwargs.pop('user_domain_name', None)
        user_domain_id = kwargs.pop('user_domain_id', None)
        # project and tenant can be used interchangeably
        project_id = (kwargs.pop('project_id', None) or
                        kwargs.pop('tenant_id', None))
        project_name = (kwargs.pop('project_name', None) or
                        kwargs.pop('tenant_name', None))
        project_domain_id = kwargs.pop('project_domain_id', None)
        project_domain_name = kwargs.pop('project_domain_name', None)
        auth = None

        use_domain = (user_domain_id or
                        user_domain_name or
                        project_domain_id or
                        project_domain_name)
        use_v3 = v3_auth_url and (use_domain or (not v2_auth_url))
        use_v2 = v2_auth_url and not use_domain

        if use_v3:
            auth = v3_auth.Password(
                v3_auth_url,
                user_id=user_id,
                username=username,
                password=password,
                user_domain_id=user_domain_id,
                user_domain_name=user_domain_name,
                project_id=project_id,
                project_name=project_name,
                project_domain_id=project_domain_id,
                project_domain_name=project_domain_name)
        elif use_v2:
            auth = v2_auth.Password(
                v2_auth_url,
                username,
                password,
                tenant_id=project_id,
                tenant_name=project_name)
        else:
            # if we get here it means domain information is provided
            # (caller meant to use Keystone V3) but the auth url is
            # actually Keystone V2. Obviously we can't authenticate a V3
            # user using V2.
            exception.GlanceError("Credential and auth_url mismatch. The given"
                                  " auth_url is using Keystone V2 endpoint, "
                                  " which may not able to handle Keystone V3 "
                                  "credentials. Please provide a correct "
                                  "Keystone V3 auth_url.")

        ks_session.auth = auth
        return ks_session

    def _get_token_and_endpoint(self):
        kwargs = {
            "username": CONF.glance.username,
            "user_id": CONF.glance.user_id,
            "password": CONF.glance.password,
            "tenant_name": CONF.glance.tenant_name,
            "tenant_id": CONF.glance.tenant_id,
            "auth_url": CONF.glance.auth_url,
            "insecure": CONF.glance.insecure,
        }
        ks_session = self._get_ks_session(**kwargs)
        endpoint = CONF.glance.endpoint or ks_session.get_endpoint(
                service_type='image',
                endpoint_type='public')
        return ks_session.get_token(), endpoint

    def dispatch(self, image, **kwargs):
        """Upload an image to the glance service.

        If metadata is provided in the kwargs it will be associated with
        the image."""
        LOG.debug("Glance dispatching %s" % image)

        # TODO(aloga): missing hypervisor type, need list spec first
        metadata = {
            "name": image.title,
            "tags": ["atrope"],
            "architecture": image.arch,
            "disk_format": None,
            "container_format": None,
            "os_distro": image.osname.lower(),
            "os_version": image.osversion,
            # AppDB properties
            "vmcatcher_event_dc_description": image.description,
            "vmcatcher_event_ad_mpuri": image.mpuri,
            "appdb_id": image.identifier,
            "sha512": image.sha512,
        }

        for k, v in kwargs.iteritems():
            if k in metadata:
                raise exception.MetadataOverwriteNotSupported(key=k)
            metadata[k] = v

        # Format is not defined in the spec. What is format? Maybe it is the
        # container format? Or is it the image format? Try to do some ugly
        # magic and infer what is this for...
        # This makes me sad :-(
        LOG.warning("The image spec is broken and I will try to guess what "
                    "I the container and the image format is. I cannot "
                    "promise anything.")
        smth_format = image.format.lower()
        (metadata["container_format"],
         metadata["disk_format"]) = self._guess_formats(smth_format)

        kwargs = {
            "filters": {
                "tag": ["atrope"],
                "appdb_id": image.identifier,
            }
        }
        # TODO(aloga): what if we have several images here?
        images = list(self.client.images.list(**kwargs))
        if len(images) > 1:
            images = [img.id for img in images]
            LOG.error("Found several images with same sha512, please remove "
                      "them manually %s.", images)
            raise exception.DuplicatedImage(images=images)

        try:
            glance_image = images.pop()
        except IndexError:
            glance_image = None
        else:
            if glance_image.sha512 != image.sha512:
                LOG.info("Image %s is %s in glance but sha512 checksums are "
                         "different, deleting it and reuploading.")
                self.client.images.delete(glance_image.id)
                glance_image = None

        if not glance_image:
            LOG.debug("Creating image %s.", image.identifier)
            glance_image = self.client.images.create(**metadata)

        if glance_image.status == "queued":
            self._upload(glance_image.id, image)

        if glance_image.status == "active":
            LOG.debug("Image %s is %s in glance.",
                      image.identifier,
                      glance_image.id)

    def sync(self, image_list):
        """Sunc image list with dispached images."""
        kwargs = {
            "filters": {
                "tag": ["atrope"],
                "image_list": image_list.name,
            }
        }
        valid_images = [i.identifier
                        for i in image_list.get_subscribed_images()]
        for image in self.client.images.list(**kwargs):
            appdb_id = image.get("appdb_id", "")
            if appdb_id not in valid_images:
                LOG.info("Image %s in glance is not valid anymore, "
                         "deleting it", image.id)
                self.client.images.delete(image.id)

        LOG.info("Sync terminated for image list %s", image_list.name)


    def _upload(self, id, image):
        fd = open(image.location, "rb")
        self.client.images.upload(id, fd)

    def _guess_formats(self, smth_format):
        if smth_format == "ova":
            container_format = "ova"
            disk_format = "vmdk"
        elif smth_format == "standard":
            # This is ugly
            container_format = "bare"
            disk_format = "raw"
        elif smth_format == "qcow2":
            container_format = "bare"
            disk_format = "qcow2"
        else:
            raise exception.ImageListSpecIsBorken()
        return container_format, disk_format
