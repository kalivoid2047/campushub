"""Unit tests for upload content-signature validation (docs/08 section 6)."""

from app.modules.resources.content_validation import matches_declared_type
from app.modules.resources.models import ResourceType

PDF = b"%PDF-1.4\n%rest of a real pdf..."
DOCX = b"PK\x03\x04" + b"\x00" * 20  # OOXML/ZIP signature
LEGACY_DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20  # OLE2 signature
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 10
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
AVI = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 10
PLAIN_TEXT = b"just some plain bytes, not a real file format at all"


def test_pdf_matches_document_and_slide():
    assert matches_declared_type(ResourceType.DOCUMENT, PDF)
    assert matches_declared_type(ResourceType.SLIDE, PDF)


def test_docx_and_legacy_doc_match_document():
    assert matches_declared_type(ResourceType.DOCUMENT, DOCX)
    assert matches_declared_type(ResourceType.DOCUMENT, LEGACY_DOC)


def test_video_signatures_match_video_only():
    for sample in (MP4, WEBM, AVI):
        assert matches_declared_type(ResourceType.VIDEO, sample)
        assert not matches_declared_type(ResourceType.DOCUMENT, sample)
        assert not matches_declared_type(ResourceType.SLIDE, sample)


def test_plain_bytes_match_nothing_but_link():
    assert not matches_declared_type(ResourceType.DOCUMENT, PLAIN_TEXT)
    assert not matches_declared_type(ResourceType.SLIDE, PLAIN_TEXT)
    assert not matches_declared_type(ResourceType.VIDEO, PLAIN_TEXT)


def test_link_type_is_exempt_from_signature_checks():
    # LINK resources carry no binary payload of their own.
    assert matches_declared_type(ResourceType.LINK, PLAIN_TEXT)
    assert matches_declared_type(ResourceType.LINK, b"")


def test_declaring_a_video_as_a_document_is_rejected():
    # The concrete attack shape this guards against: uploading an
    # executable/script disguised via a benign-sounding declared type.
    assert not matches_declared_type(ResourceType.DOCUMENT, MP4)
