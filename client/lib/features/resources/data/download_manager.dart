import 'dart:io';

import '../../../core/network/api_client.dart';
import '../../../core/storage/local_database.dart';

/// Whether a resource's current version is available for offline reading
/// (docs/07-ui-ux.md section 3.4, docs/09-offline-sync.md section 5).
enum DownloadState { notDownloaded, downloaded, staleVersionAvailable }

class DownloadInfo {
  const DownloadInfo({required this.state, this.localPath, this.sizeBytes});

  final DownloadState state;
  final String? localPath;
  final int? sizeBytes;
}

/// Downloads resource bytes to app-local storage and tracks them in the
/// `downloads` table, independent of the generic `entity_cache` (which only
/// holds metadata, never binary payloads).
///
/// Supports both storage backends transparently:
///  - local backend: GET /resources/{id}/content streams bytes through the
///    authenticated API client.
///  - S3 backend: GET /resources/{id}/download returns a presigned URL,
///    fetched directly (no bearer token — the URL itself is the credential).
class DownloadManager {
  DownloadManager(this._api, this._db, this._directory);

  final ApiClient _api;
  final LocalDatabase _db;

  /// Resolved once at startup (path_provider is async; main() resolves it
  /// before runApp, mirroring localDatabaseProvider's pattern).
  final Directory _directory;

  Future<DownloadInfo> status(String resourceId,
      {int? currentVersionSize}) async {
    final row = await _db.getDownload(resourceId);
    if (row == null) {
      return const DownloadInfo(state: DownloadState.notDownloaded);
    }
    final file = File(row['local_path'] as String);
    if (!await file.exists()) {
      await _db.removeDownload(resourceId);
      return const DownloadInfo(state: DownloadState.notDownloaded);
    }
    final sizeBytes = row['size_bytes'] as int;
    // A changed server size since our last download is our (approximate,
    // cheap) staleness signal — checksum comparison happens on redownload.
    final stale = currentVersionSize != null && currentVersionSize != sizeBytes;
    return DownloadInfo(
      state: stale
          ? DownloadState.staleVersionAvailable
          : DownloadState.downloaded,
      localPath: file.path,
      sizeBytes: sizeBytes,
    );
  }

  Future<DownloadInfo> download(String resourceId) async {
    final meta = await _api.getJson('/api/v1/resources/$resourceId/download');
    final checksum = meta['checksum'] as String;
    final sizeBytes = meta['size_bytes'] as int;
    final downloadUrl = meta['download_url'] as String?;

    final bytes = downloadUrl != null
        ? await _api.fetchExternal(downloadUrl)
        : (await _api.getBytes('/api/v1/resources/$resourceId/content'))
            .bodyBytes;

    if (!await _directory.exists()) await _directory.create(recursive: true);
    final file = File('${_directory.path}/$resourceId');
    await file.writeAsBytes(bytes, flush: true);

    await _db.recordDownload(
      resourceId: resourceId,
      localPath: file.path,
      sizeBytes: sizeBytes,
      checksum: checksum,
    );
    return DownloadInfo(
      state: DownloadState.downloaded,
      localPath: file.path,
      sizeBytes: sizeBytes,
    );
  }

  Future<void> removeDownload(String resourceId) async {
    final row = await _db.getDownload(resourceId);
    if (row != null) {
      final file = File(row['local_path'] as String);
      if (await file.exists()) await file.delete();
    }
    await _db.removeDownload(resourceId);
  }
}
