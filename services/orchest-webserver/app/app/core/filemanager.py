import logging
import os
import re
from typing import Optional, Tuple

from flask import jsonify

from _orchest.internals import config as _config
from app.models import Project

logger = logging.getLogger(__name__)

PROJECT_DIR_PATH = _config.PROJECT_DIR
DATA_DIR_PATH = _config.DATA_DIR
ALLOWED_ROOTS = [PROJECT_DIR_PATH, DATA_DIR_PATH]


def allowed_file(filename):
    """Answers: Is the given file allowed?

    Note:
        Allows all files for now.

    """
    return True


def construct_root_dir_path(root: Optional[str], project_uuid: Optional[str]) -> str:
    """
    if root is not provided, default to PROJECT_DIR_PATH;

    if root is PROJECT_DIR_PATH, project_uuid is required;
    """

    root = PROJECT_DIR_PATH if root is None else root

    if root not in ALLOWED_ROOTS:
        raise ValueError(f"Received illegal root path: {root}.")

    if root == DATA_DIR_PATH:
        return _config.USERDIR_DATA

    if root == PROJECT_DIR_PATH and project_uuid is None:
        raise ValueError("project_uuid is required.")

    project = Project.query.filter(Project.uuid == project_uuid).first()

    if project is None:
        raise ValueError("project not found.")

    return f"{_config.USERDIR_PROJECTS}/{project.path}"


def find_unique_duplicate_filepath(fp):
    counter = 1
    new_path_fs = "{base} ({counter}){ext}"

    if fp.endswith("/"):
        basename = os.path.basename(fp[:-1])
        ext = ""
        base_no_ext = basename
    else:
        basename = os.path.basename(fp)
        _, ext = os.path.splitext(fp)
        if len(ext) > 0:
            base_no_ext = basename[: -len(ext)]
        else:
            base_no_ext = basename

    # Try to find existing counter ending
    regex = r".*? \((\d+)\)$"
    matches = re.finditer(regex, base_no_ext)

    group_match = None
    for _, match in enumerate(matches, start=1):
        if len(match.group()) > 0:
            group_match = match.group(1)

    # Strip off the (<number>) match
    if group_match is not None:
        base_no_ext = base_no_ext[: -(len(group_match) + 3)]

    while True:
        new_path = os.path.join(
            os.path.abspath(os.path.join(fp, os.pardir)),
            new_path_fs.format(base=base_no_ext, counter=counter, ext=ext),
        )

        if os.path.isfile(new_path) or os.path.isdir(new_path):
            counter += 1
            continue
        else:
            return new_path


def generate_abs_path(path, root, dir, is_dir=False):
    """
    This generates a new absolute path, relative from the `dir`
    """
    return (
        "/" + os.path.relpath(os.path.join(root, path), dir) + ("/" if is_dir else "")
    )


def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, _, files in os.walk(path):
        for file in files:
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(os.path.join(root, file), os.path.join(path, "..")),
            )


def generate_tree(dir, path_filter="/", allowed_file_extensions=[], depth=3):

    if not os.path.isdir(dir):
        return jsonify({"message": f"Dir {dir} not found."}), 404

    # Init structs
    tree = {
        "type": "directory",
        "name": os.path.basename(path_filter[:-1]),
        "path": path_filter,
        "children": [],
    }
    if path_filter == "/":
        tree["root"] = True
    else:
        tree["depth"] = path_filter.count(os.sep) - 1

    dir_nodes = {}

    if path_filter != "/":
        filtered_path = os.path.join(dir, path_filter[1:-1])
    else:
        filtered_path = dir

    dir_nodes[filtered_path] = tree

    dir_depth = dir.count(os.sep)

    logger.debug("Walking %s " % filtered_path)
    for root, dirs, files in os.walk(filtered_path):

        dir_delete_set = set()
        for dirname in dirs:

            dir_path = os.path.join(root, dirname)
            dir_node = {
                "type": "directory",
                "name": dirname,
                "children": [],
                "depth": root.count(os.sep) - dir_depth + 1,
                "path": generate_abs_path(dirname, root, dir, is_dir=True),
            }

            relative_depth = dir_node["depth"] - (path_filter.count(os.sep) - 2)
            if relative_depth > depth:  # Account for filtered_path
                dir_delete_set.add(dirname)

            logger.debug(relative_depth)

            dir_nodes[dir_path] = dir_node
            dir_nodes[root]["children"].append(dir_node)

        # Filter dirs in delete set
        dirs[:] = [d for d in dirs if d not in dir_delete_set]

        for filename in files:

            if (
                len(allowed_file_extensions) == 0
                or filename.split(".")[-1] in allowed_file_extensions
            ):
                file_node = {
                    "type": "file",
                    "name": filename,
                    "path": generate_abs_path(filename, root, dir),
                }

                # this key should always exist
                try:
                    dir_nodes[root]["children"].append(file_node)
                except KeyError as e:
                    logger.error(
                        "Key %s does not exist in dir_nodes %s. Error: %s"
                        % (root, dir_nodes, e)
                    )
                except Exception as e:
                    logger.error("Error: %e" % e)

        # Sort files & directories (directories always go before files)
        if "children" in dir_nodes[root]:
            dir_nodes[root]["children"].sort(
                key=lambda e: {"directory": "a.", "file": "b."}[e["type"]] + e["name"]
            )
    return jsonify(tree)


def processRequest(
    root: Optional[str],
    path: Optional[str],
    project_uuid: Optional[str],
    depth: Optional[str] = None,
    is_path_required: Optional[bool] = True,
) -> Tuple[str, Optional[bool]]:
    if root is None:
        raise ValueError("The root query argument is required.")

    if root == PROJECT_DIR_PATH and project_uuid is None:
        raise ValueError(
            "The project_uuid query argument is required if root is /project-dir."
        )

    if depth is not None:
        try:
            depth = int(depth, 10)
        except Exception:
            raise ValueError("Invalid value for the depth query argument.")

    # in most cases, path is required,
    # except for /async/file-management/browse,
    # where either depth and path should be provided
    if depth is None and path is None:
        extra_explanation = (
            "" if is_path_required else " if the depth query argumentis not present"
        )
        raise ValueError(f"The path query argument is required{extra_explanation}.")

    if path is not None:
        if not path.startswith("/"):
            raise ValueError(
                "The path query argument should always start with a forward-slash: /"
            )

    root_dir_path = construct_root_dir_path(root=root, project_uuid=project_uuid)

    return (root_dir_path, depth)
