"""Server-side file-content validation for uploads (docs/08-security-design.md
section 6): the declared ResourceType must match what the bytes actually
are, independent of the client-supplied filename/Content-Type header, both
of which are fully attacker-controlled.

Signature (magic-byte) checks only — not a full parser. Good enough to
catch "this isn't remotely the format it claims to be" without a
heavyweight dependency (python-magic requires the libmagic system library,
which isn't part of this project's native-install deployment target).
"""

from app.modules.resources.models import ResourceType


def _is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _is_office_open_xml(data: bytes) -> bool:
    # docx/pptx/xlsx are all ZIP containers; distinguishing the exact kind
    # would need reading the archive's [Content_Types].xml, more than a
    # signature check needs to do here.
    return data.startswith(b"PK\x03\x04")


def _is_legacy_office(data: bytes) -> bool:
    # Legacy .doc/.ppt/.xls (OLE2 compound file).
    return data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _is_video(data: bytes) -> bool:
    if len(data) >= 12 and data[4:8] == b"ftyp":  # MP4/MOV family
        return True
    if data.startswith(b"\x1a\x45\xdf\xa3"):  # WebM/MKV (EBML header)
        return True
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return True
    return False


# Resource types with no entry (LINK) carry no binary payload of their own
# and are exempt from signature checking.
_SIGNATURE_CHECKS: dict[ResourceType, tuple] = {
    ResourceType.DOCUMENT: (_is_pdf, _is_office_open_xml, _is_legacy_office),
    ResourceType.SLIDE: (_is_pdf, _is_office_open_xml, _is_legacy_office),
    ResourceType.VIDEO: (_is_video,),
}


def matches_declared_type(resource_type: ResourceType, data: bytes) -> bool:
    checks = _SIGNATURE_CHECKS.get(resource_type)
    if checks is None:
        return True
    return any(check(data) for check in checks)
