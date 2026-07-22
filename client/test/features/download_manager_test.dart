import 'dart:convert';
import 'dart:io';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/local_database.dart';
import 'package:campushub/features/resources/data/download_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Future<LocalDatabase> _openDb() =>
    LocalDatabase.open(inMemoryDatabasePath, factory: databaseFactoryFfi);

void main() {
  sqfliteFfiInit();

  test('downloads via local content endpoint and records the file', () async {
    final db = await _openDb();
    final tempDir = await Directory.systemTemp.createTemp('dl_test_');
    final content = 'lecture notes'.codeUnits;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/v1/resources/r-1/download') {
          return http.Response(
            jsonEncode({
              'download_url': null,
              'inline': true,
              'size_bytes': content.length,
              'checksum': 'abc123',
            }),
            200,
          );
        }
        expect(request.url.path, '/api/v1/resources/r-1/content');
        return http.Response.bytes(content, 200);
      }),
    );
    final manager = DownloadManager(api, db, tempDir);

    final before = await manager.status('r-1');
    expect(before.state, DownloadState.notDownloaded);

    final result = await manager.download('r-1');
    expect(result.state, DownloadState.downloaded);
    expect(File(result.localPath!).readAsBytesSync(), content);

    final after =
        await manager.status('r-1', currentVersionSize: content.length);
    expect(after.state, DownloadState.downloaded);
    await db.close();
    await tempDir.delete(recursive: true);
  });

  test('downloads via presigned URL without sending the bearer token',
      () async {
    final db = await _openDb();
    final tempDir = await Directory.systemTemp.createTemp('dl_test_');
    final content = 'slides'.codeUnits;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/v1/resources/r-2/download') {
          return http.Response(
            jsonEncode({
              'download_url': 'http://s3.test/bucket/key?sig=xyz',
              'inline': false,
              'size_bytes': content.length,
              'checksum': 'def456',
            }),
            200,
          );
        }
        if (request.url.toString() == 'http://s3.test/bucket/key?sig=xyz') {
          expect(request.headers.containsKey('Authorization'), isFalse);
          return http.Response.bytes(content, 200);
        }
        return http.Response('unexpected', 404);
      }),
      tokenProvider: _StaticToken('secret-token'),
    );
    final manager = DownloadManager(api, db, tempDir);

    final result = await manager.download('r-2');
    expect(File(result.localPath!).readAsBytesSync(), content);
    await db.close();
    await tempDir.delete(recursive: true);
  });

  test('a size change on the server marks the local copy stale', () async {
    final db = await _openDb();
    final tempDir = await Directory.systemTemp.createTemp('dl_test_');
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path.endsWith('/download')) {
          return http.Response(
            jsonEncode({
              'download_url': null,
              'inline': true,
              'size_bytes': 10,
              'checksum': 'v1',
            }),
            200,
          );
        }
        return http.Response.bytes(List.filled(10, 1), 200);
      }),
    );
    final manager = DownloadManager(api, db, tempDir);
    await manager.download('r-3');

    // Catalog now reports a different size for the current version.
    final status = await manager.status('r-3', currentVersionSize: 99);
    expect(status.state, DownloadState.staleVersionAvailable);
    await db.close();
    await tempDir.delete(recursive: true);
  });

  test('removeDownload deletes the file and the tracking row', () async {
    final db = await _openDb();
    final tempDir = await Directory.systemTemp.createTemp('dl_test_');
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path.endsWith('/download')) {
          return http.Response(
            jsonEncode({
              'download_url': null,
              'inline': true,
              'size_bytes': 4,
              'checksum': 'v1',
            }),
            200,
          );
        }
        return http.Response.bytes([1, 2, 3, 4], 200);
      }),
    );
    final manager = DownloadManager(api, db, tempDir);
    final result = await manager.download('r-4');
    final file = File(result.localPath!);
    expect(await file.exists(), isTrue);

    await manager.removeDownload('r-4');
    expect(await file.exists(), isFalse);
    final status = await manager.status('r-4');
    expect(status.state, DownloadState.notDownloaded);
    await db.close();
    await tempDir.delete(recursive: true);
  });
}

class _StaticToken implements TokenProvider {
  _StaticToken(this._token);
  final String _token;

  @override
  String? get accessToken => _token;

  @override
  Future<bool> refresh() async => false;
}
