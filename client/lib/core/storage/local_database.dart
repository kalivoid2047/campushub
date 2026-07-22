import 'package:sqflite/sqflite.dart';

/// Local SQLite store (docs/09-offline-sync.md section 1).
///
/// Two concerns live here:
///  - `entity_cache`: a generic entity mirror (one row per server entity,
///    JSON payload) fed by delta pull; feature repositories read through it
///    when offline.
///  - `sync_queue`: mutations made offline, drained by the SyncEngine
///    against POST /sync/batch (docs/09 section 2).
///
/// Raw SQL (no codegen) keeps the schema in one visible place; sqflite on
/// mobile, sqflite_common_ffi on desktop and in tests.
class LocalDatabase {
  LocalDatabase(this._db);

  final Database _db;

  static const schemaVersion = 2;

  static Future<LocalDatabase> open(
    String path, {
    DatabaseFactory? factory,
  }) async {
    final databaseFactory = factory ?? databaseFactoryOrNull;
    if (databaseFactory == null) {
      throw StateError('No sqflite database factory configured');
    }
    final db = await databaseFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: schemaVersion,
        onCreate: (db, version) async {
          await _createV1Tables(db);
          await _createDownloadsTable(db);
        },
        onUpgrade: (db, oldVersion, newVersion) async {
          if (oldVersion < 2) await _createDownloadsTable(db);
        },
      ),
    );
    return LocalDatabase(db);
  }

  static Future<void> _createV1Tables(Database db) async {
    await db.execute('''
      CREATE TABLE entity_cache (
        entity_table TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        server_version INTEGER NOT NULL DEFAULT 1,
        deleted INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (entity_table, entity_id)
      )
    ''');
    await db.execute('''
      CREATE TABLE sync_queue (
        client_id TEXT PRIMARY KEY,
        entity_table TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        payload TEXT NOT NULL,
        base_version INTEGER,
        state TEXT NOT NULL DEFAULT 'pending',
        error_code TEXT,
        error_message TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE sync_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');
  }

  /// Tracks resources downloaded for offline reading (docs/09 section 5,
  /// docs/07-ui-ux.md section 3.4 download manager).
  static Future<void> _createDownloadsTable(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS downloads (
        resource_id TEXT PRIMARY KEY,
        local_path TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        checksum TEXT NOT NULL,
        downloaded_at TEXT NOT NULL
      )
    ''');
  }

  Database get raw => _db;

  // --- Entity cache -----------------------------------------------------

  Future<void> upsertEntity({
    required String entityTable,
    required String entityId,
    required String payloadJson,
    required int serverVersion,
    bool deleted = false,
  }) async {
    await _db.insert(
      'entity_cache',
      {
        'entity_table': entityTable,
        'entity_id': entityId,
        'payload': payloadJson,
        'server_version': serverVersion,
        'deleted': deleted ? 1 : 0,
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<Map<String, Object?>?> getEntity(
      String entityTable, String entityId) async {
    final rows = await _db.query(
      'entity_cache',
      where: 'entity_table = ? AND entity_id = ? AND deleted = 0',
      whereArgs: [entityTable, entityId],
      limit: 1,
    );
    return rows.isEmpty ? null : rows.first;
  }

  Future<List<Map<String, Object?>>> listEntities(String entityTable) {
    return _db.query(
      'entity_cache',
      where: 'entity_table = ? AND deleted = 0',
      whereArgs: [entityTable],
      orderBy: 'updated_at DESC',
    );
  }

  // --- Sync queue ---------------------------------------------------------

  Future<void> enqueue({
    required String clientId,
    required String entityTable,
    required String entityId,
    required String operation,
    required String payloadJson,
    int? baseVersion,
  }) async {
    await _db.insert('sync_queue', {
      'client_id': clientId,
      'entity_table': entityTable,
      'entity_id': entityId,
      'operation': operation,
      'payload': payloadJson,
      'base_version': baseVersion,
      'state': 'pending',
      'attempts': 0,
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  /// Oldest-first pending items (FIFO preserves causal order, docs/09 s2).
  Future<List<Map<String, Object?>>> pendingQueueItems({int limit = 50}) {
    return _db.query(
      'sync_queue',
      where: "state = 'pending'",
      orderBy: 'created_at ASC',
      limit: limit,
    );
  }

  Future<void> markQueueItem(
    String clientId,
    String state, {
    String? errorCode,
    String? errorMessage,
  }) async {
    await _db.rawUpdate(
      'UPDATE sync_queue SET state = ?, error_code = ?, error_message = ?, '
      'attempts = attempts + 1 WHERE client_id = ?',
      [state, errorCode, errorMessage, clientId],
    );
  }

  Future<int> countQueue(String state) async {
    final result = await _db.rawQuery(
      'SELECT COUNT(*) AS c FROM sync_queue WHERE state = ?',
      [state],
    );
    return (result.first['c'] as int?) ?? 0;
  }

  // --- Sync state (pull cursor, etc.) ----------------------------------

  Future<String?> getState(String key) async {
    final rows = await _db.query('sync_state',
        where: 'key = ?', whereArgs: [key], limit: 1);
    return rows.isEmpty ? null : rows.first['value'] as String?;
  }

  Future<void> setState(String key, String value) async {
    await _db.insert(
      'sync_state',
      {'key': key, 'value': value},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  // --- Downloads ------------------------------------------------------------

  Future<void> recordDownload({
    required String resourceId,
    required String localPath,
    required int sizeBytes,
    required String checksum,
  }) async {
    await _db.insert(
      'downloads',
      {
        'resource_id': resourceId,
        'local_path': localPath,
        'size_bytes': sizeBytes,
        'checksum': checksum,
        'downloaded_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<Map<String, Object?>?> getDownload(String resourceId) async {
    final rows = await _db.query(
      'downloads',
      where: 'resource_id = ?',
      whereArgs: [resourceId],
      limit: 1,
    );
    return rows.isEmpty ? null : rows.first;
  }

  Future<void> removeDownload(String resourceId) async {
    await _db.delete(
      'downloads',
      where: 'resource_id = ?',
      whereArgs: [resourceId],
    );
  }

  Future<void> close() => _db.close();
}

/// sqflite's global factory is null until a platform implementation (or the
/// ffi factory in tests/desktop) is installed.
DatabaseFactory? get databaseFactoryOrNull {
  try {
    return databaseFactory;
  } catch (_) {
    return null;
  }
}
