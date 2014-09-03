import sys

from oslo.config import cfg

import atrope.config
import atrope.image_list

CONF = cfg.CONF


def main():
    atrope.config.parse_args(sys.argv)
    i = atrope.image_list.ImageLists()
#    i


if __name__ == "__main__":
    main()
