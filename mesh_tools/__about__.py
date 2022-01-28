#! python3  # noqa: E265

"""
    Metadata about the package to easily retrieve informations about it.
    See: https://packaging.python.org/guides/single-sourcing-package-version/
"""

# ############################################################################
# ########## Libraries #############
# ##################################

# standard library
from configparser import ConfigParser
from datetime import date
from pathlib import Path

# ############################################################################
# ########## Globals ###############
# ##################################

__all__ = [
    "__author__",
    "__copyright__",
    "__email__",
    "__license__",
    "__summary__",
    "__title__",
    "__uri__",
    "__version__",
]

DIR_PLUGIN_ROOT = Path(__file__).parent
PLG_METADATA_FILE = DIR_PLUGIN_ROOT.resolve() / "metadata.txt"

# ############################################################################
# ########## Functions #############
# ##################################


def plugin_metadata_as_dict() -> dict:
    """Read plugin metadata.txt and returns it as a Python dict.

    Raises:
        IOError: if metadata.txt is not found

    Returns:
        dict: dict of dicts.
    """
    config = ConfigParser()
    if PLG_METADATA_FILE.is_file():
        config.read(PLG_METADATA_FILE.resolve(), encoding="UTF-8")
        return {s: dict(config.items(s)) for s in config.sections()}
    raise IOError(f"Plugin metadata.txt not found at: {PLG_METADATA_FILE}")


# ############################################################################
# ########## Variables #############
# ##################################

# store full metadata.txt as dict into a var
__plugin_md__ = plugin_metadata_as_dict()

__author__ = __plugin_md__.get("general").get("author")
__copyright__ = f"2021 - {date.today().year}, {__author__}"
__email__ = __plugin_md__.get("general").get("email")
__keywords__ = [t.strip() for t in __plugin_md__.get("general").get("repository").split("tags")]
__license__ = "GPLv3"
__summary__ = f'{__plugin_md__.get("general").get("description")}\n{__plugin_md__.get("general").get("about")}'

__title__ = __plugin_md__.get("general").get("name")
__title_clean__ = "".join(e for e in __title__ if e.isalnum())

__uri_homepage__ = __plugin_md__.get("general").get("homepage")
__uri_repository__ = __plugin_md__.get("general").get("repository")
__uri_tracker__ = __plugin_md__.get("general").get("tracker")
__uri__ = __uri_repository__

__version__ = __plugin_md__.get("general").get("version")
__version_info__ = tuple(int(num) if num.isdigit() else num for num in __version__.replace("-", ".", 1).split("."))

# #############################################################################
# ##### Main #######################
# ##################################
if __name__ == "__main__":
    plugin_md = plugin_metadata_as_dict()
    assert isinstance(plugin_md, dict)
    assert plugin_md.get("general").get("name") == __title__
    print("Plugin : " + __title__)
    print("Plugin (clean) : " + __title_clean__)
    print("Par : " + __author__)
    print("Version : " + __version__)
    print("Description : " + __summary__)
    print(
        f'Pour : {plugin_md.get("general").get("qgisminimumversion")} < QGIS < {plugin_md.get("general").get("qgismaximumversion", "3.99")}'
    )
    print(__title_clean__)
