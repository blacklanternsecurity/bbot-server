import ast
from bbot_server.preloader import APPLETS

# Here, we search the current directory for applets and do some preloading on each one.
# We use AST to parse the files and look for classes that inherit from BaseAssetFields.
# We keep track of these classes, which will later be merged into the final asset model.
# This enables applets to define custom fields along with validation logic etc., that will live
# in the asset model.

# these imports are needed for the preloading process
from typing import List, Optional, Dict, Any, Annotated  # noqa: F401
from bbot_server.assets.custom_fields import CustomAssetFields  # noqa: F401
from pydantic import Field, BeforeValidator, AfterValidator, UUID4  # noqa: F401

ASSET_FIELD_MODELS = []


for applet_name, applet_file in APPLETS.items():
    try:
        # Parse the file with AST
        with open(applet_file, "r") as f:
            source = f.read()
            tree = ast.parse(source)

        # Look for any class that inherits from BaseAssetFields
        asset_fields_class = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.bases:
                # Check each base class to see if it's BaseAssetFields
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "CustomAssetFields":
                        asset_fields_class = node
                        break
                if asset_fields_class:
                    break

        if not asset_fields_class:
            continue  # No class inheriting from BaseAssetFields found in this applet

        # Process the asset fields class
        class_source = ast.get_source_segment(source, asset_fields_class)

        # Create a unique namespace to avoid variable collisions
        local_namespace = {}

        # Execute the class definition in the isolated namespace
        # Pass globals() as the globals parameter to provide access to imported modules
        exec(class_source, globals(), local_namespace)

        # Get the class from the local namespace using its original name
        fields_class = local_namespace[asset_fields_class.name]

        # we're only interested in classes that
        if getattr(fields_class, "__tablename__", None) is None:
            # Add the class itself to the models
            ASSET_FIELD_MODELS.append(fields_class)

    except Exception as e:
        # Log error but continue with other applets
        print(f"Error loading asset fields from {applet_file}: {e}")


# now we merge all the custom asset fields into the master asset model

from ..models.asset_models import BaseAssetFacet
from bbot_server.utils.misc import combine_pydantic_models


class Asset(BaseAssetFacet):
    __tablename__ = "assets"


# merge all the custom asset fields into the master asset model
Asset = combine_pydantic_models(ASSET_FIELD_MODELS, model_name="Asset", base_model=Asset)
