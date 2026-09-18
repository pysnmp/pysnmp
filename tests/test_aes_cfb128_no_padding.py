"""RFC 3826 section 3.1.4: CFB128 is a stream mode and carries no padding.

The ciphertext of an AES-privacy message is the same length as its plaintext.
We used to zero-pad to a 16-octet boundary on both sides, which every receiver
tolerated -- BER decoding stops at the end of the scoped PDU and ignores what
follows -- so the only visible effect was 1 to 16 wasted octets on every
authPriv message, and a peer that checks the privacy payload length against the
scoped PDU would have been entitled to reject us.

The AES-192/256 services in `secmod/eso/priv/` inherit `encryptData`/
`decryptData` from `Aes`, so they are covered by the same parametrisation
rather than by a copy of it.
"""

import pytest
from pyasn1.type import univ

from pysnmp.proto.secmod.eso.priv import aes192, aes256
from pysnmp.proto.secmod.rfc3414.auth import hmacsha
from pysnmp.proto.secmod.rfc3826.priv import aes

#: Every AES privacy service we ship, standards-track and draft alike.
SERVICES = [
    pytest.param(aes.Aes, id="AES-128"),
    pytest.param(aes192.AesBlumenthal192, id="AES-192-Blumenthal"),
    pytest.param(aes256.AesBlumenthal256, id="AES-256-Blumenthal"),
    pytest.param(aes192.Aes192, id="AES-192-Reeder"),
    pytest.param(aes256.Aes256, id="AES-256-Reeder"),
]

#: Lengths either side of the 16-octet block boundary the padding used to chase.
#: 16 and 48 are aligned -- the old arithmetic, `16 - len % 16`, had no zero case
#: and appended a whole redundant block for exactly these.
LENGTHS = [1, 15, 16, 17, 32, 37, 48]

ENGINE_ID = univ.OctetString(hexValue="80004fb805")


def localizedKey(serviceClass):
    service = serviceClass()

    return service, service.localizeKey(
        hmacsha.HmacSha().serviceID, b"privpassphrase12", ENGINE_ID
    )


@pytest.mark.parametrize("serviceClass", SERVICES)
@pytest.mark.parametrize("length", LENGTHS)
def test_ciphertext_is_the_length_of_the_plaintext(serviceClass, length):
    service, key = localizedKey(serviceClass)

    ciphertext, _ = service.encryptData(
        key, (0, 0, univ.OctetString(b"\x00" * 8)), b"A" * length
    )

    assert len(ciphertext) == length


@pytest.mark.parametrize("serviceClass", SERVICES)
@pytest.mark.parametrize("length", LENGTHS)
def test_a_scoped_pdu_round_trips(serviceClass, length):
    service, key = localizedKey(serviceClass)
    plaintext = bytes(range(256))[:length] or b""

    ciphertext, salt = service.encryptData(
        key, (0, 0, univ.OctetString(b"\x00" * 8)), plaintext
    )
    decrypted = service.decryptData(key, (0, 0, univ.OctetString(salt)), ciphertext)

    assert bytes(decrypted) == plaintext


@pytest.mark.parametrize("serviceClass", SERVICES)
def test_a_pyasn1_payload_is_accepted_on_both_sides(serviceClass):
    # The padding expression used to coerce an OctetString to bytes on its way
    # past; without it the coercion has to be asked for explicitly, so both
    # entry points are exercised with a pyasn1 value rather than raw bytes.
    service, key = localizedKey(serviceClass)
    plaintext = univ.OctetString(b"scoped PDU of an awkward length")

    ciphertext, salt = service.encryptData(
        key, (0, 0, univ.OctetString(b"\x00" * 8)), plaintext
    )
    decrypted = service.decryptData(
        key, (0, 0, univ.OctetString(salt)), univ.OctetString(ciphertext)
    )

    assert len(ciphertext) == len(plaintext)
    assert bytes(decrypted) == plaintext.asOctets()


@pytest.mark.parametrize("serviceClass", SERVICES)
def test_trailing_octets_from_a_padding_peer_still_decrypt(serviceClass):
    # Interoperability in the other direction: a peer still running the old
    # padding sends a ciphertext longer than its scoped PDU. CFB decrypts each
    # segment independently, so the prefix must come back intact and the extra
    # octets must not disturb it -- which is what let the defect go unnoticed.
    service, key = localizedKey(serviceClass)
    plaintext = b"B" * 37

    ciphertext, salt = service.encryptData(
        key, (0, 0, univ.OctetString(b"\x00" * 8)), plaintext + b"\x00" * 11
    )
    decrypted = service.decryptData(key, (0, 0, univ.OctetString(salt)), ciphertext)

    assert bytes(decrypted)[: len(plaintext)] == plaintext


def test_des_still_pads():
    # RFC 3414 section 8.1.1.2: DES runs in CBC and genuinely does need the
    # plaintext brought to an 8-octet boundary. Pinned so that "remove the
    # padding" is not later applied to the module where it belongs.
    from pysnmp.proto.secmod.rfc3414.priv import des

    service = des.Des()
    key = service.localizeKey(
        hmacsha.HmacSha().serviceID, b"privpassphrase12", ENGINE_ID
    )

    ciphertext, _ = service.encryptData(key, (0, 0, None), b"A" * 5)

    assert len(ciphertext) % 8 == 0
    assert len(ciphertext) > 5
