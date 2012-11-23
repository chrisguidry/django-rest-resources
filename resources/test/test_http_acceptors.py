import unittest
import os.path

from resources.representations import LanguageAcceptor, MediaTypeAcceptor
from resources.representations import get_acceptable_types, get_acceptable_languages

ChromiumAcceptString = "application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5"
FirefoxAcceptString = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
IE8AcceptString = "image/gif, image/jpeg, image/pjpeg, image/pjpeg, application/x-ms-application, application/x-ms-xbap, application/vnd.ms-xpsdocument, application/xaml+xml, */*"
IE7AcceptString = "image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/x-ms-application, application/x-ms-xbap, application/vnd.ms-xpsdocument, application/xaml+xml, */*"
BogusFeedReaderAcceptString = "application/atom+xml application/rdf+xml application/rss+xml application/xml text/html */*"

class LanguageAcceptabilityParsingTests(unittest.TestCase):

    def testParsingNothing(self):
        # RFC 2616, 14.1 - If no Accept header field is present,
        #                  then it is assumed that the client
        #                  accepts all media types.
        liberal = LanguageAcceptor(None)
        assert liberal.accepts("en-US")
        assert liberal.accepts("anything-anywhere")

        liberal = LanguageAcceptor("")
        assert liberal.accepts("en-US")
        assert liberal.accepts("anything-anywhere")

    def testParsingAll(self):
        liberal = LanguageAcceptor("*-*")
        assert liberal.accepts("en-US")
        assert liberal.accepts("anything-anywhere")

    def testParsingHorrorShowAll(self):
        liberal = LanguageAcceptor("*")
        assert liberal.accepts("en-US")
        assert liberal.accepts("anything-anywhere")

    def testParsingOneType(self):
        focused = LanguageAcceptor("en-US")
        assert focused.accepts("en-US")
        assert focused.accepts("en")
        assert not focused.accepts("en-GB")

    def testParsingTwoTypes(self):
        focused = LanguageAcceptor("en-US,en-GB")
        assert focused.accepts("en-US")
        assert focused.accepts("en-GB")
        assert not focused.accepts("es")
        assert not focused.accepts("es-SP")

    def testParsingOneTypeRange(self):
        english = LanguageAcceptor("en-US,en-GB,en")
        assert english.accepts("en-US")
        assert english.accepts("en-GB")
        assert not english.accepts("es")
        assert not english.accepts("es-SP")

    def testParsingOneTypeRangeAndOneType(self):
        bilingual = LanguageAcceptor("es,en-US")
        assert bilingual.accepts("en-US")
        assert bilingual.accepts("es")
        assert bilingual.accepts("en")
        assert not bilingual.accepts("de")


class MediaTypeAcceptabilityParsingTests(unittest.TestCase):

    def testParsingNothing(self):
        # RFC 2616, 14.1 - If no Accept header field is present,
        #                  then it is assumed that the client
        #                  accepts all media types.
        liberal = MediaTypeAcceptor(None)
        assert liberal.accepts("text/html")
        assert liberal.accepts("anyold/thing")

        liberal = MediaTypeAcceptor("")
        assert liberal.accepts("text/html")
        assert liberal.accepts("anyold/thing")

    def testParsingAll(self):
        liberal = MediaTypeAcceptor("*/*")
        assert liberal.accepts("text/html")
        assert liberal.accepts("anyold/thing")

    def testParsingHorrorShowAll(self):
        liberal = MediaTypeAcceptor("*")
        assert liberal.accepts("text/html")
        assert liberal.accepts("anyold/thing")

    def testParsingOneType(self):
        focused = MediaTypeAcceptor("application/json")
        assert focused.accepts("application/json")
        assert not focused.accepts("text/html")
        assert not focused.accepts("anyold/thing")

    def testParsingTwoTypes(self):
        focused = MediaTypeAcceptor("application/json,text/html")
        assert focused.accepts("application/json")
        assert focused.accepts("text/html")
        assert not focused.accepts("image/jpeg")
        assert not focused.accepts("anyold/thing")

    def testParsingOneTypeRange(self):
        visual = MediaTypeAcceptor("image/*")
        assert visual.accepts("image/png")
        assert visual.accepts("image/jpeg")
        assert not visual.accepts("application/json")
        assert not visual.accepts("text/plain")

    def testParsingOneTypeRangeAndOneType(self):
        visual_and_textual = MediaTypeAcceptor("image/*,text/plain")
        assert visual_and_textual.accepts("image/png")
        assert visual_and_textual.accepts("image/jpeg")
        assert visual_and_textual.accepts("text/plain")
        assert not visual_and_textual.accepts("application/json")

    def testParsingTwoRanges(self):
        visual_and_textual = MediaTypeAcceptor("image/*,text/*")
        assert visual_and_textual.accepts("image/png")
        assert visual_and_textual.accepts("image/jpeg")
        assert visual_and_textual.accepts("text/plain")
        assert not visual_and_textual.accepts("application/json")

    def testParsingChromiumsDefaultAccept(self):
        chromium = MediaTypeAcceptor(ChromiumAcceptString)
        assert chromium.accepts("application/xml")
        assert chromium.accepts("application/xhtml+xml")
        assert chromium.accepts("text/html")
        assert chromium.accepts("text/plain")
        assert chromium.accepts("image/png")
        assert chromium.accepts("anyold/thing")

    def testParsingFirefoxsDefaultAccept(self):
        firefox = MediaTypeAcceptor(FirefoxAcceptString)
        assert firefox.accepts("application/xml")
        assert firefox.accepts("application/xhtml+xml")
        assert firefox.accepts("text/html")
        assert firefox.accepts("text/plain")
        assert firefox.accepts("image/png")
        assert firefox.accepts("anyold/thing")

class AcceptibilitySatisfyingTests(unittest.TestCase):

    def testAFocusedMediaTypeAcceptor(self):
        focused = MediaTypeAcceptor("application/json")
        assert focused.preferred(["application/json"]) == "application/json"
        assert focused.preferred(["text/html", "application/json"]) == "application/json"
        assert not focused.preferred(["text/html"])

    def testAPickyMediaTypeAcceptor(self):
        picky = MediaTypeAcceptor("application/json;q=0.9,text/html;q=0.8")
        assert picky.preferred(["application/json"]) == "application/json"
        assert picky.preferred(["text/html", "application/json"]) == "application/json"
        assert picky.preferred(["text/html"]) == "text/html"

    def testALiberalImageMediaTypeAcceptor(self):
        visual = MediaTypeAcceptor("image/*")
        assert not visual.preferred(["text/html"])
        assert visual.preferred(["image/png"]) == "image/png"
        assert visual.preferred(["image/jpeg", "text/html"]) == "image/jpeg"

    def testALiberalImageMediaTypeAcceptorThatKindaDoesNotMindText(self):
        visual = MediaTypeAcceptor("image/*;q=0.9,text/plain;q=0.1")
        assert not visual.preferred(["text/html"])
        assert visual.preferred(["image/png"]) == "image/png"
        assert visual.preferred(["image/jpeg", "text/html"]) == "image/jpeg"
        assert visual.preferred(["image/jpeg", "text/plain"]) == "image/jpeg"
        assert visual.preferred(["text/plain"]) == "text/plain"
        assert visual.preferred(["text/html", "text/plain"]) == "text/plain"

    def testALiberalMediaTypeAcceptorThatPrefersImagesAndTextToAnythingElse(self):
        visual = MediaTypeAcceptor("image/*;q=0.9,text/plain;q=0.8,*/*;q=0.5")
        assert visual.preferred(["text/html"]) == "text/html"
        assert visual.preferred(["image/png"]) == "image/png"
        assert visual.preferred(["image/jpeg", "text/html"]) == "image/jpeg"
        assert visual.preferred(["image/jpeg", "text/plain"]) == "image/jpeg"
        assert visual.preferred(["text/plain"]) == "text/plain"
        assert visual.preferred(["text/html", "text/plain"]) == "text/plain"

    def testThatPositionBreaksTies(self):
        visual = MediaTypeAcceptor("image/png;q=0.9,image/jpeg;q=0.9,text/plain")
        assert visual.preferred(["image/png", "image/jpeg"]) == "image/png"
        assert visual.preferred(["image/jpeg", "image/png"]) == "image/png"

    def testThatAMediaTypeMustHaveASlash(self):
        self.assertRaises(AssertionError, MediaTypeAcceptor, "image;q=0.9,image/jpeg;q=0.9,text/plain")

        strict = MediaTypeAcceptor("image/*;q=0.9,image/jpeg;q=0.9,text/plain")
        assert not any(map(lambda mr: "image" in mr, strict.ranges))

    def testChromiumMediaTypeAcceptor(self):
        chromium = MediaTypeAcceptor(ChromiumAcceptString)
        assert chromium.preferred(["text/html"]) == "text/html"
        assert chromium.preferred(["text/html", "application/xhtml+xml"]) == "application/xhtml+xml"
        assert chromium.preferred(["image/jpeg", "image/png", "text/plain"]) == "image/png"
        assert chromium.preferred(["image/jpeg", "text/plain"]) == "text/plain"

    def testFirefoxMediaTypeAcceptor(self):
        firefox = MediaTypeAcceptor(FirefoxAcceptString)
        assert firefox.preferred(["text/html"]) == "text/html"
        assert firefox.preferred(["text/html", "application/xhtml+xml"]) == "text/html"
        assert firefox.preferred(["image/jpeg", "image/png", "text/plain"]) == "image/jpeg"
        assert firefox.preferred(["image/jpeg", "text/plain"]) == "image/jpeg"

    def testIE7MediaTypeAcceptor(self):
        ie7 = MediaTypeAcceptor(IE7AcceptString)
        assert ie7.preferred(["text/html"]) == "text/html"
        assert ie7.preferred(["text/html", "application/xhtml+xml"]) == "text/html"
        assert ie7.preferred(["image/jpeg", "image/png", "text/plain"]) == "image/jpeg"
        assert ie7.preferred(["image/jpeg", "text/plain"]) == "image/jpeg"

    def testIE8MediaTypeAcceptor(self):
        ie8 = MediaTypeAcceptor(IE8AcceptString)
        assert ie8.preferred(["text/html"]) == "text/html"
        assert ie8.preferred(["text/html", "application/xhtml+xml"]) == "text/html"
        assert ie8.preferred(["image/jpeg", "image/png", "text/plain"]) == "image/jpeg"
        assert ie8.preferred(["image/jpeg", "text/plain"]) == "image/jpeg"

    def testFeedReaderAcceptor(self):
        fr = MediaTypeAcceptor(BogusFeedReaderAcceptString)
        assert fr.preferred(["application/atom+xml"]) == "application/atom+xml"
        assert fr.preferred(["application/rdf+xml", "application/atom+xml"]) == "application/atom+xml"
