# Copyright 2019-2021 ObjectBox Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from objectbox.c import *
from objectbox.model import Model, IdUid
from objectbox.model.entity import Entity
from objectbox.model.properties import Property, Id
from objectbox.objectbox import ObjectBox
import json


def extract_id_uid(identifier):
    id_str, uid_str = identifier.split(":")
    return int(id_str), int(uid_str)


class Builder:
    def __init__(self):
        self._model = Model()
        self._directory = ""

    def directory(self, path: str) -> "Builder":
        self._directory = path
        return self

    def model(self, model: Model) -> "Builder":
        self._model = model
        self._model._finish()
        return self

    def build(self) -> "ObjectBox":
        c_options = obx_opt()

        try:
            if len(self._directory) > 0:
                obx_opt_directory(c_options, c_str(self._directory))

            obx_opt_model(c_options, self._model._c_model)
        except CoreException:
            obx_opt_free(c_options)
            raise

        c_store = obx_store_open(c_options)
        return ObjectBox(c_store)

    def from_json(self, file: str, identifier_name="id") -> "Builder":
        with open(file) as f:
            data = json.load(f)

        model = Model()
        model.last_entity_id = IdUid(*extract_id_uid(data["lastEntityId"]))

        for entity in data["entities"]:
            entity_name = entity["name"]
            entity_id, entity_uid = extract_id_uid(entity["id"])
            entity_last_property_id, entity_last_property_uid = extract_id_uid(
                entity["lastPropertyId"]
            )
            props = {}
            for property in entity["properties"]:
                flags = None
                index_type = None
                id, uid = extract_id_uid(property["id"])
                name = property["name"]
                prop_type = property["type"]
                try:
                    py_type = py_types_lookup[prop_type]
                except:
                    print(f"Property type {prop_type} not found. Skipping...")
                    continue
                try:
                    flags = int(property["flags"])
                    if flags > 999:
                        # TODO not yet implemented in python api
                        index_type = flags
                        flags = None
                except:
                    pass
                props[name] = (
                    Property(
                        py_type,
                        type=prop_type,
                        id=id,
                        uid=uid,
                        property_flags=flags,
                        index_type=index_type,
                    )
                    if name != identifier_name
                    else Id(id=id, uid=uid)
                )

            # build model
            model.entity(
                Entity(
                    cls=type(entity_name, (object,), props),
                    id=entity_id,
                    uid=entity_uid,
                ),
                last_property_id=IdUid(
                    entity_last_property_id, entity_last_property_uid
                ),
            )

        return self.model(model)

    def __str__(self) -> str:
        try:
            class_dict = self._model.get_classes(expand=True)
        except:
            return "Builder: empty"
        out_str = "Builder has the following classes:\n"
        for k, v in class_dict.items():
            out_str += f"{k}: {v}\n"

        return out_str
