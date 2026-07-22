import 'dart:math';

final _secureRandom = Random.secure();

/// RFC 4122 v4 UUID from a CSPRNG, without a package dependency. Used
/// wherever the client needs to generate a client-side entity/idempotency
/// id (docs/09-offline-sync.md section 2: client_id doubles as the sync
/// idempotency key).
String newUuid() {
  final bytes = List<int>.generate(16, (_) => _secureRandom.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
      '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}
