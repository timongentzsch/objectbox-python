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


import ctypes.util
import os
import platform
from objectbox.version import Version

# This file contains C-API bindings based on lib/objectbox.h, linking to the 'objectbox' shared library.
# The bindings are implementing using ctypes, see https://docs.python.org/dev/library/ctypes.html for introduction.


# Version of the library used by the binding. This version is checked at runtime to ensure binary compatibility.
# Don't forget to update download-c-lib.py when upgrading to a newer version.
required_version = "0.21.0"


def shlib_name(library: str) -> str:
    """Returns the platform-specific name of the shared library"""
    if platform.system() == "Linux":
        return "lib" + library + ".so"
    elif platform.system() == "Windows":
        return library + ".dll"
    elif platform.system() == "Darwin":
        return "lib" + library + ".dylib"
    else:
        assert False, "Unsupported platform: " + platform.system()


# initialize the C library
lib_path = os.path.dirname(os.path.realpath(__file__))
lib_path = os.path.join(
    lib_path,
    "lib",
    platform.machine() if platform.system() != "Darwin" else "macos-universal",
    shlib_name("objectbox"),
)
C = ctypes.CDLL(lib_path)

# load the core library version
__major = ctypes.c_int(0)
__minor = ctypes.c_int(0)
__patch = ctypes.c_int(0)
C.obx_version(ctypes.byref(__major), ctypes.byref(__minor), ctypes.byref(__patch))

# C-api (core library) version
version_core = Version(__major.value, __minor.value, __patch.value)

assert (
    str(version_core) == required_version
), "Incorrect ObjectBox version loaded: %s instead of expected %s " % (
    str(version_core),
    required_version,
)

# define some basic types
obx_err = ctypes.c_int
obx_schema_id = ctypes.c_uint32
obx_uid = ctypes.c_uint64
obx_id = ctypes.c_uint64
obx_qb_cond = ctypes.c_int

# enums
OBXPropertyType = ctypes.c_int
OBXPropertyFlags = ctypes.c_int
OBXDebugFlags = ctypes.c_int
OBXPutMode = ctypes.c_int
OBXOrderFlags = ctypes.c_int


class OBX_model(ctypes.Structure):
    pass


OBX_model_p = ctypes.POINTER(OBX_model)


class OBX_store(ctypes.Structure):
    pass


OBX_store_p = ctypes.POINTER(OBX_store)


class OBX_store_options(ctypes.Structure):
    pass


OBX_store_options_p = ctypes.POINTER(OBX_store_options)


class OBX_bytes(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
    ]


OBX_bytes_p = ctypes.POINTER(OBX_bytes)


class OBX_bytes_array(ctypes.Structure):
    _fields_ = [
        ("data", OBX_bytes_p),
        ("count", ctypes.c_size_t),
    ]


OBX_bytes_array_p = ctypes.POINTER(OBX_bytes_array)


class OBX_id_array(ctypes.Structure):
    _fields_ = [
        ("ids", ctypes.POINTER(obx_id)),
        ("count", ctypes.c_size_t),
    ]


OBX_id_array_p = ctypes.POINTER(OBX_id_array)


class OBX_txn(ctypes.Structure):
    pass


OBX_txn_p = ctypes.POINTER(OBX_txn)


class OBX_box(ctypes.Structure):
    pass


OBX_box_p = ctypes.POINTER(OBX_box)


class OBX_async(ctypes.Structure):
    pass


OBX_async_p = ctypes.POINTER(OBX_async)


class OBX_query_builder(ctypes.Structure):
    pass


OBX_query_builder_p = ctypes.POINTER(OBX_query_builder)


class OBX_query(ctypes.Structure):
    pass


OBX_query_p = ctypes.POINTER(OBX_query)

# manually configure error methods, we can't use `fn()` defined below yet due to circular dependencies
C.obx_last_error_message.restype = ctypes.c_char_p
C.obx_last_error_code.restype = obx_err


class CoreException(Exception):
    codes = {
        0: "SUCCESS",
        404: "NOT_FOUND",
        10001: "ILLEGAL_STATE",
        10002: "ILLEGAL_ARGUMENT",
        10003: "ALLOCATION",
        10097: "NO_ERROR_INFO",
        10098: "GENERAL",
        10099: "UNKNOWN",
        10101: "DB_FULL",
        10102: "MAX_READERS_EXCEEDED",
        10103: "STORE_MUST_SHUTDOWN",
        10199: "STORAGE_GENERAL",
        10201: "UNIQUE_VIOLATED",
        10202: "NON_UNIQUE_RESULT",
        10203: "PROPERTY_TYPE_MISMATCH",
        10299: "CONSTRAINT_VIOLATED",
        10301: "STD_ILLEGAL_ARGUMENT",
        10302: "STD_OUT_OF_RANGE",
        10303: "STD_LENGTH",
        10304: "STD_BAD_ALLOC",
        10305: "STD_RANGE",
        10306: "STD_OVERFLOW",
        10399: "STD_OTHER",
        10501: "SCHEMA",
        10502: "FILE_CORRUPT",
    }

    def __init__(self, code):
        self.code = code
        self.message = py_str(C.obx_last_error_message())
        name = self.codes[code] if code in self.codes else "n/a"
        super(CoreException, self).__init__("%d (%s) - %s" % (code, name, self.message))


class NotFoundException(Exception):
    pass


# assert the the returned obx_err is empty
def check_obx_err(code: obx_err, func, args) -> obx_err:
    if code == 404:
        raise NotFoundException()
    elif code != 0:
        raise CoreException(code)

    return code


# assert that the returned pointer/int is non-empty
def check_result(result, func, args):
    if not result:
        raise CoreException(C.obx_last_error_code())
    return result


# creates a global function "name" with the given restype & argtypes, calling C function with the same name.
# restype is used for error checking: if not None, check_result will throw an exception if the result is empty.
def c_fn(name: str, restype: type, argtypes):
    func = C.__getattr__(name)
    func.argtypes = argtypes
    func.restype = restype

    if restype is not None:
        func.errcheck = check_result

    return func


# like c_fn, but for functions returning obx_err
def c_fn_rc(name: str, argtypes):
    func = C.__getattr__(name)
    func.argtypes = argtypes
    func.restype = obx_err
    func.errcheck = check_obx_err

    return func


def py_str(ptr: ctypes.c_char_p) -> str:
    return ctypes.c_char_p(ptr).value.decode("utf-8")


def c_str(string: str) -> ctypes.c_char_p:
    return string.encode("utf-8")


def c_voidp_as_bytes(voidp, size):
    # TODO verify which of the following two approaches is better. Performance-wise, it seems the same.

    # slice the data from the pointer
    # return ctypes.cast(voidp, ctypes.POINTER(ctypes.c_char))[:size]

    # create a memory view
    return memoryview(
        ctypes.cast(voidp, ctypes.POINTER(ctypes.c_ubyte * size))[0]
    ).tobytes()


# OBX_model* (void);
obx_model = c_fn("obx_model", OBX_model_p, [])

# obx_err (OBX_model* model, const char* name, obx_schema_id entity_id, obx_uid entity_uid);
obx_model_entity = c_fn_rc(
    "obx_model_entity", [OBX_model_p, ctypes.c_char_p, obx_schema_id, obx_uid]
)

# obx_err (OBX_model* model, const char* name, OBXPropertyType type, obx_schema_id property_id, obx_uid property_uid);
obx_model_property = c_fn_rc(
    "obx_model_property",
    [OBX_model_p, ctypes.c_char_p, OBXPropertyType, obx_schema_id, obx_uid],
)

# obx_err (OBX_model* model, OBXPropertyFlags flags);
obx_model_property_flags = c_fn_rc(
    "obx_model_property_flags", [OBX_model_p, OBXPropertyFlags]
)

# obx_err (OBX_model*, obx_schema_id entity_id, obx_uid entity_uid);
obx_model_last_entity_id = c_fn(
    "obx_model_last_entity_id", None, [OBX_model_p, obx_schema_id, obx_uid]
)

# obx_err (OBX_model* model, obx_schema_id index_id, obx_uid index_uid);
obx_model_last_index_id = c_fn(
    "obx_model_last_index_id", None, [OBX_model_p, obx_schema_id, obx_uid]
)

# obx_err (OBX_model* model, obx_schema_id relation_id, obx_uid relation_uid);
obx_model_last_relation_id = c_fn(
    "obx_model_last_relation_id", None, [OBX_model_p, obx_schema_id, obx_uid]
)

# obx_err (OBX_model* model, obx_schema_id property_id, obx_uid property_uid);
obx_model_entity_last_property_id = c_fn_rc(
    "obx_model_entity_last_property_id", [OBX_model_p, obx_schema_id, obx_uid]
)

# OBX_store_options* ();
obx_opt = c_fn("obx_opt", OBX_store_options_p, [])

# obx_err (OBX_store_options* opt, const char* dir);
obx_opt_directory = c_fn_rc("obx_opt_directory", [OBX_store_options_p, ctypes.c_char_p])

# void (OBX_store_options* opt, size_t size_in_kb);
obx_opt_max_db_size_in_kb = c_fn(
    "obx_opt_max_db_size_in_kb", None, [OBX_store_options_p, ctypes.c_size_t]
)

# void (OBX_store_options* opt, int file_mode);
obx_opt_file_mode = c_fn(
    "obx_opt_file_mode", None, [OBX_store_options_p, ctypes.c_uint]
)

# void (OBX_store_options* opt, int max_readers);
obx_opt_max_readers = c_fn(
    "obx_opt_max_readers", None, [OBX_store_options_p, ctypes.c_uint]
)

# obx_err (OBX_store_options* opt, OBX_model* model);
obx_opt_model = c_fn_rc("obx_opt_model", [OBX_store_options_p, OBX_model_p])

# void (OBX_store_options* opt);
obx_opt_free = c_fn("obx_opt_free", None, [OBX_store_options_p])

# OBX_store* (const OBX_store_options* options);
obx_store_open = c_fn("obx_store_open", OBX_store_p, [OBX_store_options_p])

# obx_err (OBX_store* store);
obx_store_close = c_fn_rc("obx_store_close", [OBX_store_p])

# OBX_txn* (OBX_store* store);
obx_txn_write = c_fn("obx_txn_write", OBX_txn_p, [OBX_store_p])

# OBX_txn* (OBX_store* store);
obx_txn_read = c_fn("obx_txn_read", OBX_txn_p, [OBX_store_p])

# obx_err (OBX_txn* txn)
obx_txn_close = c_fn_rc("obx_txn_close", [OBX_txn_p])

# obx_err (OBX_txn* txn);
obx_txn_abort = c_fn_rc("obx_txn_abort", [OBX_txn_p])

# obx_err (OBX_txn* txn);
obx_txn_success = c_fn_rc("obx_txn_success", [OBX_txn_p])

# OBX_box* (OBX_store* store, obx_schema_id entity_id);
obx_box = c_fn("obx_box", OBX_box_p, [OBX_store_p, obx_schema_id])

# obx_err (OBX_box* box, obx_id id, const void** data, size_t* size);
obx_box_get = c_fn_rc(
    "obx_box_get",
    [
        OBX_box_p,
        obx_id,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_size_t),
    ],
)

# OBX_bytes_array* (OBX_box* box);
obx_box_get_all = c_fn("obx_box_get_all", OBX_bytes_array_p, [OBX_box_p])

# obx_id (OBX_box* box, obx_id id_or_zero);
obx_box_id_for_put = c_fn("obx_box_id_for_put", obx_id, [OBX_box_p, obx_id])

# obx_err (OBX_box* box, uint64_t count, obx_id* out_first_id);
obx_box_ids_for_put = c_fn_rc(
    "obx_box_ids_for_put", [OBX_box_p, ctypes.c_uint64, ctypes.POINTER(obx_id)]
)

# obx_err (OBX_box* box, obx_id id, const void* data, size_t size);
obx_box_put = c_fn_rc(
    "obx_box_put", [OBX_box_p, obx_id, ctypes.c_void_p, ctypes.c_size_t]
)

# obx_err (OBX_box* box, const OBX_bytes_array* objects, const obx_id* ids, OBXPutMode mode);
obx_box_put_many = c_fn_rc(
    "obx_box_put_many",
    [OBX_box_p, OBX_bytes_array_p, ctypes.POINTER(obx_id), OBXPutMode],
)

# obx_err (OBX_box* box, obx_id id);
obx_box_remove = c_fn_rc("obx_box_remove", [OBX_box_p, obx_id])

# obx_err (OBX_box* box, uint64_t* out_count);
obx_box_remove_all = c_fn_rc(
    "obx_box_remove_all", [OBX_box_p, ctypes.POINTER(ctypes.c_uint64)]
)

# obx_err (OBX_box* box, bool* out_is_empty);
obx_box_is_empty = c_fn_rc(
    "obx_box_is_empty", [OBX_box_p, ctypes.POINTER(ctypes.c_bool)]
)

# obx_err obx_box_count(OBX_box* box, uint64_t limit, uint64_t* out_count);
obx_box_count = c_fn_rc(
    "obx_box_count", [OBX_box_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)]
)

# OBX_query_builder* obx_query_builder(OBX_store* store, obx_schema_id entity_id);
obx_query_builder = c_fn(
    "obx_query_builder", OBX_query_builder_p, [OBX_store_p, obx_schema_id]
)

# OBX_C_API obx_err obx_qb_close(OBX_query_builder* builder);
obx_qb_close = c_fn_rc("obx_qb_close", [OBX_query_builder_p])

# OBX_C_API OBX_query* obx_query(OBX_query_builder* builder);
obx_query = c_fn("obx_query", OBX_query_p, [OBX_query_builder_p])

# OBX_C_API obx_err obx_qb_error_code(OBX_query_builder* builder);
obx_qb_error_code = c_fn_rc("obx_qb_error_code", [OBX_query_builder_p])

# OBX_C_API const char* obx_qb_error_message(OBX_query_builder* builder);
obx_qb_error_message = c_fn(
    "obx_qb_error_message", ctypes.c_char_p, [OBX_query_builder_p]
)

# OBX_C_API obx_qb_cond obx_qb_null(OBX_query_builder* builder, obx_schema_id property_id);
obx_qb_null = c_fn("obx_qb_null", obx_qb_cond, [OBX_query_builder_p, obx_schema_id])

# OBX_C_API obx_qb_cond obx_qb_not_null(OBX_query_builder* builder, obx_schema_id property_id);
obx_qb_not_null = c_fn(
    "obx_qb_not_null", obx_qb_cond, [OBX_query_builder_p, obx_schema_id]
)

# OBX_C_API obx_qb_cond obx_qb_equals_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                            bool case_sensitive);
obx_qb_equals_string = c_fn(
    "obx_qb_equals_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_co nd obx_qb_not_equals_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                               bool case_sensitive);
obx_qb_not_equals_string = c_fn(
    "obx_qb_not_equals_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_contains_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                              bool case_sensitive);
obx_qb_contains_string = c_fn(
    "obx_qb_contains_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_contains_element_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                      const char* value, bool case_sensitive);
obx_qb_contains_element_string = c_fn(
    "obx_qb_contains_element_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_contains_key_value_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                        const char* key, const char* value, bool case_sensitive);
obx_qb_contains_key_value_string = c_fn(
    "obx_qb_contains_key_value_string",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_bool,
    ],
)

# OBX_C_API obx_qb_cond obx_qb_starts_with_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                 const char* value, bool case_sensitive);
obx_qb_starts_with_string = c_fn(
    "obx_qb_starts_with_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_ends_with_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                               bool case_sensitive);
obx_qb_ends_with_string = c_fn(
    "obx_qb_ends_with_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_greater_than_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                  const char* value, bool case_sensitive);
obx_qb_greater_than_string = c_fn(
    "obx_qb_greater_than_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_greater_or_equal_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                      const char* value, bool case_sensitive);
obx_qb_greater_or_equal_string = c_fn(
    "obx_qb_greater_or_equal_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_less_than_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                               bool case_sensitive);
obx_qb_less_than_string = c_fn(
    "obx_qb_less_than_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_less_or_equal_string(OBX_query_builder* builder, obx_schema_id property_id,
#                                                   const char* value, bool case_sensitive);
obx_qb_less_or_equal_string = c_fn(
    "obx_qb_less_or_equal_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_in_strings(OBX_query_builder* builder, obx_schema_id property_id,
#                                         const char* const values[], size_t count, bool case_sensitive);
obx_qb_in_strings = c_fn(
    "obx_qb_in_strings",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_size_t,
        ctypes.c_bool,
    ],
)

# OBX_C_API obx_qb_cond obx_qb_any_equals_string(OBX_query_builder* builder, obx_schema_id property_id, const char* value,
#                                                bool case_sensitive);
obx_qb_any_equals_string = c_fn(
    "obx_qb_any_equals_string",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_char_p, ctypes.c_bool],
)

# OBX_C_API obx_qb_cond obx_qb_equals_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_equals_int = c_fn(
    "obx_qb_equals_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_not_equals_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_not_equals_int = c_fn(
    "obx_qb_not_equals_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_greater_than_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_greater_than_int = c_fn(
    "obx_qb_greater_than_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_greater_or_equal_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_greater_or_equal_int = c_fn(
    "obx_qb_greater_or_equal_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_less_than_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_less_than_int = c_fn(
    "obx_qb_less_than_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_less_or_equal_int(OBX_query_builder* builder, obx_schema_id property_id, int64_t value);
obx_qb_less_or_equal_int = c_fn(
    "obx_qb_less_or_equal_int",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_between_2ints(OBX_query_builder* builder, obx_schema_id property_id, int64_t value_a,
#                                            int64_t value_b);
obx_qb_between_2ints = c_fn(
    "obx_qb_between_2ints",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_int64, ctypes.c_int64],
)

# OBX_C_API obx_qb_cond obx_qb_in_int64s(OBX_query_builder* builder, obx_schema_id property_id, const int64_t values[],
#                                        size_t count);
obx_qb_in_int64s = c_fn(
    "obx_qb_in_int64s",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
    ],
)

# OBX_C_API obx_qb_cond obx_qb_not_in_int64s(OBX_query_builder* builder, obx_schema_id property_id,
#                                            const int64_t values[], size_t count);
obx_qb_not_in_int64s = c_fn(
    "obx_qb_not_in_int64s",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
    ],
)

# OBX_C_API obx_qb_cond obx_qb_in_int32s(OBX_query_builder* builder, obx_schema_id property_id, const int32_t values[],
#                                        size_t count);
obx_qb_in_int32s = c_fn(
    "obx_qb_in_int32s",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_size_t,
    ],
)

# OBX_C_API obx_qb_cond obx_qb_not_in_int32s(OBX_query_builder* builder, obx_schema_id property_id,
#                                            const int32_t values[], size_t count);
obx_qb_not_in_int32s = c_fn(
    "obx_qb_not_in_int32s",
    obx_qb_cond,
    [
        OBX_query_builder_p,
        obx_schema_id,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_size_t,
    ],
)


# OBX_C_API obx_qb_cond obx_qb_greater_than_double(OBX_query_builder* builder, obx_schema_id property_id, double value);
obx_qb_greater_than_double = c_fn(
    "obx_qb_greater_than_double",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_double],
)

# OBX_C_API obx_qb_cond obx_qb_greater_or_equal_double(OBX_query_builder* builder, obx_schema_id property_id,
#                                                      double value);
obx_qb_greater_or_equal_double = c_fn(
    "obx_qb_greater_or_equal_double",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_double],
)

# OBX_C_API obx_qb_cond obx_qb_less_than_double(OBX_query_builder* builder, obx_schema_id property_id, double value);
obx_qb_less_than_double = c_fn(
    "obx_qb_less_than_double",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_double],
)

# OBX_C_API obx_qb_cond obx_qb_less_or_equal_double(OBX_query_builder* builder, obx_schema_id property_id, double value);
obx_qb_less_or_equal_double = c_fn(
    "obx_qb_less_or_equal_double",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_double],
)

# OBX_C_API obx_qb_cond obx_qb_between_2doubles(OBX_query_builder* builder, obx_schema_id property_id, double value_a,
#                                               double value_b);
obx_qb_between_2doubles = c_fn(
    "obx_qb_between_2doubles",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_double, ctypes.c_double],
)

# OBX_C_API obx_qb_cond obx_qb_equals_bytes(OBX_query_builder* builder, obx_schema_id property_id, const void* value,
#                                           size_t size);
obx_qb_equals_bytes = c_fn(
    "obx_qb_equals_bytes",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_void_p, ctypes.c_size_t],
)

# OBX_C_API obx_qb_cond obx_qb_greater_than_bytes(OBX_query_builder* builder, obx_schema_id property_id,
#                                                 const void* value, size_t size);
obx_qb_greater_than_bytes = c_fn(
    "obx_qb_greater_than_bytes",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_void_p, ctypes.c_size_t],
)

# OBX_C_API obx_qb_cond obx_qb_greater_or_equal_bytes(OBX_query_builder* builder, obx_schema_id property_id,
#                                                     const void* value, size_t size);
obx_qb_greater_or_equal_bytes = c_fn(
    "obx_qb_greater_or_equal_bytes",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_void_p, ctypes.c_size_t],
)

# OBX_C_API obx_qb_cond obx_qb_less_than_bytes(OBX_query_builder* builder, obx_schema_id property_id, const void* value,
#                                              size_t size);
obx_qb_less_than_bytes = c_fn(
    "obx_qb_less_than_bytes",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_void_p, ctypes.c_size_t],
)

# OBX_C_API obx_qb_cond obx_qb_less_or_equal_bytes(OBX_query_builder* builder, obx_schema_id property_id,
#                                                  const void* value, size_t size);
obx_qb_less_or_equal_bytes = c_fn(
    "obx_qb_less_or_equal_bytes",
    obx_qb_cond,
    [OBX_query_builder_p, obx_schema_id, ctypes.c_void_p, ctypes.c_size_t],
)

# OBX_C_API obx_qb_cond obx_qb_all(OBX_query_builder* builder, const obx_qb_cond conditions[], size_t count);
obx_qb_all = c_fn(
    "obx_qb_all", obx_qb_cond, [OBX_query_builder_p, obx_qb_cond, ctypes.c_size_t]
)

# OBX_C_API obx_qb_cond obx_qb_any(OBX_query_builder* builder, const obx_qb_cond conditions[], size_t count);
obx_qb_any = c_fn(
    "obx_qb_any", obx_qb_cond, [OBX_query_builder_p, obx_qb_cond, ctypes.c_size_t]
)

# OBX_C_API obx_err obx_qb_param_alias(OBX_query_builder* builder, const char* alias);
obx_qb_param_alias = c_fn_rc(
    "obx_qb_param_alias", [OBX_query_builder_p, ctypes.c_char_p]
)

# OBX_C_API obx_err obx_qb_order(OBX_query_builder* builder, obx_schema_id property_id, OBXOrderFlags flags);
obx_qb_order = c_fn_rc(
    "obx_qb_order", [OBX_query_builder_p, obx_schema_id, OBXOrderFlags]
)

# OBX_C_API OBX_query* obx_query(OBX_query_builder* builder);
obx_query = c_fn("obx_query", OBX_query_p, [OBX_query_builder_p])

# OBX_C_API obx_err obx_query_close(OBX_query* query);
obx_query_close = c_fn_rc("obx_query_close", [OBX_query_p])

# OBX_C_API OBX_query* obx_query_clone(OBX_query* query);
obx_query_clone = c_fn("obx_query_clone", OBX_query_p, [OBX_query_p])

# OBX_C_API obx_err obx_query_offset(OBX_query* query, size_t offset);
obx_query_offset = c_fn_rc("obx_query_offset", [OBX_query_p, ctypes.c_size_t])

# OBX_C_API obx_err obx_query_offset_limit(OBX_query* query, size_t offset, size_t limit);
obx_query_offset_limit = c_fn_rc(
    "obx_query_offset_limit", [OBX_query_p, ctypes.c_size_t, ctypes.c_size_t]
)

# OBX_C_API obx_err obx_query_limit(OBX_query* query, size_t limit);
obx_query_limit = c_fn_rc("obx_query_limit", [OBX_query_p, ctypes.c_size_t])

# OBX_C_API OBX_bytes_array* obx_query_find(OBX_query* query);
obx_query_find = c_fn("obx_query_find", OBX_bytes_array_p, [OBX_query_p])

# OBX_C_API obx_err obx_query_find_first(OBX_query* query, const void** data, size_t* size);
obx_query_find_first = c_fn_rc(
    "obx_query_find_first",
    [OBX_query_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)],
)

# OBX_C_API obx_err obx_query_find_unique(OBX_query* query, const void** data, size_t* size);
obx_query_find_unique = c_fn_rc(
    "obx_query_find_unique",
    [OBX_query_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)],
)

# typedef bool obx_data_visitor(void* user_data, const void* data, size_t size);

# OBX_C_API obx_err obx_query_visit(OBX_query* query, obx_data_visitor* visitor, void* user_data);
# obx_query_visit = fn('obx_query_visit', obx_err, [OBX_query_p, obx_data_visitor_p, ctypes.c_void_p])

# OBX_C_API OBX_id_array* obx_query_find_ids(OBX_query* query);
obx_query_find_ids = c_fn("obx_query_find_ids", OBX_id_array_p, [OBX_query_p])

# OBX_C_API obx_err obx_query_count(OBX_query* query, uint64_t* out_count);
obx_query_count = c_fn_rc(
    "obx_query_count", [OBX_query_p, ctypes.POINTER(ctypes.c_uint64)]
)

# OBX_C_API obx_err obx_query_remove(OBX_query* query, uint64_t* out_count);
obx_query_remove = c_fn_rc(
    "obx_query_remove", [OBX_query_p, ctypes.POINTER(ctypes.c_uint64)]
)

# OBX_C_API const char* obx_query_describe(OBX_query* query);
obx_query_describe = c_fn("obx_query_describe", ctypes.c_char_p, [OBX_query_p])

# OBX_C_API const char* obx_query_describe_params(OBX_query* query);
obx_query_describe_params = c_fn(
    "obx_query_describe_params", ctypes.c_char_p, [OBX_query_p]
)

# OBX_bytes_array* (size_t count);
obx_bytes_array = c_fn("obx_bytes_array", OBX_bytes_array_p, [ctypes.c_size_t])

# obx_err (OBX_bytes_array* array, size_t index, const void* data, size_t size);
obx_bytes_array_set = c_fn_rc(
    "obx_bytes_array_set",
    [OBX_bytes_array_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t],
)

# void (OBX_bytes_array * array);
obx_bytes_array_free = c_fn("obx_bytes_array_free", None, [OBX_bytes_array_p])

OBXPropertyType_Bool = 1
OBXPropertyType_Byte = 2
OBXPropertyType_Short = 3
OBXPropertyType_Char = 4
OBXPropertyType_Int = 5
OBXPropertyType_Long = 6
OBXPropertyType_Float = 7
OBXPropertyType_Double = 8
OBXPropertyType_String = 9
OBXPropertyType_Date = 10
OBXPropertyType_Relation = 11
OBXPropertyType_DateNano = 12
OBXPropertyType_Flex = 13
OBXPropertyType_BoolVector = 22
OBXPropertyType_ByteVector = 23
OBXPropertyType_ShortVector = 24
OBXPropertyType_CharVector = 25
OBXPropertyType_IntVector = 26
OBXPropertyType_LongVector = 27
OBXPropertyType_FloatVector = 28
OBXPropertyType_DoubleVector = 29
OBXPropertyType_StringVector = 30

py_types_lookup = {
    1: bool,  # OBXPropertyType_Bool
    2: int,  # OBXPropertyType_Byte
    3: int,  # OBXPropertyType_Short
    4: str,  # OBXPropertyType_Char
    5: int,  # OBXPropertyType_Int
    6: int,  # OBXPropertyType_Long
    7: float,  # OBXPropertyType_Float
    8: float,  # OBXPropertyType_Double
    9: str,  # OBXPropertyType_String
    10: int,  # OBXPropertyType_Date
    # 11: str, # OBXPropertyType_Relation
    12: int,  # OBXPropertyType_DateNano
    13: str,  # OBXPropertyType_Flex
    22: bool,  # OBXPropertyType_BoolVector
    23: int,  # OBXPropertyType_ByteVector
    24: int,  # OBXPropertyType_ShortVector
    25: int,  # OBXPropertyType_CharVector
    26: int,  # OBXPropertyType_IntVector
    27: str,  # OBXPropertyType_LongVector
    28: float,  # OBXPropertyType_FloatVector
    29: float,  # OBXPropertyType_DoubleVector
    # 30: str # OBXPropertyType_StringVector
}

OBXPropertyFlags_ID = 1
OBXPropertyFlags_NON_PRIMITIVE_TYPE = 2
OBXPropertyFlags_NOT_NULL = 4
OBXPropertyFlags_INDEXED = 8
OBXPropertyFlags_RESERVED = 16
OBXPropertyFlags_UNIQUE = 32
OBXPropertyFlags_ID_MONOTONIC_SEQUENCE = 64
OBXPropertyFlags_ID_SELF_ASSIGNABLE = 128
OBXPropertyFlags_INDEX_PARTIAL_SKIP_NULL = 256
OBXPropertyFlags_INDEX_PARTIAL_SKIP_ZERO = 512
OBXPropertyFlags_VIRTUAL = 1024
OBXPropertyFlags_INDEX_HASH = 2048
OBXPropertyFlags_INDEX_HASH64 = 4096
OBXPropertyFlags_UNSIGNED = 8192

OBXDebugFlags_LOG_TRANSACTIONS_READ = 1
OBXDebugFlags_LOG_TRANSACTIONS_WRITE = 2
OBXDebugFlags_LOG_QUERIES = 4
OBXDebugFlags_LOG_QUERY_PARAMETERS = 8
OBXDebugFlags_LOG_ASYNC_QUEUE = 16

# Standard put ("insert or update")
OBXPutMode_PUT = 1

# Put succeeds only if the entity does not exist yet.
OBXPutMode_INSERT = 2

# Put succeeds only if the entity already exist.
OBXPutMode_UPDATE = 3

# The given ID (non-zero) is guaranteed to be new; don't use unless you know exactly what you are doing!
# This is primarily used internally. Wrong usage leads to inconsistent data (e.g. index data not updated)!
OBXPutMode_PUT_ID_GUARANTEED_TO_BE_NEW = 4

# Reverts the order from ascending (default) to descending.
OBXOrderFlags_DESCENDING = 1

# Makes upper case letters (e.g. "Z") be sorted before lower case letters (e.g. "a").
# If not specified, the default is case insensitive for ASCII characters.
OBXOrderFlags_CASE_SENSITIVE = 2

# For scalars only: changes the comparison to unsigned (default is signed).
OBXOrderFlags_UNSIGNED = 4

# null values will be put last.
# If not specified, by default null values will be put first.
OBXOrderFlags_NULLS_LAST = 8

# null values should be treated equal to zero (scalars only).
OBXOrderFlags_NULLS_ZERO = 16
