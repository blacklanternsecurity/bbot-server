import sys
import logging
import importlib
import traceback
from pathlib import Path
from contextlib import suppress

from bbot_server.errors import BBOTServerError

log = logging.getLogger(__name__)

modules_dir = Path(__file__).parent

# REST API applets
API_MODULES = {}

# command line modules (bbctl)
CLI_MODULES = {}


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
                        parent_name = "root_applet"
                    module_family = module_dict.get(parent_name, {})
                    # if we get a duplicate module name, raise an error
                    if module_name in module_family:
                        raise BBOTServerError(
                            f'Encountered duplicate module "{module_name}" in {file} ({module_dict})'
                        )
                    module_family[module_name] = value
                    module_dict[parent_name] = module_family


# search recursively for every python file in the modules dir
python_files = list(modules_dir.rglob("*.py"))

# load applets
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
