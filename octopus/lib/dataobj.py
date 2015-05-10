from octopus.lib import dates
from copy import deepcopy
import locale, json

#########################################################
## Data coerce functions

def to_unicode():
    def to_utf8_unicode(val):
        if isinstance(val, unicode):
            return val
        elif isinstance(val, basestring):
            try:
                return val.decode("utf8", "strict")
            except UnicodeDecodeError:
                raise ValueError(u"Could not decode string")
        else:
            return unicode(val)

    return to_utf8_unicode

def to_int():
    def intify(val):
        # strip any characters that are outside the ascii range - they won't make up the int anyway
        # and this will get rid of things like strange currency marks
        if isinstance(val, unicode):
            val = val.encode("ascii", errors="ignore")

        # try the straight cast
        try:
            return int(val)
        except ValueError:
            pass

        # could have commas in it, so try stripping them
        try:
            return int(val.replace(",", ""))
        except ValueError:
            pass

        # try the locale-specific approach
        try:
            return locale.atoi(val)
        except ValueError:
            pass

        raise ValueError(u"Could not convert string to int: {x}".format(x=val))

    return intify

def to_float():
    def floatify(val):
        # strip any characters that are outside the ascii range - they won't make up the float anyway
        # and this will get rid of things like strange currency marks
        if isinstance(val, unicode):
            val = val.encode("ascii", errors="ignore")

        # try the straight cast
        try:
            return float(val)
        except ValueError:
            pass

        # could have commas in it, so try stripping them
        try:
            return float(val.replace(",", ""))
        except ValueError:
            pass

        # try the locale-specific approach
        try:
            return locale.atof(val)
        except ValueError:
            pass

        raise ValueError(u"Could not convert string to float: {x}".format(x=val))

    return floatify

def date_str(in_format=None, out_format=None):
    def datify(val):
        return dates.reformat(val, in_format=in_format, out_format=out_format)

    return datify

############################################################

############################################################
## The core data object which manages all the interactions
## with the underlying data member variable

class DataSchemaException(Exception):
    pass

class DataObj(object):
    """
    Class which provides services to other classes which store their internal data
    as a python data structure in the self.data field.
    """

    SCHEMA = None

    STRUCT = None

    DEFAULT_COERCE = {
        "unicode" : to_unicode(),
        "utcdatetime" : date_str(),
        "integer" : to_int(),
        "float" : to_float()
    }

    def __init__(self, raw=None, coerce=None):
        # prep the coersion routine
        self.coerce = deepcopy(self.DEFAULT_COERCE)
        if coerce is not None:
            self.coerce.update(coerce)

        # restructure the object based on the struct
        if self.STRUCT is not None:
            raw = construct(raw, self.STRUCT, self.coerce)

        # assign the data
        self.data = {} if raw is None else raw

        # run against the old validation routine
        # (now deprecated)
        self.validate()

    def validate(self):
        if self.SCHEMA is not None:
            validate(self.data, self.SCHEMA)
        return True

    def populate(self, fields_and_values):
        for k, v in fields_and_values.iteritems():
            setattr(self, k, v)

    def clone(self):
        return self.__class__(deepcopy(self.data))

    def json(self):
        return json.dumps(self.data)

    def _get_path(self, path, default):
        parts = path.split(".")
        context = self.data

        for i in range(len(parts)):
            p = parts[i]
            d = {} if i < len(parts) - 1 else default
            context = context.get(p, d)
        return context

    def _set_path(self, path, val):
        parts = path.split(".")
        context = self.data

        for i in range(len(parts)):
            p = parts[i]

            if p not in context and i < len(parts) - 1:
                context[p] = {}
                context = context[p]
            elif p in context and i < len(parts) - 1:
                context = context[p]
            else:
                context[p] = val

    def _delete_from_list(self, path, val=None, matchsub=None, prune=True):
        l = self._get_list(path)

        removes = []
        i = 0
        for entry in l:
            if val is not None:
                if entry == val:
                    removes.append(i)
            elif matchsub is not None:
                matches = 0
                for k, v in matchsub.iteritems():
                    if entry.get(k) == v:
                        matches += 1
                if matches == len(matchsub.keys()):
                    removes.append(i)
            i += 1

        removes.sort(reverse=True)
        for r in removes:
            del l[r]

        if len(l) == 0 and prune:
            self._delete(path, prune)

    def _delete(self, path, prune=True):
        parts = path.split(".")
        context = self.data

        stack = []
        for i in range(len(parts)):
            p = parts[i]
            if p in context:
                if i < len(parts) - 1:
                    stack.append(context[p])
                    context = context[p]
                else:
                    del context[p]
                    if prune and len(stack) > 0:
                        stack.pop() # the last element was just deleted
                        self._prune_stack(stack)

    def _prune_stack(self, stack):
        while len(stack) > 0:
            context = stack.pop()
            todelete = []
            for k, v in context.iteritems():
                if isinstance(v, dict) and len(v.keys()) == 0:
                    todelete.append(k)
            for d in todelete:
                del context[d]

    def _coerce(self, val, cast, accept_failure=False):
        if cast is None:
            return val
        try:
            return cast(val)
        except (ValueError, TypeError):
            if accept_failure:
                return val
            raise DataSchemaException(u"Cast with {x} failed on {y}".format(x=cast, y=val))

    def _get_single(self, path, coerce=None, default=None, allow_coerce_failure=True):
        # get the value at the point in the object
        val = self._get_path(path, default)

        if coerce is not None and val is not None:
            # if you want to coerce and there is something to coerce do it
            return self._coerce(val, coerce, accept_failure=allow_coerce_failure)
        else:
            # otherwise return the value
            return val

    def _get_list(self, path, coerce=None, by_reference=True, allow_coerce_failure=True):
        # get the value at the point in the object
        val = self._get_path(path, None)

        # if there is no value and we want to do by reference, then create it, bind it and return it
        if val is None and by_reference:
            mylist = []
            self._set_single(path, mylist)
            return mylist

        # otherwise, default is an empty list
        elif val is None and not by_reference:
            return []

        # check that the val is actually a list
        if not isinstance(val, list):
            raise DataSchemaException(u"Expecting a list at {x} but found {y}".format(x=path, y=val))

        # if there is a value, do we want to coerce each of them
        if coerce is not None:
            coerced = [self._coerce(v, coerce, accept_failure=allow_coerce_failure) for v in val]
            if by_reference:
                self._set_single(path, coerced)
            return coerced
        else:
            if by_reference:
                return val
            else:
                return deepcopy(val)

    def _set_single(self, path, val, coerce=None, allow_coerce_failure=False, allowed_values=None, allowed_range=None,
                    allow_none=True, ignore_none=False):

        if val is None and ignore_none:
            return

        if val is None and not allow_none:
            raise DataSchemaException(u"NoneType is not allowed at {x}".format(x=path))

        # first see if we need to coerce the value (and don't coerce None)
        if coerce is not None and val is not None:
            val = self._coerce(val, coerce, accept_failure=allow_coerce_failure)

        if allowed_values is not None and val not in allowed_values:
            raise DataSchemaException(u"Value {x} is not permitted at {y}".format(x=val, y=path))

        if allowed_range is not None:
            lower, upper = allowed_range
            if (lower is not None and val < lower) or (upper is not None and val > upper):
                raise DataSchemaException("Value {x} is outside the allowed range: {l} - {u}".format(x=val, l=lower, u=upper))

        # now set it at the path point in the object
        self._set_path(path, val)

    def _set_list(self, path, val, coerce=None, allow_coerce_failure=False, allow_none=True, ignore_none=False):
        # first ensure that the value is a list
        if not isinstance(val, list):
            val = [val]

        # now carry out the None check
        # for each supplied value, if it is none, and none is not allowed, raise an error if we do not
        # plan to ignore the nones.
        for v in val:
            if v is None and not allow_none:
                if not ignore_none:
                    raise DataSchemaException(u"NoneType is not allowed at {x}".format(x=path))

        # now coerce each of the values, stripping out Nones if necessary
        val = [self._coerce(v, coerce, accept_failure=allow_coerce_failure) for v in val if v is not None or not ignore_none]

        # check that the cleaned array isn't empty, and if it is behave appropriately
        if len(val) == 0:
            # this is equivalent to a None, so we need to decide what to do
            if ignore_none:
                # if we are ignoring nones, just do nothing
                return
            elif not allow_none:
                # if we are not ignoring nones, and not allowing them, raise an error
                raise DataSchemaException(u"Empty array not permitted at {x}".format(x=path))

        # now set it on the path
        self._set_path(path, val)

    def _add_to_list(self, path, val, coerce=None, allow_coerce_failure=False, allow_none=False, ignore_none=True):
        if val is None and ignore_none:
            return

        if val is None and not allow_none:
            raise DataSchemaException(u"NoneType is not allowed in list at {x}".format(x=path))

        # first coerce the value
        if coerce is not None:
            val = self._coerce(val, coerce, accept_failure=allow_coerce_failure)
        current = self._get_list(path, by_reference=True)
        current.append(val)

    def _utf8_unicode(self):
        """
        DEPRECATED - use dataobj.to_unicode() instead
        """
        return to_unicode()

    def _int(self):
        """
        DEPRECATED - use dataobj.to_int() instead
        """
        return to_int()

    def _float(self):
        """
        DEPRECATED - use dataobj.to_float() instead
        """
        return to_float()

    def _date_str(self, in_format=None, out_format=None):
        """
        DEPRECATED - use dataobj.date_str instead
        """
        return date_str(in_format=in_format, out_format=out_format)



############################################################
## Primitive object schema validation

class ObjectSchemaValidationError(Exception):
    pass


def validate(obj, schema):
    """
    DEPRECATED - use "construct" instead

    :param obj:
    :param schema:
    :return:
    """
    # all fields
    allowed = schema.get("bools", []) + schema.get("fields", []) + schema.get("lists", []) + schema.get("objects", [])

    for k, v in obj.iteritems():
        # is k allowed at all
        if k not in allowed:
            raise ObjectSchemaValidationError("object contains key " + k + " which is not permitted by schema")

        # check the bools are bools
        if k in schema.get("bools", []):
            if type(v) != bool:
                raise ObjectSchemaValidationError("object contains " + k + " = " + str(v) + " but expected boolean")

        # check that the fields are plain old strings
        if k in schema.get("fields", []):
            if type(v) != str and type(v) != unicode and type(v) != int and type(v) != float:
                raise ObjectSchemaValidationError("object contains " + k + " = " + str(v) + " but expected string, unicode or a number")

        # check that the lists are really lists
        if k in schema.get("lists", []):
            if type(v) != list:
                raise ObjectSchemaValidationError("object contains " + k + " = " + str(v) + " but expected list")
            # if it is a list, then for each member validate
            entry_schema = schema.get("list_entries", {}).get(k)
            if entry_schema is None:
                # validate the entries as fields
                for e in v:
                    if type(e) != str and type(e) != unicode and type(e) != int and type(e) != float:
                        raise ObjectSchemaValidationError("list in object contains " + str(type(e)) + " but expected string, unicode or a number in " + k)
            else:
                # validate each entry against the schema
                for e in v:
                    validate(e, entry_schema)

        # check that the objects are objects
        if k in schema.get("objects", []):
            if type(v) != dict:
                raise ObjectSchemaValidationError("object contains " + k + " = " + str(v) + " but expected object/dict")
            # if it is an object, then validate
            object_schema = schema.get("object_entries", {}).get(k)
            if object_schema is None:
                #raise ObjectSchemaValidationError("no object entry for object " + k)
                pass # we are not imposing a schema on this object
            else:
                validate(v, object_schema)

############################################################
## Data structure coercion

class DataStructureException(Exception):
    pass

def construct(obj, struct, coerce, context=""):
    """
    {
        "fields" : {
            "field_name" : {"coerce" :"coerce_function"}

        },
        "objects" : [
            "field_name"
        ],
        "lists" : {
            "field_name" : {"contains" : "object|list|field", "coerce" : "field_coerce_function}
        },
        "reqired" : ["field_name"],
        "structs" : {
            "field_name" : {
                <construct>
            }
        }
    }

    :param obj:
    :param struct:
    :param coerce:
    :return:
    """
    if obj is None:
        return None

    # check that all the required fields are there
    keys = obj.keys()
    for r in struct.get("required", []):
        if r not in keys:
            c = context if context != "" else "root"
            raise DataStructureException("Field '{r}' is required but not present at '{c}'".format(r=r, c=c))

    # check that there are no fields that are not allowed
    allowed = struct.get("fields", {}).keys() + struct.get("objects", []) + struct.get("lists", {}).keys()
    for k in keys:
        if k not in allowed:
            c = context if context != "" else "root"
            raise DataStructureException("Field '{k}' is not permitted at '{c}'".format(k=k, c=c))

    # this is the new object we'll be creating from the old
    constructed = {}

    # now check all the fields
    for field_name, instructions in struct.get("fields", {}).iteritems():
        val = obj.get(field_name)
        if val is None:
            continue
        coerce_fn = coerce.get(instructions.get("coerce", "unicode"))
        if coerce_fn is None:
            raise DataStructureException("No coersion function defined for type '{x}' at '{c}'".format(x=instructions.get("coerce", "unicode"), c=context + field_name))

        try:
            constructed[field_name] = coerce_fn(val)
        except ValueError as e:
            raise DataStructureException("Unable to coerce '{v}' to '{fn}' at '{c}'".format(v=val, fn=instructions.get("coerce", "unicode"), c=context + field_name))

    # next check all the objetcs (which will involve a recursive call to this function
    for field_name in struct.get("objects", []):
        val = obj.get(field_name)
        if val is None:
            continue
        if type(val) != dict:
            raise DataStructureException("Found '{x}' = '{y}' but expected object/dict".format(x=context + field_name, y=val))

        instructions = struct.get("struct", {}).get(field_name)
        if instructions is None:
            constructed[field_name] = deepcopy(val)
        else:
            constructed[field_name] = construct(val, instructions, coerce=coerce, context=context + field_name + ".")

    # now check all the lists
    for field_name, instructions in struct.get("lists", {}).iteritems():
        vals = obj.get(field_name)
        if vals is None:
            continue

        nvals = []
        contains = instructions.get("contains")
        if contains == "field":
            # coerce all the values in the list
            coerce_fn = coerce.get(instructions.get("coerce", "unicode"))
            if coerce_fn is None:
                raise DataStructureException("No coersion function defined for type '{x}' at '{c}'".format(x=instructions.get("coerce", "unicode"), c=context + field_name))

            for i in xrange(len(vals)):
                val = vals[i]
                try:
                    nvals.append(coerce_fn(val))
                except ValueError as e:
                    raise DataStructureException("Unable to coerce '{v}' to '{fn}' at '{c}' position '{p}'".format(v=val, fn=instructions.get("coerce", "unicode"), c=context + field_name, p=i))

        elif contains == "object":
            # for each object in the list, send it for construction
            for i in range(len(vals)):
                val = vals[i]

                if type(val) != dict:
                    raise DataStructureException("Found '{x}[{p}]' = '{y}' but expected object/dict".format(x=context + field_name, y=val, p=i))

                subinst = struct.get("struct", {}).get(field_name)
                if subinst is None:
                    nvals.append(deepcopy(val))
                else:
                    nvals.append(construct(val, subinst, coerce=coerce, context=context + field_name + "[" + str(i) + "]."))

        else:
            raise DataStructureException("Cannot understand structure where list '{x}' elements contain '{y}'".format(x=context + field_name, y=contains))

        constructed[field_name] = nvals

    return constructed




############################################################
## Unit test support

def test_dataobj(obj, fields_and_values):
    """
    Test a dataobj to make sure that the getters and setters you have specified
    are working correctly.

    Provide it a data object and a list of fields with the values to set and the expeceted return values (if required):

    {
        "key" : ("set value", "get value")
    }

    If you provide only the set value, then the get value will be required to be the same as the set value in the test

    {
        "key" : "set value"
    }

    :param obj:
    :param fields_and_values:
    :return:
    """
    for k, valtup in fields_and_values.iteritems():
        if not isinstance(valtup, tuple):
            valtup = (valtup,)
        set_val = valtup[0]
        try:
            setattr(obj, k, set_val)
        except AttributeError:
            assert False, u"Unable to set attribute {x} with value {y}".format(x=k, y=set_val)

    for k, valtup in fields_and_values.iteritems():
        if not isinstance(valtup, tuple):
            valtup = (valtup,)
        get_val = valtup[0]
        if len(valtup) > 1:
            get_val = valtup[1]
        val = getattr(obj, k)
        assert val == get_val, (k, val, get_val)