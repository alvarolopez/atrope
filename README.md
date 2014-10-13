# atrope

Atrope is a program intended to keep in sync one or several image list sources
(such as RSS, HEPiX VM image lists, EGI's AppDB image lists, etc.) with a local
cache or with an image catalog (such as OpenStack glance).

* Free software: Apache license
* Source: https://github.com/alvarolopez/atrope
* Bugs: https://github.com/alvarolopez/atrope/issues

## Features

### Image Sources

Current list of supported image lists:

* HePIX VM image lists.

### Dispatchers

Apart from the sync with a local cache directory, atrope is able to dispatch and sync that cache with an image catalog. The current list of dispatchers is:

* OpenStack Glance image catalog.
