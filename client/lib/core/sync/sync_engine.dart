import 'dart:convert';

import '../error/app_exception.dart';
import '../network/api_client.dart';
import '../storage/local_database.dart';

/// Result of one sync cycle, surfaced to the UI sync-status chip
/// (docs/07-ui-ux.md section 4, FR-SYNC-4).
class SyncResult {
  const SyncResult({
    required this.pushed,
    required this.conflicts,
    required this.rejected,
    required this.pulled,
    required this.offline,
  });

  final int pushed;
  final int conflicts;
  final int rejected;
  final int pulled;
  final bool offline;
}

/// Push-then-pull sync cycle (docs/09-offline-sync.md sections 2-4).
///
/// Push: drains `sync_queue` FIFO via POST /sync/batch. Applied items leave
/// the queue; conflicts/errors are marked terminal for that client_id (the
/// user resolves and a NEW client_id is enqueued — docs/09 section 3).
/// Pull: GET /sync/changes?since={cursor}, upserting into `entity_cache`
/// and advancing the stored cursor only after the page is applied.
class SyncEngine {
  SyncEngine(this._api, this._db);

  final ApiClient _api;
  final LocalDatabase _db;

  static const _cursorKey = 'pull_cursor';
  static const _batchLimit = 50;

  Future<SyncResult> runSyncCycle() async {
    var pushed = 0;
    var conflicts = 0;
    var rejected = 0;
    var pulled = 0;

    try {
      // --- Push ---
      while (true) {
        final items = await _db.pendingQueueItems(limit: _batchLimit);
        if (items.isEmpty) break;

        final response = await _api.postJson('/api/v1/sync/batch', {
          'items': [
            for (final item in items)
              {
                'client_id': item['client_id'],
                'entity_table': item['entity_table'],
                'entity_id': item['entity_id'],
                'operation': item['operation'],
                'payload': jsonDecode(item['payload'] as String),
                'base_version': item['base_version'],
              }
          ],
        });

        for (final raw in response['results'] as List<dynamic>) {
          final result = raw as Map<String, dynamic>;
          final clientId = result['client_id'] as String;
          switch (result['status'] as String) {
            case 'applied':
              pushed++;
              await _db.markQueueItem(clientId, 'applied');
            case 'conflict':
              conflicts++;
              await _db.markQueueItem(
                clientId,
                'conflict',
                errorCode: 'SYNC_CONFLICT',
                errorMessage: jsonEncode({
                  'server_version': result['server_version'],
                  'server_payload': result['server_payload'],
                }),
              );
            default:
              rejected++;
              await _db.markQueueItem(
                clientId,
                'rejected',
                errorCode: result['error_code'] as String?,
                errorMessage: result['error_message'] as String?,
              );
          }
        }
        if (items.length < _batchLimit) break;
      }

      // --- Pull ---
      var cursor = int.tryParse(await _db.getState(_cursorKey) ?? '0') ?? 0;
      while (true) {
        final page = await _api.getJson(
          '/api/v1/sync/changes',
          query: {'since': '$cursor', 'limit': '200'},
        );
        final changes = page['changes'] as List<dynamic>;
        for (final raw in changes) {
          final change = raw as Map<String, dynamic>;
          await _db.upsertEntity(
            entityTable: change['entity_table'] as String,
            entityId: change['entity_id'] as String,
            payloadJson: jsonEncode(change['payload']),
            serverVersion: change['version'] as int,
            deleted: change['operation'] == 'delete',
          );
          pulled++;
        }
        cursor = page['next_cursor'] as int;
        await _db.setState(_cursorKey, '$cursor');
        if (page['has_more'] != true) break;
      }
    } on NetworkUnavailableException {
      // Offline: everything stays queued; retry on next cycle
      // (docs/09 section 9 — connectivity errors retry, 4xx do not).
      return SyncResult(
        pushed: pushed,
        conflicts: conflicts,
        rejected: rejected,
        pulled: pulled,
        offline: true,
      );
    }

    return SyncResult(
      pushed: pushed,
      conflicts: conflicts,
      rejected: rejected,
      pulled: pulled,
      offline: false,
    );
  }
}
