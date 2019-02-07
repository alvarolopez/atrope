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

import json

import glanceclient.client
from glanceclient import exc as glance_exc
from keystoneauth1 import loading
from keystoneclient.v3 import client as ks_client_v3
from oslo_config import cfg
from oslo_log import log

from atrope.dispatcher import base
from atrope import exception

opts = [
    cfg.StrOpt('mapping_file',
               default='etc/voms.json',
               help='File containing the VO <-> tenant mapping for image '
                    'lists private to VOs'),
]

CFG_GROUP = "glance"
CONF = cfg.CONF
CONF.import_opt("prefix", "atrope.dispatcher.base", group="dispatchers")
CONF.register_opts(opts, group="glance")

loading.register_auth_conf_options(CONF, CFG_GROUP)
loading.register_session_conf_options(CONF, CFG_GROUP)

opts += (loading.get_auth_common_conf_options() +
         loading.get_session_conf_options() +
         loading.get_auth_plugin_conf_options('password'))

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
            - "APPLIANCE_ATTRIBUTES": will contain the original data from
               the Hepix description as json if available

    Moreover, some glance property keys will be set:
        - os_version
        - os_name
        - architecture
        - disk_format
        - container_format

    """
    def __init__(self):
        self.client = self._get_glance_client()
        self.ks_client = self._get_ks_client()

        try:
            self.json_mapping = json.loads(
                open(CONF.glance.mapping_file).read())
        except ValueError:
            raise exception.GlanceInvalidMappingFIle(
                file=CONF.glance.mapping_file,
                reason="Bad JSON."
            )

        # Format is not defined in the spec. What is format? Maybe it is the
        # container format? Or is it the image format? Try to do some ugly
        # magic and infer what is this for...
        # This makes me sad :-(
        LOG.debug("The image spec is broken and I will try to guess what "
                  "the container and the image format are. I cannot "
                  "promise anything.")

    def _get_ks_client(self):
        auth_plugin = loading.load_auth_from_conf_options(CONF, CFG_GROUP)
        sess = loading.load_session_from_conf_options(CONF, CFG_GROUP,
                                                      auth=auth_plugin)
        return ks_client_v3.Client(session=sess)

    def _get_glance_client(self, project_id=None):
        if project_id:
            auth_plugin = loading.load_auth_from_conf_options(
                CONF, CFG_GROUP, project_id=project_id)
        else:
            auth_plugin = loading.load_auth_from_conf_options(CONF, CFG_GROUP)

        session = loading.load_session_from_conf_options(CONF, CFG_GROUP,
                                                         auth=auth_plugin)
        return glanceclient.client.Client(2, session=session)

    def _get_vo_tenant_mapping(self, vo):
        tenant = self.json_mapping.get(vo, {}).get("tenant", None)
        tenants = self.ks_client.projects.list(name=tenant)
        return tenants[0].id if tenants else None

    def dispatch(self, image_name, image, is_public, **kwargs):
        """Upload an image to the glance service.

        If metadata is provided in the kwargs it will be associated with
        the image.
        """
        LOG.info("Glance dispatching '%s'", image.identifier)

        # TODO(aloga): missing hypervisor type, need list spec first
        metadata = {
            "name": image_name,
            "tags": ["atrope"],
            "architecture": image.arch,
            "disk_format": None,
            "container_format": "bare",
            "os_distro": image.osname.lower(),
            "os_version": image.osversion,
            "visibility": "public" if is_public else "private",
            # AppDB properties
            "vmcatcher_event_dc_description": image.description,
            "vmcatcher_event_ad_mpuri": image.mpuri,
            "appdb_id": image.identifier,
            "sha512": image.sha512,
        }

        appliance_attrs = getattr(image, appliance_attributes)
        if appliance_attrs:
            metadata['APPLIANCE_ATTRIBUTES'] = json.dumps(appliance_attrs)

        for k, v in kwargs.iteritems():
            if k in metadata:
                raise exception.MetadataOverwriteNotSupported(key=k)
            metadata[k] = v

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
                      "them manually and run atrope again: %s", images)
            raise exception.DuplicatedImage(images=images)

        try:
            glance_image = images.pop()
        except IndexError:
            glance_image = None
        else:
            if glance_image.sha512 != image.sha512:
                LOG.warning("Image '%s' is '%s' in glance but sha512 checksums"
                            "are different, deleting it and reuploading.",
                            image.identifier, glance_image.id)
                self.client.images.delete(glance_image.id)
                glance_image = None

        metadata["disk_format"], image_fd = image.get_disk()
        metadata["disk_format"].lower()
        if metadata["disk_format"] not in ['ami', 'ari', 'aki', 'vhd',
                                           'vhdx', 'vmdk', 'raw', 'qcow2',
                                           'vdi', 'iso', 'ploop', 'root-tar']:
            metadata["disk_format"] = "raw"

        if not glance_image:
            LOG.debug("Creating image '%s'.", image.identifier)
            glance_image = self.client.images.create(**metadata)

        if glance_image.status == "queued":
            LOG.debug("Uploading image '%s'.", image.identifier)
            self._upload(glance_image.id, image_fd)

        if glance_image.status == "active":
            LOG.info("Image '%s' stored in glance as '%s'.",
                     image.identifier, glance_image.id)

        if metadata.get("vo", None) is not None:
            tenant = self._get_vo_tenant_mapping(metadata["vo"])
            if tenant is not None:
                try:
                    self.client.images.update(glance_image.id,
                                              visibility="shared")
                    self.client.image_members.create(glance_image.id,
                                                     tenant)
                except glance_exc.HTTPConflict:
                    LOG.debug("Image '%s' already associated with VO '%s', "
                              "tenant '%s'",
                              image.identifier, metadata["vo"], tenant)
                finally:
                    client = self._get_glance_client(project_id=tenant)
                    client.image_members.update(glance_image.id,
                                                tenant, 'accepted')

                    LOG.info("Image '%s' associated with VO '%s', tenant '%s'",
                             image.identifier, metadata["vo"], tenant)
            else:
                LOG.error("Image '%s' is associated with VO '%s' but no "
                          "tenant mapping could be found!",
                          image.identifier, metadata["vo"])

    def sync(self, image_list):
        """Sunc image list with dispached images."""
        kwargs = {
            "filters": {
                "tag": ["atrope"],
                "image_list": image_list.name,
            }
        }
        valid_images = [i.identifier
                        for i in image_list.get_valid_subscribed_images()]
        for image in self.client.images.list(**kwargs):
            appdb_id = image.get("appdb_id", "")
            if appdb_id not in valid_images:
                LOG.warning("Glance image '%s' is not valid anymore, "
                            "deleting it", image.id)
                self.client.images.delete(image.id)

        LOG.info("Sync terminated for image list '%s'", image_list.name)

    def _upload(self, id, image_fd):
        self.client.images.upload(id, image_fd)

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
