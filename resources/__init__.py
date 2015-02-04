from datetime import datetime
import httplib
import json
from time import mktime

from django.http import HttpResponse
from django.template import Context

try:
    from django.views.decorators.vary import vary_on_headers
except ImportError:
    def vary_on_headers(*args):
        """A no-op vary_on_headers decorator for running outside of Django"""
        def inner(func):
            return func
        return inner

from representations import MediaTypeAcceptor, get_acceptable_types, \
                            LanguageAcceptor, get_acceptable_languages

class HttpException(Exception):
    def __init__(self, status_code, response, headers=None):
        self.status_code = status_code
        self.response = response
        self.headers = headers or {}

    def __unicode__(self):
        return "%s %s" % (self.status_code, self.response)
    __str__ = __unicode__

    def as_http_response(self):
        response = HttpResponse(status=self.status_code,
                                content_type="text/plain",
                                content=self.response)

        for header, value in self.headers.items():
            response[header] = value

        return response

class Resource(object):
    """Resource is the base class for any REST resource."""

    ALL_METHODS = set(("OPTIONS", "HEAD", "GET", "PATCH", "PUT", "POST", "DELETE"))
    SAFE_METHODS = set(("OPTIONS", "HEAD", "GET"))
    UNSAFE_METHODS = ALL_METHODS - SAFE_METHODS

    RENDERERS = {
        "application/json": "render_json",
        "application/rss+xml": "render_rss",
        "text/html": "render_html",
        "text/plain": "render_plaintext",
        "text/csv": "render_csv"
    }

    @classmethod
    @vary_on_headers('Accept', 'Accept-Language', 'ETag')
    def dispatch(cls, request, *args, **kwargs):
        resource = cls()

        try:
            method = getattr(resource, request.method)
        except AttributeError as e:
            return HttpException(405, "%s is not supported on %s." % (request.method, request.path),
                                 headers = {"Allow": ", ".join(cls.allowed_methods()) }).as_http_response()

        try:
            return method(request, *args, **kwargs)
        except HttpException as e:
            if "application/json+html" in get_acceptable_types(request):
                return HttpResponse(status=httplib.OK, content_type="text/html",
                                    content=json.dumps({ "success": False, "message": e.response }))
            return e.as_http_response()

    @classmethod
    def allowed_methods(cls):
        return set((attr for attr in dir(cls) if attr in Resource.ALL_METHODS and callable(getattr(cls, attr))))

    def get_client_address(self, request):
        address = request.META.get("HTTP_X_FORWARDED_FOR", None)
        if not address:
            address = request.META.get("HTTP_X_REAL_IP", None)
        if not address:
            address = request.META.get("REMOTE_ADDR", None)
        return address

    def interpret_range_parameters(self, request, default_start, default_limit):
        # count  number  The number of items to return
        # start  number  The number of the first item to return (zero-based)
        # end    number  The number of the lst item to return (zero-based). If both count and end
        #                are specified, count will override end.
        count = self.interpret_integer(request.GET, "count", default=None)
        start = self.interpret_integer(request.GET, "start", default=default_start)
        limit = self.interpret_integer(request.GET, "limit", default=default_limit)
        if isinstance(count, int):
            stop = count
        elif isinstance(limit, int):
            stop = start + limit
        else:
            stop = None
        return slice(start, stop, 1)

    def interpret_sort_parameters(self, request, default_sort_field, default_direction):
        '''Sort and direction parameters'''
        # sort       string  Field on which to order results
        # direction  string  Either DESC or ASC
        sort_field = request.GET.get("sort", default_sort_field)
        direction = self.interpret_options(request.GET, "direction", options=["asc", "desc"], default=default_direction)
        return sort_field, direction

    @staticmethod
    def django_sort(sort_field, direction):
        '''Takes a sort field and a direction "ASC" or "DESC" and returns Django model order_by-friendly string'''
        return ("-" if direction.lower() == "desc" else "")+sort_field

    def interpret(self, request):
        content_type = request.META["CONTENT_TYPE"]
        if content_type.startswith("application/json"):
            try:
                return json.loads(request.body)
            except:
                raise HttpException(422, "The provided JSON body could not be parsed.")
        elif content_type.startswith("multipart/form-data"):
            return dict(request.POST.items())
        elif content_type.startswith("text/plain"):
            return { "value": request.body }
        elif content_type.startswith('application/x-www-form-urlencoded'):
            return dict(request.POST)
        else:
            raise HttpException(415, "%s %s does not support bodies in '%s'" % (request.method, request.path, request.META["CONTENT_TYPE"]))

    def interpret_date(self, date_string):
        raise NotImplementedError()

    @classmethod
    def interpret_boolean(cls, querydict, key, default=None, also_valid=[]):
        '''Check for boolean-ish parameter in querydict and return either True, False, None,
        or be argument if it's in the also_valid option, otherwise raise raise a 400 error'''
        value = querydict.get(key, default)
        if value in ([True, False, None] + also_valid):
            return value
        booleans = dict.fromkeys(['true', 't', 'yes', 'y'], True)
        booleans.update(dict.fromkeys(['false', 'f', 'no', 'n'], False))
        if value.lower() in booleans:
            return booleans[value.lower()]
        raise HttpException(400, "'%s' is not a valid choice for %s. Choose from '%s'." % \
                                 (value, key, "', '".join(['true', 'false']+also_valid)))

    @classmethod
    def interpret_options(cls, querydict, key, options, default=None):
        '''Check for a parameter in a querydict that is one of several options'''
        value = querydict.get(key, default)
        if value.lower() in map(str.lower, options):
            return value
        raise HttpException(400, "'%s' is not a valid choice for %s. Choose from '%s'." % (value, key, "', ".join(options)))

    @classmethod
    def interpret_integer(cls, querydict, key, default=None, also_valid=[], case_sensitive=False):
        '''Check for a parameter in a query dict that is an integer or one of
        any other also_valid values.'''
        value = querydict.get(key, default)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            if not case_sensitive:
                value = value.lower()
                also_valid = map(str.lower, also_valid)
            if value in also_valid:
                return value
            raise HttpException(400, ("%s is invalid. %s must be an interger" % (value, key))+\
                                     (" or %s." % ", ".join(also_valid) if also_valid else "."))

    def empty(self, request, status):
        return HttpResponse("", status=status, content_type="text/plain")

    def render(self, request, context, status):
        acceptable_types = get_acceptable_types(request)

        native_type = None
        if "native_mediatype" in context:
            native_type = context["native_mediatype"]

        acceptable_languages = get_acceptable_languages(request)

        output_type = None
        if acceptable_types == "application/json+html":
            acceptable_types = "application/json"
            output_type = "text/html"

        language, mediatype, renderer = self.select_renderer(acceptable_languages,
                                                             native_type,
                                                             acceptable_types)

        if not output_type:
            output_type = mediatype

        if not renderer:
            raise HttpException(406,
                                "There were no representations deemed acceptable given '%s' in '%s'." %
                                (acceptable_types, acceptable_languages))
        else:
            if "-" in language:
                context["language"], context["dialect"] = language.split("-")
            else:
                context["language"] = language
                favorite_language = LanguageAcceptor(acceptable_languages).ranges[0]
                if favorite_language.type == language and favorite_language.subtype:
                    context["dialect"] = favorite_language.subtype

            content = renderer(request, context)

            if "__charset__" in context and context["__charset__"]:
                mediatype += "; charset=" + context["__charset__"]

            response = HttpResponse(content, status=status, content_type=output_type)

            response["Content-Language"] = (context["language"] +
                                            ("-" + context["dialect"] if "dialect" in context else ""))

            if "__content_disposition__" in context and context["__content_disposition__"]:
                response["Content-Disposition"] = context["__content_disposition__"]

            return response

    def select_renderer(self, acceptable_languages, native_type, acceptable_types):
        """Selects the best media type class based on an RFC 2616 Accept field"""
        languages = self.get_representations()

        preferred_languages = LanguageAcceptor(acceptable_languages).all_preferred(languages.keys()) or []
        for preferred_language in preferred_languages + ["any"]:
            if preferred_language in languages:
                mediatypes = languages[preferred_language]

                preferred_type = None
                type_acceptor = MediaTypeAcceptor(acceptable_types)

                if (native_type and
                    type_acceptor.accepts(native_type) and
                    native_type in mediatypes):
                    preferred_type = native_type

                if not preferred_type:
                    preferred_type = type_acceptor.preferred(mediatypes.keys())

                if preferred_type:
                    renderer = mediatypes[preferred_type]
                    return preferred_language, preferred_type, renderer

        return None, None, None

    def get_representations(self):
        representations = {}
        for mimetype, renderer in self.RENDERERS.items():
            try:
                representations[mimetype] = getattr(self, renderer)
                if mimetype == "application/json":
                    representations["application/x-javascript"] = self.render_jsonp
                    representations["application/javascript"] = self.render_jsonp
            except AttributeError:
                pass
        return { "en": representations }

    def render_jsonp(self, request, context):
        padding = request.GET.get("callback", "var result = ")
        return padding + "(" + self.render_json(request, context) + ");"
