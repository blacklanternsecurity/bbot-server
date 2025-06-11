import ast
import sys
import logging
import importlib
import traceback
from pathlib import Path
from contextlib import suppress

from bbot_server.errors import BBOTServerError

# needed for asset model preloading
from bbot_server.assets import CustomAssetFields  # noqa: F401
from typing import List, Optional, Dict, Any, Annotated  # noqa: F401
from pydantic import Field, BeforeValidator, AfterValidator, UUID4  # noqa: F401

log = logging.getLogger(__name__)


modules_dir = Path(__file__).parent

# models that add custom fields to the main asset model
ASSET_FIELD_MODELS = []

# REST API applets
API_MODULES = {}

# command line modules (bbctl)
CLI_MODULES = {}


def check_for_asset_field_models(source_code, filename):
    """
    Here, we preload an applet's source code and look for classes that inherit from BaseAssetFields.
    We keep track of these classes, which will later be merged into the final asset model.

    This solves a chicken-and-egg problem where applets need to modify the primary asset model,
    while also needing access to it in its final form.
    """

    tree = ast.parse(source_code)

    # Look for any class that inherits from BaseAssetFields
    asset_fields_classes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.bases:
            # Check each base class to see if it's BaseAssetFields
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "CustomAssetFields":
                    asset_fields_classes.append(node)
                    break

    # Create a unique namespace to avoid variable collisions
    local_namespace = {}

    for asset_fields_class in asset_fields_classes:
        # Process the asset fields class
        class_source = ast.get_source_segment(source_code, asset_fields_class)

        # Execute the class definition in the isolated namespace
        # Pass globals() as the globals parameter to provide access to imported modules
        try:
            exec(class_source, globals(), local_namespace)
        except BaseException:
            log.error(
                f"Error processing asset fields class {asset_fields_class.name} in {filename.name}: {sys.exc_info()[1]}"
            )
            log.error(traceback.format_exc())
            continue

        # Get the class from the local namespace using its original name
        fields_class = local_namespace[asset_fields_class.name]

        # we're only interested in classes that
        if getattr(fields_class, "__tablename__", None) is None:
            # Add the class itself to the models
            ASSET_FIELD_MODELS.append(fields_class)


# search recursively for every python file in the modules dir
python_files = list(modules_dir.rglob("*.py"))


### PRELOADING ###

# preload asset fields before loading any other modules
for file in python_files:
    if file.stem.endswith("_api"):
        source_code = open(file).read()
        # check for custom asset fields
        check_for_asset_field_models(source_code, file)

# now we merge all the custom asset fields into the master asset model

from ..models.asset_models import BaseAssetFacet
from bbot_server.utils.misc import combine_pydantic_models
import bbot_server.assets as assetlib


class Asset(BaseAssetFacet):
    __tablename__ = "assets"


# merge all the custom asset fields into the master asset model
Asset = combine_pydantic_models(ASSET_FIELD_MODELS, model_name="Asset", base_model=Asset)
assetlib.Asset = Asset
assetlib.ASSET_FIELD_MODELS = ASSET_FIELD_MODELS

### END PRELOADING ###


def load_python_file(file, namespace, module_dict, base_class_name, module_key_attr):
    spec = importlib.util.spec_from_file_location(namespace, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[namespace] = module
    spec.loader.exec_module(module)

    # for every top-level variable in the .py file
    for variable in module.__dict__.keys():
        # get its value
        value = getattr(module, variable)
        with suppress(TypeError):
            # Check if it's a class and not the base class itself
            if isinstance(value, type) and value.__name__ != base_class_name:
                # Get the class names from the MRO
                class_names = [cls.__name__ for cls in value.__mro__]
                # Check if the base class name is in the MRO
                if base_class_name in class_names:
                    module_name = getattr(value, module_key_attr, "")
                    if not module_name:
                        log.error(f"Module {value.__name__} does not define required attribute{module_key_attr}")
                    parent_name = getattr(value, "attach_to", "")
                    if not parent_name:
                        log.error(f"Module {value.__name__} does not define required attribute 'attach_to'")
                    module_family = module_dict.get(parent_name, {})
                    # if we get a duplicate module name, raise an error
                    if module_name in module_family:
                        raise BBOTServerError(
                            f'Encountered duplicate module "{module_name}" in {file} ({module_dict})'
                        )
                    module_family[module_name] = value
                    module_dict[parent_name] = module_family


# load applets first
for file in python_files:
    if file.stem.endswith("_api"):
        module_name = file.stem.rsplit("_applet", 1)[0]
        namespace = f"bbot_server.modules.applets.{module_name}"
        module = load_python_file(
            file=file,
            namespace=namespace,
            module_dict=API_MODULES,
            base_class_name="BaseApplet",
            module_key_attr="name_lowercase",
        )

# then CLI modules
for file in python_files:
    if file.stem.endswith("_cli"):
        module_name = file.stem.rsplit("_cli", 1)[0]
        namespace = f"bbot_server.modules.cli.{module_name}"
        load_python_file(
            file=file,
            namespace=namespace,
            module_dict=CLI_MODULES,
            base_class_name="BaseBBCTL",
            module_key_attr="command",
        )
