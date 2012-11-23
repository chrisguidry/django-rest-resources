import mimetypes
import operator
import re

mimetypes.add_type("application/json", ".json")
mimetypes.add_type("application/rss+xml", ".rss")
mimetypes.add_type("application/json+html", ".jsonh") # a made-up mimetype to represent a JSON response returned as HTML, for ExtJS fileupload support
mimetypes.add_type("text/csv", ".csv")

mimetypes.add_type("application/x-font-ttf", ".ttf")
mimetypes.add_type("font/opentype", ".otf")
mimetypes.add_type("application/vnc.ms-fontobject", ".eot")
mimetypes.add_type("application/x-font-woff", ".woff")

def get_acceptable_types(request):
    acceptable_types = None

    path = request.path
    path = path[:-1] if path.endswith("/") else path

    demanded_types = mimetypes.guess_type(path)[0]
    if demanded_types:
        acceptable_types = demanded_types
    elif "HTTP_ACCEPT" in request.META:
        acceptable_types = request.META["HTTP_ACCEPT"]

    return acceptable_types or ""

def get_acceptable_languages(request):
    acceptable_languages = ""

    if "HTTP_ACCEPT_LANGUAGE" in request.META:
        acceptable_languages = request.META["HTTP_ACCEPT_LANGUAGE"]

    if not acceptable_languages:
        acceptable_languages = "en;q=0.1"

    # always inject a low-quality English accept for a fallback
    found_english = False
    for language in acceptable_languages.split(","):
        if language.startswith("en"):
            found_english = True
            break

    if not found_english:
        # Injecting a low-quality English accept as a fallback
        acceptable_languages += ",en;q=0.1";

    return acceptable_languages or ""

class Acceptor(object):
    """Interprets RFC 2616 section 14.1-14.4 Accept headers"""

    def __init__(self, ranges):
        self.ranges = ranges
        for position, range in enumerate(self.ranges):
            range.position = position
        self.ranges.sort()

    def accepts(self, media_type):
        return any(map(lambda range: media_type in range, self.ranges))

    def preferred(self, offerings):
        return (self.all_preferred(offerings) or [None])[0]

    def all_preferred(self, offerings):
        def best_mediarange(offering):
            matching = filter(lambda mediarange: offering in mediarange,
                              self.ranges)
            if matching:
                return max(matching,
                           key = lambda mediarange: mediarange.quality)

        best = filter(operator.itemgetter(1),
                      zip(offerings,
                          map(best_mediarange,
                              offerings)))
        if best:
            best.sort(key=operator.itemgetter(1))
            return map(operator.itemgetter(0), best)


class MediaTypeAcceptor(Acceptor):
    ACCEPT_PATTERN = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')

    def __init__(self, rfc2616_accept_string):
        if not rfc2616_accept_string or not rfc2616_accept_string.strip():
            rfc2616_accept_string = "*/*"

        ranges = [MediaRange(mediatype, float(quality) if quality else 1.0)
                  for mediatype, quality in self.ACCEPT_PATTERN.findall(rfc2616_accept_string.strip())]

        super(MediaTypeAcceptor, self).__init__(ranges)

class MediaRange(object):
    """Represents one media range in an RFC 2616 Accept field"""

    def __init__(self, media_type, quality=1.0):
        if media_type == "*":
            media_type = "*/*"
        assert "/" in media_type, "Media Ranges should be of the form 'type/subtype'"

        self.type, self.subtype = media_type.split("/")
        self.quality = quality or 1.0

    def __contains__(self, media_type):
        if not "/" in media_type:
            return False

        type, subtype = media_type.split("/")
        if type == self.type or self.type == "*":
            if subtype == self.subtype or self.subtype == "*":
                return True
        return False

    def __cmp__(self, other):
        comparison = 0 - cmp(self.quality, other.quality)
        if not comparison:
            if hasattr(self, "position") and hasattr(other, "position"):
                comparison = cmp(self.position, other.position)
        return comparison

    def __str__(self):
        toreturn = self.type + "/" + self.subtype + ";q=" + str(self.quality)
        if hasattr(self, "position"):
            toreturn += ";position=" + str(self.position)
        return toreturn
    __repr__ = __str__



class LanguageAcceptor(Acceptor):
    ACCEPT_PATTERN = re.compile(r'([^\s;,]+)(?:[^,]*?;\s*q=(\d*(?:\.\d+)?))?')

    @classmethod
    def get_acceptor_for_all_acceptable_languages(cls, request):
        return cls(get_acceptable_languages(request))

    def __init__(self, rfc2616_accept_string):
        """Parses an RFC 2616 section 14.1 Accept field"""

        if not rfc2616_accept_string or not rfc2616_accept_string.strip():
            rfc2616_accept_string = "*-*"

        rfc2616_accept_string = rfc2616_accept_string.strip()

        # cleanup any bogus languages, like (ahem) IE's "en-us"
        rfc2616_accept_string = re.sub(r"([a-z]+)\-([a-z]+)",
                                       lambda m: m.groups()[0] + "-" + m.groups()[1].upper(),
                                       rfc2616_accept_string)

        ranges = [LanguageRange(language, float(quality) if quality else 1.0)
                  for language, quality in self.ACCEPT_PATTERN.findall(rfc2616_accept_string)]

        # finally, inject languages where only dialects are specified, like
        # if en-US is presented, then add en;q=0.9
        lowest_quality = min(map(lambda r: r.quality, ranges))
        new_ranges = []
        for range in ranges:
            if range.subtype:
                found_parent = False
                for other_range in ranges:
                    if other_range.type == range.type and not other_range.subtype:
                        found_parent = True
                        break
                if not found_parent:
                    new_ranges.append(LanguageRange(range.type, quality=lowest_quality - 0.1))
        ranges += new_ranges

        # de-dupe languages, taking the highest quality for each language
        languages = {}
        for range in ranges:
            if (range.type, range.subtype) in languages:
                if range.quality > languages[(range.type, range.subtype)].quality:
                    languages[(range.type, range.subtype)] = range
            else:
                languages[(range.type, range.subtype)] = range

        super(LanguageAcceptor, self).__init__(languages.values())

class LanguageRange(object):
    """Represents one language range in an RFC 2616 Accept field"""

    def __init__(self, language, quality=1.0):
        if language == "*":
            language = "*-*"

        if "-" in language:
            self.type, self.subtype = language.split("-")
        else:
            self.type, self.subtype = language, None
        self.quality = quality or 1.0

    def __contains__(self, language):
        if "-" in language:
            type, subtype = language.split("-")
        else:
            type, subtype = language, None
        if type == self.type or self.type == "*":
            if subtype == self.subtype or self.subtype == "*":
                return True
        return False

    def __cmp__(self, other):
        comparison = 0 - cmp(self.quality, other.quality)
        if not comparison:
            if hasattr(self, "position") and hasattr(other, "position"):
                comparison = cmp(self.position, other.position)
        return comparison

    def __str__(self):
        if self.subtype:
            toreturn = self.type + "-" + self.subtype + ";q=" + str(self.quality)
        else:
            toreturn = self.type + ";q=" + str(self.quality)
        if hasattr(self, "position"):
            toreturn += ";position=" + str(self.position)
        return toreturn
    __repr__ = __str__
