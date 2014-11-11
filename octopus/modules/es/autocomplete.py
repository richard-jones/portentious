from octopus.core import app

import esprit
import json

from flask import Blueprint, request, abort, make_response

from octopus.lib import webapp, plugin

blueprint = Blueprint('autocomplete', __name__)

@blueprint.route('/compound/<config_name>')
@webapp.jsonp
def compound(config_name):
    # get the configuration
    acc = app.config.get("AUTOCOMPLETE_COMPOUND")
    cfg = acc.get(config_name)
    if cfg is None:
        abort(404)

    # get the query value
    q = request.values.get("q")
    if q is None or q == "":
        abort(400)
    q = q.strip()

    # apply any input filters to the query value
    ifs = cfg.get("input_filter")
    if ifs is not None:
        q = ifs(q)

    # get the filters that will be used to match documents
    filters = cfg.get("filters")
    if filters is None or len(filters.keys()) == 0:
        abort(500)

    # now build the query object
    query = {"query" : {"bool" : {"should" : []}}}
    for field, params in filters.iteritems():
        wq = _do_wildcard(q, params.get("start_wildcard", True), params.get("end_wildcard", True))
        boost = params.get("boost", 1.0)
        wcq = {"wildcard" : {field : {"value" : wq, "boost" : boost}}}
        query["query"]["bool"]["should"].append(wcq)

    # set the size of the result set
    size = request.values.get("size")
    if size is None or size == "":
        size = cfg.get("default_size")
    else:
        try:
            size = int(size)
        except:
            abort(400)
    if size > cfg.get("max_size", 25):
        size = cfg.get("max_size", 25)
    query["size"] = size

    # add the fields constraint
    fields = cfg.get("fields")
    if fields is None or len(fields) == 0:
        abort(500)
    query["fields"] = fields

    # get the name of the model that will handle this query, and then look up
    # the class that will handle it
    dao_name = cfg.get("dao")
    dao_klass = plugin.load_class(dao_name)
    if dao_klass is None:
        abort(500)

    # issue the query
    res = dao_klass.query(q=query)
    records = esprit.raw.unpack_json_result(res)

    # rewrite the field names if necessary
    field_name_map = cfg.get("field_name_map")
    mapped_records = []
    if field_name_map is not None and len(field_name_map.keys()) > 0:
        for r in records:
            newobj = {}
            for k, v in r.iteritems():
                newk = field_name_map.get(k)
                if newk is None:
                    newobj[k] = v
                else:
                    newobj[newk] = v
            mapped_records.append(newobj)
        records = mapped_records

    # make the response
    resp = make_response(json.dumps(records))
    resp.mimetype = "application/json"
    return resp

def _do_wildcard(q, start, end):
    # add/remove wildcard characters from the string
    if end:
        if not q.endswith("*"):
            q += "*"
    else:
        q = q.rstrip("*")

    if start:
        if not q.startswith("*"):
            q = "*" + q
    else:
        q = q.lstrip("*")

    return q
